import io
from uuid import UUID

import anyio
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.core.s3 import get_s3_client
from app.main import logger
from app.services.media.models import ImageStatus, ProductImage


def _process_image_sync(image_data: bytes) -> bytes:
    """
    Synchronously open and re-save an image to sanitize it.

    Args:
        image_data: Raw image bytes from S3.

    Returns:
        Sanitized image bytes in the original format.

    Raises:
        UnidentifiedImageError: If the file is not a valid image.
        ValueError: If the image format is unsupported.
    """
    with Image.open(io.BytesIO(image_data)) as img:
        output = io.BytesIO()
        img.save(output, format=img.format)
        return output.getvalue()


async def sanitize_and_activate_image_task(
    ctx: dict,
    image_id: UUID,
    bucket: str,
    object_key: str,
) -> None:
    """
    Download, sanitize, re-upload, and activate a product image.

    This task runs asynchronously after an S3 upload webhook. It downloads
    the image, validates and re-encodes it via Pillow, writes the sanitized
    version back to S3, and updates the database status to ACTIVE.

    Args:
        ctx: Task context containing 'session_maker' for database access.
        image_id: ID of the ProductImage record to process.
        bucket: S3 bucket name.
        object_key: S3 object key of the uploaded image.

    Raises:
        UnidentifiedImageError: If the uploaded file is not a valid image.
    """
    session_maker = ctx['session_maker']
    try:
        async with get_s3_client() as s3_client:
            response = await s3_client.get_object(Bucket=bucket, Key=object_key)
            image_data = await response['Body'].read()
            try:
                sanitized_data = await anyio.to_thread.run_sync(
                    _process_image_sync, image_data
                )
            except (UnidentifiedImageError, ValueError) as e:
                logger.error('invalid image file', image_id=image_id, error=str(e))
                raise
            await s3_client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=sanitized_data,
                ContentType=response.get('ContentType', 'image/jpeg'),
            )
        async with session_maker() as session:
            result = await session.execute(
                select(ProductImage).where(ProductImage.id == image_id)
            )
            image = result.scalar_one_or_none()
            if image:
                image.status = ImageStatus.ACTIVE
                await session.commit()
                logger.info('image sanitized and activated', image_id=image_id)
    except Exception as e:
        logger.error('failed to sanitize image', image_id=image_id, error=str(e))
        async with session_maker() as session:
            result = await session.execute(
                select(ProductImage).where(ProductImage.id == image_id)
            )
            image = result.scalar_one_or_none()
            if image:
                image.status = ImageStatus.FAILED
                await session.commit()
