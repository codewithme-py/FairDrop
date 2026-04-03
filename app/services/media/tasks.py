import io
from uuid import UUID

from PIL import Image
from sqlalchemy import select

from app.core.s3 import get_s3_client
from app.services.media.models import ImageStatus, ProductImage


async def sanitize_and_activate_image_task(
    ctx: dict,
    image_id: UUID,
    bucket: str,
    object_key: str,
) -> None:
    """Background task to strip EXIF and activate an image."""
    session_maker = ctx['session_maker']

    # 1. Sanitize the image
    async with get_s3_client() as s3_client:
        response = await s3_client.get_object(Bucket=bucket, Key=object_key)
        image_data = await response['Body'].read()

        with Image.open(io.BytesIO(image_data)) as img:
            output = io.BytesIO()
            img.save(output, format=img.format)
            output.seek(0)

            await s3_client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=output,
                ContentType=response.get('ContentType', 'image/jpeg'),
            )

    # 2. Update status in database
    async with session_maker() as session:
        result = await session.execute(
            select(ProductImage).where(ProductImage.id == image_id)
        )
        image = result.scalar_one_or_none()
        if image:
            image.status = ImageStatus.ACTIVE
            await session.commit()
