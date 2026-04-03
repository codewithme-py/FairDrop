from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product, ProductStatus
from app.services.orders.models import Order


async def get_external_catalog(
    session: AsyncSession,
) -> Sequence[Product]:
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
    stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
