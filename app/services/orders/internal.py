from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.services.orders.models import Order, OrderStatus


async def cancel_order_by_system(session: AsyncSession, order_id: UUID) -> None:
    """
    Cancel an order by ID without performing ownership checks.

    This function is intended for internal system use (e.g., reservation
    expiry cleanup) where user context is not available.

    Args:
        session: Async database session.
        order_id: ID of the order to cancel.

    Raises:
        NotFoundError: If the order does not exist.
    """
    order_result = await session.execute(
        select(Order).with_for_update().where(Order.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise NotFoundError
    order.status = OrderStatus.CANCELLED
