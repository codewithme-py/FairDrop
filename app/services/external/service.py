from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product, ProductStatus
from app.services.orders.models import Order


async def get_external_catalog(
    session: AsyncSession,
) -> Sequence[Product]:
    """
    Fetch all active products for the partner catalog.

    Args:
        session: Async database session.

    Returns:
        Sequence of active products ordered by name.
    """
    stmt = (
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_external_order_status(
    session: AsyncSession,
    user_id: UUID,
    order_id: UUID,
) -> Order | None:
    """
    Retrieve a specific order if it belongs to the given user.

    Args:
        session: Async database session.
        user_id: ID of the order owner.
        order_id: ID of the order to look up.

    Returns:
        The Order object if found and owned by the user, or None.
    """
    stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
