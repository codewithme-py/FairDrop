from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.s3 import get_s3_client
from app.services.media.schemas import (
    ImageUploadRequest,
    ImageUploadResponse,
    MinioWebhookEvent,
)
from app.services.media.service import generate_upload_url, handle_minio_webhook
from app.services.user.models import User
from app.shared.deps import get_current_user

router_v1 = APIRouter(prefix='/media', tags=['Media'])


@router_v1.post('/products/{product_id}/upload_url', response_model=ImageUploadResponse)
async def create_upload_url(
    product_id: UUID,
    req: ImageUploadRequest,
    session: AsyncSession = Depends(get_session),
    s3_client: Any = Depends(get_s3_client),
    current_user: User = Depends(get_current_user),
) -> ImageUploadResponse:
    return await generate_upload_url(session, s3_client, product_id, req)


@router_v1.post('/webhook/minio')
async def minio_webhook(
    event: MinioWebhookEvent,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await handle_minio_webhook(session, event)
    return {'status': 'ok'}
