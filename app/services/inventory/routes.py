from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.core.config import settings
from app.core.database import SessionDep
from app.core.s3 import get_s3_client_gen
from app.core.security import RoleChecker, UserRole
from app.services.inventory.models import ProductStatus
from app.services.inventory.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ReservationCreate,
    ReservationResponse,
)
from app.services.inventory.service import InventoryAdminService, InventoryService
from app.services.media.service import generate_presigned_get_url
from app.services.user.models import User
from app.shared.decorators import idempotent
from app.shared.deps import get_current_user
from app.shared.rate_limit import check_rate_limit

from .deps import (
    get_inventory_admin_service,
    get_inventory_service,
)

router_v1 = APIRouter(prefix='/inventory', tags=['Inventory'])

SELLER_DEPENDENCY = Depends(
    RoleChecker(
        allowed_roles=[UserRole.SELLER, UserRole.SELLER_B2B],
        required_verified=False,
    )
)
ADMIN_DEPENDENCY = Depends(
    RoleChecker(
        allowed_roles=[UserRole.ADMIN, UserRole.MODERATOR],
    )
)
ADMIN_AND_SELLER_DEPENDENCY = Depends(
    RoleChecker(
        allowed_roles=[
            UserRole.ADMIN,
            UserRole.MODERATOR,
            UserRole.SELLER,
            UserRole.SELLER_B2B,
        ],
    )
)


async def _enrich_product_images(product: Any, s3_client: Any) -> ProductRead:
    """
    Generate presigned URLs for a product's images and attach them to the response.

    Args:
        product: SQLAlchemy Product instance with loaded images relationship.
        s3_client: S3 client for generating presigned URLs.

    Returns:
        ProductRead schema with image_urls populated.
    """
    read_obj = ProductRead.model_validate(product)
    image_urls = []
    if hasattr(product, 'images'):
        for img in product.images:
            if img.status == 'active':
                url = await generate_presigned_get_url(s3_client, img.file_path)
                image_urls.append(url)
    read_obj.image_urls = image_urls
    return read_obj


@router_v1.get('/', response_model=list[ProductRead])
async def get_active_products(
    session: SessionDep,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    s3_client: Any = Depends(get_s3_client_gen),
    skip: int = 0,
    limit: int = 50,
) -> list[ProductRead]:
    """
    List active products available for purchase with pagination.

    Args:
        session: Async database session.
        service: Inventory service instance.
        s3_client: S3 client for generating image URLs.
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.

    Returns:
        Paginated list of active products with presigned image URLs.
    """
    products = await service.get_products(
        status=ProductStatus.ACTIVE,
        skip=skip,
        limit=limit,
        session=session,
    )
    return [await _enrich_product_images(p, s3_client) for p in products]


