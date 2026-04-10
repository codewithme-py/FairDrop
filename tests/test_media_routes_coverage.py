from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.media.routes import (
    create_upload_url,
    minio_webhook,
    view_private_file,
)
from app.services.media.schemas import ImageUploadRequest, MinioWebhookEvent
from app.services.user.models import User, UserRole


@pytest.mark.asyncio
@patch('app.services.media.routes.generate_upload_url', new_callable=AsyncMock)
async def test_route_create_upload_url(mock_service: Any) -> None:
    """Verify create_upload_url route delegates to the service layer."""
    mock_service.return_value = 'mock_res'

    req = ImageUploadRequest(filename='t.png', content_type='image/png')
    res = await create_upload_url(
        uuid4(),
        req,
        session=MagicMock(),
        s3_client=MagicMock(),
        current_user=MagicMock(),
    )
    assert res == 'mock_res'


@pytest.mark.asyncio
@patch('app.services.media.routes.handle_minio_webhook', new_callable=AsyncMock)
async def test_route_minio_webhook(mock_service: Any) -> None:
    """Verify minio_webhook route delegates to the handler and returns ok status."""
    mock_req = MagicMock()
    event = MinioWebhookEvent.model_validate({'Records': []})
    res = await minio_webhook(mock_req, event, session=MagicMock())
    assert res == {'status': 'ok'}


@pytest.mark.asyncio
async def test_route_view_private_file_forbidden() -> None:
    """Verify view_private_file returns 403 for non-admin/non-verification users."""
    u = User(role=UserRole.SELLER)
    with pytest.raises(HTTPException) as exc:
        await view_private_file(
            'type', uuid4(), 'doc', MagicMock(), MagicMock(), current_user=u
        )
    assert exc.value.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
@patch('app.services.media.routes.get_secure_file_path', new_callable=AsyncMock)
async def test_route_view_private_file_not_found(mock_get: Any) -> None:
    """Verify view_private_file returns 404 when the file path cannot be resolved."""
    mock_get.return_value = None
    u = User(role=UserRole.ADMIN)
    with pytest.raises(HTTPException) as exc:
        await view_private_file(
            'type', uuid4(), 'doc', MagicMock(), MagicMock(), current_user=u
        )
    assert exc.value.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@patch('app.services.media.routes.get_secure_file_path', new_callable=AsyncMock)
@patch('app.services.media.routes.generate_presigned_get_url', new_callable=AsyncMock)
@patch(
    'app.services.media.routes.audit_log_service.log_pii_access', new_callable=AsyncMock
)
async def test_route_view_private_file_success(
    mock_audit: Any, mock_url: Any, mock_get: Any
) -> None:
    """Verify view_private_file returns redirect and logs PII access for admins."""
    u = User(id=uuid4(), role=UserRole.ADMIN)
    mock_get.return_value = 's3://path'
    mock_url.return_value = 'http://url'
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    res = await view_private_file(
        'verification_doc',
        uuid4(),
        'doc_key',
        mock_session,
        MagicMock(),
        current_user=u,
    )
    assert res.status_code == 307
    assert res.headers['location'] == 'http://url'
    mock_audit.assert_called_once()
    mock_session.commit.assert_called_once()
