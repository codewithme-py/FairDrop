from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RoleChecker
from app.services.buyer_user.schemas import (
    BuyerOrderRead,
    BuyerStats,
)
from app.services.buyer_user.service import (
    get_my_orders,
    get_my_stats,
)
from app.services.orders.models import OrderStatus
from app.services.user.models import User, UserRole

router_v1 = APIRouter(prefix='/buyer_user', tags=['Buyer Dashboard'])

BUYER_DEPENDENCY = Depends(
    RoleChecker(allowed_roles=[UserRole.USER, UserRole.USER_B2B])
)


@router_v1.get('/stats', response_model=BuyerStats)
async def fetch_my_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = BUYER_DEPENDENCY,
) -> BuyerStats:
    """
    Retrieve purchase statistics for the authenticated buyer.

    Args:
        session: Async database session.
        current_user: Authenticated buyer user.

    Returns:
        BuyerStats containing counts of total, pending, paid, and shipped orders.
    """
    return await get_my_stats(session, current_user.id)


@router_v1.get('/orders', response_model=list[BuyerOrderRead])
async def fetch_my_orders(
    status: OrderStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = BUYER_DEPENDENCY,
) -> list[BuyerOrderRead]:
    """
    Retrieve order history for the authenticated buyer.

    Args:
        status: Optional filter by order status.
        session: Async database session.
        current_user: Authenticated buyer user.

    Returns:
        List of orders with their items, optionally filtered by status.
    """
    orders = await get_my_orders(session, current_user.id, status)
    return [BuyerOrderRead.model_validate(o) for o in orders]
