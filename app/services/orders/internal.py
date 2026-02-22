from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.services.orders.models import Order, OrderStatus


async def cancel_order_by_system(session: AsyncSession, order_id: UUID) -> None:
    order_result = await session.execute(
        select(Order).with_for_update().where(Order.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise NotFoundError
    order.status = OrderStatus.CANCELLED
