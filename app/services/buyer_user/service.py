from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.buyer_user.schemas import BuyerStats
from app.services.orders.models import Order, OrderStatus


async def get_my_orders(
    session: AsyncSession,
    user_id: UUID,
    status: OrderStatus | None = None,
) -> Sequence[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    if status:
        stmt = stmt.where(Order.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_my_stats(
    session: AsyncSession,
    user_id: UUID,
) -> BuyerStats:
    stmt = (
        select(Order.status, func.count(Order.id))
        .where(Order.user_id == user_id)
        .group_by(Order.status)
    )
    result = await session.execute(stmt)
    counts: dict[OrderStatus, int] = {row[0]: row[1] for row in result.all()}

    return BuyerStats(
        total_orders=sum(counts.values()),
        pending_orders=counts.get(OrderStatus.PENDING, 0),
        paid_orders=counts.get(OrderStatus.PAID, 0),
        shipped_orders=counts.get(OrderStatus.SHIPPED, 0),
    )
