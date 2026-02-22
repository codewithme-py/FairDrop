from typing import Any
from urllib.parse import unquote
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.inventory.internal import ensure_product_exists
from app.services.media.models import ImageStatus, ProductImage
from app.services.media.schemas import (
    ImageUploadRequest,
    ImageUploadResponse,
    MinioWebhookEvent,
)

logger = structlog.get_logger(__name__)


async def generate_upload_url(
    session: AsyncSession,
    s3_client: Any,
    product_id: UUID,
    req: ImageUploadRequest,
) -> ImageUploadResponse:
    await ensure_product_exists(session, product_id)
    image_id = uuid4()
    file_path = f'products/{product_id}/{image_id}-{req.filename}'
    db_image = ProductImage(
        id=image_id,
        product_id=product_id,
        file_path=file_path,
    )
    session.add(db_image)
    await session.commit()
    presigned_url = await s3_client.generate_presigned_post(
        Bucket=settings.minio_bucket_name,
        Key=file_path,
        Fields={'Content-Type': req.content_type},
        Conditions=[
            {'Content-Type': req.content_type},
            [
                'content-length-range',
                settings.min_file_size_bytes,
                settings.max_file_size_bytes,
            ],
        ],
        ExpiresIn=settings.presigned_url_expire_seconds,
    )
    return ImageUploadResponse(
        image_id=image_id,
        url=presigned_url['url'],
        fields=presigned_url['fields'],
    )


async def handle_minio_webhook(
    session: AsyncSession,
    event: MinioWebhookEvent,
) -> None:
    if not event.records:
        return
    for record in event.records:
        if not record.event_name.startswith('s3:ObjectCreated:'):
            continue
        object_key = unquote(record.s3.object.key)
        result = await session.execute(
            select(ProductImage)
            .with_for_update()
            .where(ProductImage.file_path == object_key)
        )
        image = result.scalar_one_or_none()
        if image is not None and image.status == ImageStatus.PENDING:
            image.status = ImageStatus.ACTIVE
            await session.commit()
        else:
            logger.warning('image not found or not in pending status')
