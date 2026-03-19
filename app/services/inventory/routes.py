from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RoleChecker, UserRole
from app.services.inventory.models import ProductStatus
from app.services.inventory.rate_limit import check_rate_limit
from app.services.inventory.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ReservationCreate,
    ReservationResponse,
)
from app.services.inventory.service import InventoryAdminService, InventoryService
from app.services.user.models import User
from app.shared.decorators import idempotent
from app.shared.deps import get_current_user

from .deps import (
    get_inventory_admin_service,
    get_inventory_service,
)

router_v1 = APIRouter(prefix='/inventory', tags=['Inventory'])

SELLER_DEPENDENCY = Depends(
    RoleChecker(
        allowed_roles=[UserRole.SELLER, UserRole.SELLER_B2B],
        required_verified=True,
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


@router_v1.get('/', response_model=list[ProductRead])
async def get_active_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    skip: int = 0,
    limit: int = 50,
) -> list[ProductRead]:
    products = await service.get_products(
        status=ProductStatus.ACTIVE,
        skip=skip,
        limit=limit,
        session=session,
    )
    return [ProductRead.model_validate(p) for p in products]


@router_v1.post('/', response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
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
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
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
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_AND_SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
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
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> None:
    await service.delete_product(
        session=session,
        product_id=product_id,
        current_user=current_user,
    )


@router_v1.get('/{product_id}', response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
    product = await service.get_product(
        session=session,
        product_id=product_id,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/reserve', response_model=ReservationResponse)
@idempotent()
async def reservation_data(
    request: Request,
    reservation_data: ReservationCreate,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    x_idempotency_key: str = Header(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReservationResponse:
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        user_id=str(current_user.id),
        item_id=str(reservation_data.product_id),
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
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, SELLER_DEPENDENCY],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ProductRead:
    product = await service.submit_for_moderation(
        session=session,
        product_id=product_id,
        current_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/{product_id}/approve', response_model=ProductRead)
async def approve_product(
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
    product = await service.approve_product(
        session=session,
        product_id=product_id,
        moderator_user=current_user,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/{product_id}/reject', response_model=ProductRead)
async def reject_product(
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
    reason: str = Query(...),
) -> ProductRead:
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
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, ADMIN_DEPENDENCY],
    service: Annotated[InventoryAdminService, Depends(get_inventory_admin_service)],
) -> ProductRead:
    product = await service.claim_for_moderation(
        session=session,
        product_id=product_id,
        moderator_user=current_user,
    )
    return ProductRead.model_validate(product)
