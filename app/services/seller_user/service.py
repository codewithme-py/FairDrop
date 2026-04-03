from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.inventory.models import Product, ProductStatus
from app.services.orders.models import Order, OrderItem, OrderStatus
from app.services.seller_user.schemas import (
    SellerOrderItemRead,
    SellerOrderRead,
    SellerStats,
)


async def get_my_products(
    session: AsyncSession,
    user_id: UUID,
    status: ProductStatus | None = None,
) -> Sequence[Product]:
    stmt = select(Product).where(Product.owner_id == user_id)
    if status:
        stmt = stmt.where(Product.status == status)
    stmt = stmt.order_by(Product.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_my_orders(
    session: AsyncSession,
    user_id: UUID,
    status: OrderStatus | None = None,
) -> list[SellerOrderRead]:
    order_id_stmt = (
        select(Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.owner_id == user_id)
    )
    if status:
        order_id_stmt = order_id_stmt.where(Order.status == status)
    order_ids_result = await session.execute(order_id_stmt)
    order_ids = order_ids_result.scalars().all()
    if not order_ids:
        return []
    stmt = (
        select(Order)
        .where(Order.id.in_(order_ids))
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    result = await session.execute(stmt)
    orders = result.scalars().all()
    seller_orders = []
    for order in orders:
        my_items = [
            SellerOrderItemRead(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
            )
            for item in order.items
            if item.product.owner_id == user_id
        ]
        display_address = None
        if order.status not in (
            OrderStatus.PENDING,
            OrderStatus.FAILED,
            OrderStatus.CANCELLED,
        ):
            display_address = order.shipping_address
        seller_orders.append(
            SellerOrderRead(
                id=order.id,
                status=order.status,
                created_at=order.created_at,
                shipping_address=display_address,
                seller_items=my_items,
            )
        )
    return seller_orders


async def get_my_stats(
    session: AsyncSession,
    user_id: UUID,
) -> SellerStats:
    prod_stmt = (
        select(
            Product.status,
            func.count(Product.id),
        )
        .where(Product.owner_id == user_id)
        .group_by(Product.status)
    )
    prod_result = await session.execute(prod_stmt)
    prod_counts: dict[ProductStatus, int] = {
        row[0]: row[1] for row in prod_result.all()
    }
    order_stmt = (
        select(
            Order.status,
            func.count(func.distinct(Order.id)),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.owner_id == user_id)
        .group_by(Order.status)
    )
    order_result = await session.execute(order_stmt)
    order_counts: dict[OrderStatus, int] = {
        row[0]: row[1] for row in order_result.all()
    }
    return SellerStats(
        total_products=sum(prod_counts.values()),
        active_products=prod_counts.get(ProductStatus.ACTIVE, 0),
        pending_moderation=prod_counts.get(ProductStatus.PENDING_MODERATION, 0),
        rejected_products=prod_counts.get(ProductStatus.REJECTED, 0),
        pending_orders=order_counts.get(OrderStatus.PENDING, 0),
        paid_orders=order_counts.get(OrderStatus.PAID, 0),
    )
