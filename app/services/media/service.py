from typing import Any, cast
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
from app.services.user.models import VerificationRequest

logger = structlog.get_logger(__name__)


async def generate_presigned_get_url(
    s3_client: Any,
    key: str,
    expires_in: int = 3600,
) -> str:
    """Generates a presigned GET URL for reading private files."""
    return cast(
        str,
        await s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.minio_bucket_name, 'Key': key},
            ExpiresIn=expires_in,
        ),
    )


async def get_secure_file_path(
    session: AsyncSession,
    target_type: str,
    target_id: UUID,
    doc_key: str | None = None,
) -> str | None:
    """Resolves a secure S3 path from a database resource."""
    if target_type == 'verification_doc':
        result_v = await session.execute(
            select(VerificationRequest).where(VerificationRequest.id == target_id)
        )
        v_req = result_v.scalar_one_or_none()
        if v_req and v_req.docs_url and doc_key:
            doc_val = v_req.docs_url.get(doc_key)
            return str(doc_val) if doc_val else None
    elif target_type == 'product_image':
        result_i = await session.execute(
            select(ProductImage).where(ProductImage.id == target_id)
        )
        img = result_i.scalar_one_or_none()
        if img:
            return str(img.file_path)
    return None


async def sanitize_image_metadata(
    s3_client: Any,
    bucket: str,
    key: str,
) -> None:
    """OBSOLETE: Moved to tasks.py"""
    pass


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
    arq_redis: Any = None,
) -> None:
    """Processes MinIO S3:ObjectCreated events with idempotency and robust errors."""
    if not event.records:
        return
    for record in event.records:
        if not record.event_name.startswith('s3:ObjectCreated:'):
            logger.debug('skipping non-create event', event_name=record.event_name)
            continue
        object_key = unquote(record.s3.object.key)
        result = await session.execute(
            select(ProductImage)
            .with_for_update()
            .where(ProductImage.file_path == object_key)
        )
        image = result.scalar_one_or_none()
        if image is None:
            logger.warning('image record not found in DB for S3 event', key=object_key)
            continue
        if image.status != ImageStatus.PENDING:
            logger.info(
                'skipping webhook: image not in pending status',
                key=object_key,
                current_status=image.status,
            )
            continue
        if not arq_redis:
            logger.error(
                'CRITICAL: arq_redis pool missing, cannot enqueue sanitization',
                key=object_key,
            )
            continue
        await arq_redis.enqueue_job(
            'sanitize_and_activate_image_task',
            image_id=image.id,
            bucket=settings.minio_bucket_name,
            object_key=object_key,
        )
        logger.info(
            'enqueued image sanitization task', image_id=image.id, key=object_key
        )
    await session.commit()
