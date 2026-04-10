from collections import deque
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product, Reservation
from app.services.inventory.tasks import release_expired_reservations
from app.services.media.models import ImageStatus, ProductImage
from app.services.media.schemas import MinioWebhookEvent, S3Entity, S3Object, S3Record
from app.services.media.service import handle_minio_webhook
from app.services.media.tasks import sanitize_and_activate_image_task
from app.services.orders.models import OrderStatus


class SimpleMockSession:
    """A deterministic mock session that returns predefined responses in order."""

    def __init__(self, responses: Any = None) -> None:
        self.responses = deque(responses or [])
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt: Any) -> Any:
        res = MagicMock()
        val = self.responses.popleft() if self.responses else None
        res.scalars.return_value.all.return_value = (
            val if isinstance(val, list) else [val]
        )
        res.scalar_one_or_none.return_value = val
        return res

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> 'SimpleMockSession':
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    def begin_nested(self) -> MagicMock:
        return MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())


@pytest.mark.asyncio
async def test_inventory_tasks_error_isolation() -> None:
    """Verify that one failing reservation doesn't stop others."""
    res_id1, res_id2 = uuid4(), uuid4()
    mock_session = SimpleMockSession(
        [
            [res_id1, res_id2],
            Reservation(id=res_id1, product_id=uuid4(), status=OrderStatus.PENDING),
            None,
            Reservation(id=res_id2, product_id=uuid4(), status=OrderStatus.PENDING),
            Product(id=uuid4(), qty_available=10),
        ]
    )
    ctx = {'session_maker': MagicMock(return_value=mock_session)}
    with patch('app.services.inventory.tasks.cancel_order_by_system', AsyncMock()):
        await release_expired_reservations(ctx)
    assert mock_session.committed is True


@pytest.mark.asyncio
async def test_media_task_failed_status_on_error() -> None:
    """Verify image status changes to FAILED if sanitization fails."""
    img_id = uuid4()
    img_obj = ProductImage(id=img_id, status=ImageStatus.PENDING)
    mock_session = SimpleMockSession([img_obj, img_obj])
    ctx = {'session_maker': MagicMock(return_value=mock_session)}
    with patch('app.services.media.tasks.get_s3_client') as mock_s3:
        mock_s3.return_value.__aenter__.return_value.get_object.side_effect = Exception(
            'S3 Down'
        )
        await sanitize_and_activate_image_task(ctx, img_id, 'b', 'k')
    assert img_obj.status == ImageStatus.FAILED
    assert mock_session.committed is True


@pytest.mark.asyncio
async def test_media_webhook_idempotency_check() -> None:
    """Verify webhook doesn't enqueue if status is not PENDING."""
    img_obj = ProductImage(id=uuid4(), status=ImageStatus.ACTIVE, file_path='k')
    mock_session = SimpleMockSession([img_obj])
    mock_arq = AsyncMock()
    event = MinioWebhookEvent(
        Records=[
            S3Record(
                eventName='s3:ObjectCreated:Put', s3=S3Entity(object=S3Object(key='k'))
            )
        ]
    )
    await handle_minio_webhook(
        cast(AsyncSession, mock_session), event, arq_redis=mock_arq
    )
    mock_arq.enqueue_job.assert_not_called()
    assert mock_session.committed is True
