from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import OrderStatus


async def mark_reservation_as_completed(
    session: AsyncSession, reservation_id: UUID
) -> None:
    res_result = await session.execute(
        select(Reservation).with_for_update().where(Reservation.id == reservation_id)
    )
    reservation = res_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    reservation.status = OrderStatus.COMPLETED


async def mark_reservation_by_order_as_completed(
    session: AsyncSession, order_id: UUID
) -> None:
    res_result = await session.execute(
        select(Reservation).with_for_update().where(Reservation.order_id == order_id)
    )
    reservation = res_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    reservation.status = OrderStatus.COMPLETED


async def cancel_reservation_and_return_stock(
    session: AsyncSession, reservation_id: UUID
) -> None:
    res_result = await session.execute(
        select(Reservation).with_for_update().where(Reservation.id == reservation_id)
    )
    reservation = res_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    prod_result = await session.execute(
        select(Product).with_for_update().where(Product.id == reservation.product_id)
    )
    product = prod_result.scalar_one_or_none()
    if product:
        product.qty_available += reservation.qty_reserved
    reservation.status = OrderStatus.CANCELLED


async def cancel_reservation_by_order_and_return_stock(
    session: AsyncSession, order_id: UUID
) -> None:
    res_result = await session.execute(
        select(Reservation).with_for_update().where(Reservation.order_id == order_id)
    )
    reservation = res_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    prod_result = await session.execute(
        select(Product).with_for_update().where(Product.id == reservation.product_id)
    )
    product = prod_result.scalar_one_or_none()
    if product:
        product.qty_available += reservation.qty_reserved
    reservation.status = OrderStatus.CANCELLED


async def ensure_product_exists(
    session: AsyncSession,
    product_id: UUID,
) -> None:
    prod_result = await session.execute(
        select(Product.id).where(Product.id == product_id)
    )
    if prod_result.scalar_one_or_none() is None:
        raise NotFoundError
