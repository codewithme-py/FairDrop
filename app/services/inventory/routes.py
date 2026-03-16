from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
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
from app.services.inventory.service import InventoryService
from app.services.user.models import User
from app.shared.decorators import idempotent
from app.shared.deps import get_current_user

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
    skip: int = 0,
    limit: int = 50,
) -> list[ProductRead]:
    products = await InventoryService.get_products(
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
) -> ProductRead:
    product = await InventoryService.create_product(
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
) -> ProductRead:
    product = await InventoryService.change_status(
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
) -> ProductRead:
    product = await InventoryService.update_product(
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
) -> None:
    await InventoryService.delete_product(
        session=session,
        product_id=product_id,
        current_user=current_user,
    )


@router_v1.get('/{product_id}', response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductRead:
    product = await InventoryService.get_product(
        session=session,
        product_id=product_id,
    )
    return ProductRead.model_validate(product)


@router_v1.post('/reserve', response_model=ReservationResponse)
@idempotent()
async def reservation_data(
    request: Request,
    reservation_data: ReservationCreate,
    x_idempotency_key: str = Header(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReservationResponse:
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        user_id=str(current_user.id),
        item_id=str(reservation_data.product_id),
    )
    result = await InventoryService.reserve_items(
        session=session,
        user_id=current_user.id,
        idempotency_key=x_idempotency_key,
        reservation_data=reservation_data,
    )
    return ReservationResponse.model_validate(result)
