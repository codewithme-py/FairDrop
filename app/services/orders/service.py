import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import check_ownership
from app.services.inventory.internal import (
    cancel_reservation_by_order_and_return_stock,
    mark_reservation_by_order_as_completed,
)
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import Order, OrderItem, OrderStatus
from app.services.orders.schemas import OrderCreate
from app.services.user.models import User


class OrderService:
    @staticmethod
    async def _get_order(
        session: AsyncSession,
        order_id: UUID,
        current_user: User,
        for_update: bool = False,
    ) -> Order:
        stmt = select(Order).where(Order.id == order_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError
        check_ownership(current_user, order)
        return order

    @staticmethod
    async def create_order_from_reservation(
        session: AsyncSession,
        current_user: User,
        order_data: OrderCreate,
    ) -> Order:
        reservation_result = await session.execute(
            select(Reservation)
            .with_for_update()
            .where(
                Reservation.id == order_data.reservation_id,
                Reservation.user_id == current_user.id,
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
            user_id=current_user.id,
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
        await session.refresh(create_order, attribute_names=['items'])
        return create_order

    @staticmethod
    async def confirm_order_payment(
        session: AsyncSession, order_id: UUID, current_user: User
    ) -> Order:
        order = await OrderService._get_order(
            session, order_id, current_user, for_update=True
        )
        if order.status != OrderStatus.PENDING:
            raise ConflictError
        order.status = OrderStatus.PAID
        await mark_reservation_by_order_as_completed(session, order_id)
        await session.commit()
        return order

    @staticmethod
    async def cancel_order(
        session: AsyncSession, order_id: UUID, current_user: User
    ) -> Order:
        order = await OrderService._get_order(
            session, order_id, current_user, for_update=True
        )
        if order.status != OrderStatus.PENDING:
            raise ConflictError

        order.status = OrderStatus.CANCELLED
        await cancel_reservation_by_order_and_return_stock(session, order_id)
        await session.commit()
        return order
