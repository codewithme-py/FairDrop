from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RoleChecker
from app.services.inventory.models import ProductStatus
from app.services.orders.models import OrderStatus
from app.services.seller_user.schemas import (
    SellerOrderRead,
    SellerProductRead,
    SellerStats,
)
from app.services.seller_user.service import (
    get_my_orders,
    get_my_products,
    get_my_stats,
)
from app.services.user.models import User, UserRole

router_v1 = APIRouter(prefix='/seller_user', tags=['Seller Dashboard'])

SELLER_DEPENDENCY = Depends(
    RoleChecker(
        allowed_roles=[UserRole.SELLER, UserRole.SELLER_B2B],
        required_verified=True,
    )
)


@router_v1.get('/stats', response_model=SellerStats)
async def fetch_my_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = SELLER_DEPENDENCY,
) -> SellerStats:
    return await get_my_stats(session, current_user.id)


@router_v1.get('/products', response_model=list[SellerProductRead])
async def fetch_my_products(
    status: ProductStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = SELLER_DEPENDENCY,
) -> list[SellerProductRead]:
    products = await get_my_products(session, current_user.id, status)
    return [SellerProductRead.model_validate(p) for p in products]


@router_v1.get('/orders', response_model=list[SellerOrderRead])
async def fetch_my_orders(
    status: OrderStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = SELLER_DEPENDENCY,
) -> list[SellerOrderRead]:
    return await get_my_orders(session, current_user.id, status)
