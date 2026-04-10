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
    """
    Generate a presigned GET URL for reading private files with host substitution.

    Normalizes the S3 key by stripping bucket prefixes and internal URL
    patterns, then generates a time-limited presigned URL.

    Args:
        s3_client: Aioboto3 S3 client instance.
        key: Raw S3 object key (may contain bucket prefix or full URL).
        expires_in: URL expiration time in seconds (default 1 hour).

    Returns:
        Presigned GET URL with the public S3 endpoint substituted.
    """
    logger.debug(
        'generating s3 url',
        input_key=key,
        current_bucket=settings.minio_bucket_name,
    )
    original_key = key
    if '://' in key:
        parts = key.split('/', 3)
        if len(parts) >= 4:
            key = parts[3]
    bucket_candidates = [
        settings.minio_bucket_name,
        's3_fairdrop-media',
        's3-fairdrop-media',
    ]
    while True:
        key = key.lstrip('/')
        stripped = False
        for b in bucket_candidates:
            if key.startswith(f'{b}/'):
                key = key[len(b) + 1 :]
                stripped = True
        if not stripped:
            break
    key = key.lstrip('/')
    if key != original_key:
        logger.debug('sanitized s3 key', original=original_key, sanitized=key)
    url = cast(
        str,
        await s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.minio_bucket_name, 'Key': key},
            ExpiresIn=expires_in,
        ),
    )
    if settings.minio_url != settings.s3_public_url:
        url = url.replace(settings.minio_url, settings.s3_public_url)
    return url


async def get_secure_file_path(
    session: AsyncSession,
    target_type: str,
    target_id: UUID,
    doc_key: str | None = None,
) -> str | None:
    """
    Resolve a secure S3 file path from a database resource.

    Args:
        session: Async database session.
        target_type: Resource type ('verification_doc' or 'product_image').
        target_id: ID of the resource.
        doc_key: Optional document key for verification documents.

    Returns:
        The S3 file path string, or None if the resource is not found.
    """
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
    """OBSOLETE: Moved to tasks.py. No-op retained for backward compatibility."""
    pass


async def generate_upload_url(
    session: AsyncSession,
    s3_client: Any,
    product_id: UUID,
    req: ImageUploadRequest,
) -> ImageUploadResponse:
    """
    Create a ProductImage record and generate a presigned S3 POST upload URL.

    Args:
        session: Async database session.
        s3_client: Aioboto3 S3 client instance.
        product_id: ID of the product to attach the image to.
        req: Upload request with filename and content type.

    Returns:
        Response with the image ID and presigned upload URL/fields.

    Raises:
        NotFoundError: If the product does not exist.
    """
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
    """
    Process MinIO S3:ObjectCreated events with idempotency and robust error handling.

    For each create event, finds the matching ProductImage record in PENDING
    status and enqueues a sanitization task. Non-create events and already-
    processed images are skipped.

    Args:
        session: Async database session.
        event: Parsed MinIO webhook event containing S3 records.
        arq_redis: ARQ Redis connection pool for task enqueueing.
    """
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
