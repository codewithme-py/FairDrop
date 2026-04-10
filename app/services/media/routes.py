from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_log.service import audit_log_service
from app.core.database import get_session
from app.core.s3 import get_s3_client_gen
from app.services.media.schemas import (
    ImageUploadRequest,
    ImageUploadResponse,
    MinioWebhookEvent,
)
from app.services.media.service import (
    generate_presigned_get_url,
    generate_upload_url,
    get_secure_file_path,
    handle_minio_webhook,
)
from app.services.user.models import User, UserRole
from app.shared.deps import get_current_user, get_current_user_flexible

router_v1 = APIRouter(prefix='/media', tags=['Media'])


@router_v1.post('/products/{product_id}/upload_url', response_model=ImageUploadResponse)
async def create_upload_url(
    product_id: UUID,
    req: ImageUploadRequest,
    session: AsyncSession = Depends(get_session),
    s3_client: Any = Depends(get_s3_client_gen),
    current_user: User = Depends(get_current_user),
) -> ImageUploadResponse:
    """
    Generate a presigned S3 upload URL for a product image.

    The client uses the returned URL and fields to upload the image directly
    to S3. A ProductImage record is created in advance in PENDING status.

    Args:
        product_id: ID of the product to attach the image to.
        req: Upload request containing filename and content type.
        session: Async database session.
        s3_client: S3 client for generating presigned URLs.
        current_user: Authenticated user.

    Returns:
        Response containing image ID, presigned upload URL, and form fields.
    """
    return await generate_upload_url(session, s3_client, product_id, req)


@router_v1.post('/webhook/minio')
async def minio_webhook(
    request: Request,
    event: MinioWebhookEvent,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """
    Handle MinIO S3 event notifications for uploaded images.

    On receiving an s3:ObjectCreated event, this endpoint enqueues an
    asynchronous image sanitization task (virus scan, format validation, etc.).

    Args:
        request: FastAPI request containing the ARQ Redis pool.
        event: Parsed MinIO webhook payload.
        session: Async database session.

    Returns:
        Simple status confirmation.
    """
    await handle_minio_webhook(session, event, arq_redis=request.app.state.arq_redis)
    return {'status': 'ok'}


@router_v1.get('/view/{target_type}/{target_id}', response_class=RedirectResponse)
async def view_private_file(
    target_type: str,
    target_id: UUID,
    doc_key: str | None = None,
    session: AsyncSession = Depends(get_session),
    s3_client: Any = Depends(get_s3_client_gen),
    current_user: User = Depends(get_current_user_flexible),
) -> RedirectResponse:
    """
    Generate a temporary redirect to a presigned URL for a private file.

    Only admins and moderators are authorized to view private files.
    Access to verification documents is logged for audit purposes.

    Args:
        target_type: Type of resource ('verification_doc' or 'product_image').
        target_id: ID of the resource.
        doc_key: Optional document key for verification documents.
        session: Async database session.
        s3_client: S3 client for generating presigned URLs.
        current_user: Authenticated user.

    Returns:
        HTTP 307 redirect to the presigned S3 URL.

    Raises:
        HTTPException: 403 if the user is not authorized.
        HTTPException: 404 if the file path cannot be resolved.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.MODERATOR):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not authorized to view this file'
        )
    file_path = await get_secure_file_path(session, target_type, target_id, doc_key)
    if not file_path:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='File not found')
    if target_type == 'verification_doc':
        await audit_log_service.log_pii_access(
            session=session,
            actor_id=current_user.id,
            target_id=target_id,
            target_type='verification_request',
            reason=f'viewing_doc_{doc_key}' if doc_key else 'viewing_verification_doc',
        )
        await session.commit()
    url = await generate_presigned_get_url(s3_client, file_path)
    return RedirectResponse(url=url, status_code=HTTPStatus.TEMPORARY_REDIRECT)
