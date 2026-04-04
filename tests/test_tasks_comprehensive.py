import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from app.services.inventory.models import Product, Reservation
from app.services.inventory.tasks import release_expired_reservations
from app.services.media.models import ImageStatus, ProductImage
from app.services.media.tasks import (
    _process_image_sync,
    sanitize_and_activate_image_task,
)
from app.services.orders.models import OrderStatus


class AsyncContextManagerMock:
    async def __aenter__(self) -> MagicMock:
        return MagicMock()

    async def __aexit__(self, *args: Any) -> None:
        pass


class DeepMockSession:
    def __init__(self, responses: Any = None) -> None:
        self.responses = responses or []
        self.idx = 0
        self.committed = False

    async def execute(self, stmt: Any) -> Any:
        if self.idx < len(self.responses):
            val = self.responses[self.idx]
            self.idx += 1
            if isinstance(val, Exception):
                raise val
            res = MagicMock()
            res.scalars.return_value.all.return_value = (
                val if isinstance(val, list) else [val]
            )
            res.scalar_one_or_none.return_value = val
            return res
        return MagicMock()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    def begin_nested(self) -> AsyncContextManagerMock:
        return AsyncContextManagerMock()

    async def __aenter__(self) -> 'DeepMockSession':
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_inventory_tasks_full_loop() -> None:
    """Verify inventory tasks process multiple reservations and handle stock return."""
    res_id = uuid4()
    p_id = uuid4()
    res = Reservation(
        id=res_id, product_id=p_id, qty_reserved=2, status=OrderStatus.PENDING
    )
    prod = Product(id=p_id, qty_available=10)
    mock_session = DeepMockSession([[res_id], res, prod])
    ctx = {'session_maker': MagicMock(return_value=mock_session)}
    with patch('app.services.inventory.tasks.cancel_order_by_system', AsyncMock()):
        await release_expired_reservations(ctx)
    assert prod.qty_available == 12
    assert res.status == OrderStatus.EXPIRED
    assert mock_session.committed is True


@pytest.mark.asyncio
async def test_inventory_tasks_error_in_loop() -> None:
    """Verify that one failing reservation doesn't stop the loop."""
    res_id1, res_id2 = uuid4(), uuid4()
    mock_session = DeepMockSession(
        [
            [res_id1, res_id2],
            Reservation(id=res_id1, status=OrderStatus.PENDING),
            Exception('DB Fail'),
            Reservation(id=res_id2, status=OrderStatus.PENDING),
            Product(qty_available=10),
        ]
    )
    ctx = {'session_maker': MagicMock(return_value=mock_session)}
    await release_expired_reservations(ctx)
    assert mock_session.idx >= 4


def test_process_image_sync_real() -> None:
    """Test the synchronous PIL processing logic with a real small image."""
    img = Image.new('RGB', (10, 10), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    data = buf.getvalue()
    result = _process_image_sync(data)
    assert len(result) > 0
    assert Image.open(io.BytesIO(result)).size == (10, 10)


@pytest.mark.asyncio
async def test_media_tasks_pil_and_s3() -> None:
    """Verify media task sanitzes image and updates DB/S3."""
    img_id = uuid4()
    img_obj = ProductImage(id=img_id, status=ImageStatus.PENDING)
    mock_session = DeepMockSession([img_obj])
    ctx = {'session_maker': MagicMock(return_value=mock_session)}
    fake_img_data = b'fake_bytes'
    with (
        patch('app.services.media.tasks.get_s3_client') as mock_s3_gen,
        patch(
            'app.services.media.tasks.anyio.to_thread.run_sync',
            AsyncMock(return_value=fake_img_data),
        ),
    ):
        mock_s3 = AsyncMock()
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=AsyncMock(return_value=fake_img_data)),
            'ContentType': 'image/jpeg',
        }
        mock_s3_gen.return_value.__aenter__.return_value = mock_s3
        await sanitize_and_activate_image_task(ctx, img_id, 'bucket', 'key')
    assert img_obj.status == ImageStatus.ACTIVE
    assert mock_s3.put_object.called
    assert mock_session.committed is True