@router_v1.post('/', response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    session: SessionDep,
    current_user: Annotated[User, SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
    """
    Create a new product as a seller.

    Args:
        product_data: Product creation payload.
        session: Async database session.
        current_user: Authenticated seller user.
        service: Inventory service instance.

    Returns:
        The created product with assigned ID and timestamps.
    """
    product = await service.create_product(
        current_user=current_user,
        session=session,
        product_data=product_data,
        owner_id=current_user.id,
    )
    return ProductRead.model_validate(product)


@router_v1.patch('/{product_id}/activate', response_model=ProductRead)
async def activate_product(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
    """
    Activate a product, making it visible and purchasable (admin only).

    Args:
        product_id: ID of the product to activate.
        session: Async database session.
        current_user: Authenticated admin user.
        service: Inventory admin service instance.

    Returns:
        The updated product with ACTIVE status.
    """
    product = await service.change_status(
        session=session,
        product_id=product_id,
        status=ProductStatus.ACTIVE,
        current_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.patch('/{product_id}', response_model=ProductRead)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_AND_SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
    """
    Update product details. Only the owner or an admin can modify a product.

    Updating an active product will automatically revert it to PENDING_MODERATION.

    Args:
        product_id: ID of the product to update.
        product_data: Fields to update (partial payload).
        session: Async database session.
        current_user: Authenticated seller or admin user.
        service: Inventory service instance.

    Returns:
        The updated product.
    """
    product = await service.update_product(
        session=session,
        product_id=product_id,
        product_data=product_data,
        current_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> None:
    """
    Delete a product permanently (admin only).

    Args:
        product_id: ID of the product to delete.
        session: Async database session.
        current_user: Authenticated admin user.
        service: Inventory service instance.
    """
    await service.delete_product(
        session=session,
        product_id=product_id,
        current_user=current_user,
    )


@router_v1.get('/{product_id}', response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: SessionDep,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    s3_client: Any = Depends(get_s3_client_gen),
) -> ProductRead:
    """
    Retrieve a single product by ID with presigned image URLs.

    Args:
        product_id: ID of the product to retrieve.
        session: Async database session.
        service: Inventory service instance.
        s3_client: S3 client for generating image URLs.

    Returns:
        Product details with presigned image URLs.

    Raises:
        NotFoundError: If the product does not exist.
    """
    product = await service.get_product(
        session=session,
        product_id=product_id,
    )
    return await _enrich_product_images(product, s3_client)


@router_v1.post('/reserve', response_model=ReservationResponse)
@idempotent()
async def reservation_data(
    request: Request,
    reservation_data: ReservationCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    x_idempotency_key: str = Header(...),
) -> ReservationResponse:
    """
    Reserve stock for a specific product.

    Requires authentication and idempotency key. This endpoint is
    rate-limited per user and per product.

    Args:
        request: FastAPI request object for rate limiting.
        reservation_data: Reservation payload with product ID and quantity.
        session: Async database session.
        current_user: Authenticated user making the reservation.
        service: Inventory service instance.
        x_idempotency_key: Idempotency key to prevent duplicate reservations.

    Returns:
        Created reservation details including expiration time.

    Raises:
        NotFoundError: If the product does not exist.
        InsufficientInventoryError: If requested quantity exceeds available stock.
        ConflictError: If the idempotency key is already used.
    """
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        keys=[
            f'rate_limit:user:{current_user.id}',
            f'rate_limit:item:{reservation_data.product_id}',
        ],
        limits=[settings.rate_limit_user_rps, settings.rate_limit_global_rps],
    )
    result = await service.reserve_items(
        session=session,
        user_id=current_user.id,
        idempotency_key=x_idempotency_key,
        reservation_data=reservation_data,
    )
    return ReservationResponse.model_validate(result)


@router_v1.post('/{product_id}/submit', response_model=ProductRead)
async def submit_for_moderation(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
    """
    Submit a product for admin moderation.

    Only DRAFT or REJECTED products can be submitted.

    Args:
        product_id: ID of the product to submit.
        session: Async database session.
        current_user: Authenticated seller user (must own the product).
        service: Inventory service instance.

    Returns:
        The product with status set to PENDING_MODERATION.

    Raises:
        ConflictError: If the product is not in DRAFT or REJECTED status.
    """
    product = await service.submit_for_moderation(
        session=session,
        product_id=product_id,
        current_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/{product_id}/approve', response_model=ProductRead)
async def approve_product(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
    """
    Approve a product under moderation, making it active (admin/moderator only).

    Args:
        product_id: ID of the product to approve.
        session: Async database session.
        current_user: Authenticated admin or moderator user.
        service: Inventory admin service instance.

    Returns:
        The product with status set to ACTIVE.

    Raises:
        ConflictError: If the product is not in MODERATION_IN_PROGRESS status.
    """
    product = await service.approve_product(
        session=session,
        product_id=product_id,
        moderator_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/{product_id}/reject', response_model=ProductRead)
async def reject_product(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
    reason: str = Query(...),
) -> ProductRead:
    """
    Reject a product under moderation with a reason (admin/moderator only).

    Args:
        product_id: ID of the product to reject.
        session: Async database session.
        current_user: Authenticated admin or moderator user.
        service: Inventory admin service instance.
        reason: Rejection reason provided to the seller.

    Returns:
        The product with status set to REJECTED.

    Raises:
        ConflictError: If the product is not in MODERATION_IN_PROGRESS status.
    """
    product = await service.reject_product(
        session=session,
        product_id=product_id,
        moderator_user=current_user,
        reason=reason,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/{product_id}/claim', response_model=ProductRead)
async def claim_for_moderation(
    product_id: UUID,
    session: SessionDep,
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
    """
    Claim a product for moderation, assigning it to the current admin/moderator.

    Args:
        product_id: ID of the product to claim.
        session: Async database session.
        current_user: Authenticated admin or moderator user.
        service: Inventory admin service instance.

    Returns:
        The product with status set to MODERATION_IN_PROGRESS and moderator_id assigned.

    Raises:
        ConflictError: If the product is not in PENDING_MODERATION status.
    """
    product = await service.claim_for_moderation(
        session=session,
        product_id=product_id,
        moderator_user=current_user,
    )
    return ProductRead.model_validate(product)
