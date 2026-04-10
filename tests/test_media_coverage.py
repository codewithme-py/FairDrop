from contextlib import asynccontextmanager
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.media.models import ImageStatus, ProductImage
from app.services.media.schemas import ImageUploadRequest, MinioWebhookEvent
from app.services.media.service import (
    generate_presigned_get_url,
    generate_upload_url,
    get_secure_file_path,
    handle_minio_webhook,
)
from app.services.media.tasks import sanitize_and_activate_image_task
from app.services.user.models import VerificationRequest


class SimpleMockSession:
    """A lightweight mock database session for media service unit tests."""

    def __init__(self, target_obj: Any = None) -> None:
        self.target_obj = target_obj
        self.added_objs: list[Any] = []
        self.committed = False

    async def __aenter__(self) -> 'SimpleMockSession':
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = self.target_obj
        mock_res.scalar_one.return_value = self.target_obj
        mock_res.with_for_update.return_value = mock_res
        return mock_res

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        pass

    def add(self, obj: Any) -> None:
        self.added_objs.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added_objs.extend(objs)


@pytest.mark.asyncio
async def test_generate_upload_url_logic() -> None:
    """Verify generate_upload_url creates a record and returns the presigned URL."""
    p_id = uuid4()
    mock_session = SimpleMockSession()
    mock_s3 = AsyncMock()
    mock_s3.generate_presigned_post.return_value = {'url': 'u', 'fields': {}}
    with patch('app.services.media.service.ensure_product_exists', AsyncMock()):
        req = ImageUploadRequest(filename='t.jpg', content_type='image/jpeg')
        resp = await generate_upload_url(
            cast(AsyncSession, mock_session), mock_s3, p_id, req
        )
    assert resp.url == 'u'
    assert len(mock_session.added_objs) == 1
    assert isinstance(mock_session.added_objs[0], ProductImage)


@pytest.mark.asyncio
async def test_handle_webhook_logic() -> None:
    """Verify webhook enqueues a sanitization job for a pending image upload."""
    i_id = uuid4()
    img = ProductImage(id=i_id, file_path='p.jpg', status=ImageStatus.PENDING)
    mock_session = SimpleMockSession(target_obj=img)
    mock_arq = AsyncMock()
    event = MinioWebhookEvent.model_validate(
        {
            'Records': [
                {
                    'eventName': 's3:ObjectCreated:Put',
                    's3': {'object': {'key': 'p.jpg'}},
                }
            ]
        }
    )
    await handle_minio_webhook(
        cast(AsyncSession, mock_session), event, arq_redis=mock_arq
    )
    assert mock_arq.enqueue_job.called


@pytest.mark.asyncio
async def test_get_secure_path_logic() -> None:
    """Verify get_secure_file_path retrieves paths for docs and images."""
    v_id = uuid4()
    v_req = VerificationRequest(id=v_id, docs_url={'p': 'k'})
    mock_session = SimpleMockSession(target_obj=v_req)
    path = await get_secure_file_path(
        cast(AsyncSession, mock_session), 'verification_doc', v_id, 'p'
    )
    assert path == 'k'
    img_id = uuid4()
    img = ProductImage(id=img_id, file_path='img.jpg')
    mock_session.target_obj = img
    path = await get_secure_file_path(
        cast(AsyncSession, mock_session), 'product_image', img_id
    )
    assert path == 'img.jpg'


@pytest.mark.asyncio
async def test_sanitize_task_stable() -> None:
    """Verify sanitize task marks image as ACTIVE after processing."""
    img_id = uuid4()
    img_obj = ProductImage(
        id=img_id,
        product_id=uuid4(),
        file_path='t.jpg',
        status=ImageStatus.PENDING,
    )
    mock_session = SimpleMockSession(target_obj=img_obj)
    mock_sm = MagicMock(return_value=mock_session)
    ctx = {'session_maker': mock_sm}
    mock_body = AsyncMock()
    mock_body.read.return_value = b'data'
    mock_s3 = AsyncMock()
    mock_s3.get_object.return_value = {'Body': mock_body, 'ContentType': 'image/jpeg'}

    @asynccontextmanager
    async def mock_s3_cm() -> Any:
        yield mock_s3

    with (
        patch('PIL.Image.open') as mock_open,
        patch('app.services.media.tasks.get_s3_client', side_effect=mock_s3_cm),
    ):
        mock_img = MagicMock()
        mock_img.format = 'JPEG'
        mock_open.return_value.__enter__.return_value = mock_img
        await sanitize_and_activate_image_task(ctx, img_id, 'b', 'k')
    assert img_obj.status == ImageStatus.ACTIVE
    assert mock_session.committed


@pytest.mark.asyncio
async def test_generate_presigned_get() -> None:
    """Verify generate_presigned_get_url returns the S3 presigned URL."""
    mock_s3 = AsyncMock()
    mock_s3.generate_presigned_url.return_value = 'http://redir'
    url = await generate_presigned_get_url(mock_s3, 'key')
    assert url == 'http://redir'
