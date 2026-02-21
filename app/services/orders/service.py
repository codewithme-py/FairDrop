import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import Order, OrderItem, OrderStatus
from app.services.orders.schemas import OrderCreate


async def create_order_from_reservation(
    session: AsyncSession,
    user_id: UUID,
    order_data: OrderCreate,
) -> Order:
    reservation_result = await session.execute(
        select(Reservation)
        .with_for_update()
        .where(
            Reservation.id == order_data.reservation_id,
            Reservation.user_id == user_id,
            Reservation.status == OrderStatus.PENDING,
        )
    )
    reservation = reservation_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    if reservation.expires_at < datetime.datetime.now(datetime.UTC):
        raise ConflictError
    if reservation.order_id is not None:
        raise ConflictError
    product = (
        await session.execute(
            select(Product).where(Product.id == reservation.product_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise NotFoundError
    create_order = Order(
        user_id=user_id,
        total_amount=product.price * reservation.qty_reserved,
        status=OrderStatus.PENDING,
        shipping_address=order_data.shipping_address,
    )
    session.add(create_order)
    await session.flush()
    create_order_item = OrderItem(
        order_id=create_order.id,
        product_id=reservation.product_id,
        product_name=product.name,
        quantity=reservation.qty_reserved,
        price=product.price,
    )
    session.add(create_order_item)
    reservation.order_id = create_order.id
    await session.commit()
    return create_order


async def _get_locked_order_and_reservation(
    session: AsyncSession, order_id: UUID, user_id: UUID
) -> tuple[Order, Reservation]:
    order_result = await session.execute(
        select(Order)
        .with_for_update()
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise NotFoundError
    if order.status != OrderStatus.PENDING:
        raise ConflictError
    res_result = await session.execute(
        select(Reservation).with_for_update().where(Reservation.order_id == order_id)
    )
    reservation = res_result.scalar_one_or_none()
    if not reservation:
        raise NotFoundError
    return order, reservation


async def confirm_order_payment(
    session: AsyncSession,
    order_id: UUID,
    user_id: UUID,
) -> Order:
    order, reservation = await _get_locked_order_and_reservation(
        session, order_id, user_id
    )
    order.status = OrderStatus.PAID
    reservation.status = OrderStatus.COMPLETED
    await session.commit()
    return order


async def cancel_order(
    session: AsyncSession,
    order_id: UUID,
    user_id: UUID,
) -> Order:
    order, reservation = await _get_locked_order_and_reservation(
        session, order_id, user_id
    )
    product_rollback = await session.execute(
        select(Product).with_for_update().where(Product.id == reservation.product_id)
    )
    product = product_rollback.scalar_one_or_none()
    if product:
        product.qty_available += reservation.qty_reserved
    order.status = OrderStatus.CANCELLED
    reservation.status = OrderStatus.CANCELLED
    await session.commit()
    return order
