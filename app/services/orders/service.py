import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_log.service import audit_log_service
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import check_ownership
from app.services.inventory.internal import (
    cancel_reservation_by_order_and_return_stock,
    mark_reservation_by_order_as_completed,
)
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import Order, OrderItem, OrderStatus
from app.services.orders.schemas import OrderCreate, OrderResponse
from app.services.user.models import User, UserRole


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
    async def _log_order_change(
        session: AsyncSession,
        user: User,
        order: Order,
        old_snapshot: OrderResponse | None,
        action: str,
    ) -> None:
        await audit_log_service.log_object_change(
            session=session,
            actor_id=user.id,
            target_id=order.id,
            target_type='order',
            action=action,
            old_obj=old_snapshot,
            new_obj=OrderResponse.model_validate(order),
        )

    @staticmethod
    async def get_order_for_details(
        session: AsyncSession,
        order_id: UUID,
        current_user: User,
    ) -> Order:
        order = await OrderService._get_order(session, order_id, current_user)
        if current_user.id != order.user_id and current_user.role in (
            UserRole.ADMIN,
            UserRole.MODERATOR,
        ):
            await audit_log_service.log_pii_access(
                session=session,
                actor_id=current_user.id,
                target_id=order.id,
                target_type='order',
                reason='admin_pii_view',
            )
            await session.commit()
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

        exp_at = (
            reservation.expires_at.replace(tzinfo=None)
            if reservation.expires_at
            else datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        )
        if exp_at < datetime.datetime.now(datetime.UTC).replace(tzinfo=None):
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
            id=uuid4(),
            user_id=current_user.id,
            total_amount=product.price * reservation.qty_reserved,
            status=OrderStatus.PENDING,
            shipping_address=order_data.shipping_address,
        )
        session.add(create_order)
        await session.flush()
        create_order_item = OrderItem(
            id=uuid4(),
            order_id=create_order.id,
            product_id=reservation.product_id,
            product_name=product.name,
            quantity=reservation.qty_reserved,
            price=product.price,
        )
        session.add(create_order_item)
        reservation.order_id = create_order.id
        await session.flush()
        await session.refresh(create_order, attribute_names=['items'])
        await OrderService._log_order_change(
            session=session,
            user=current_user,
            order=create_order,
            old_snapshot=None,
            action='create',
        )
        await session.commit()
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
        await session.flush()
        await session.refresh(order, attribute_names=['items'])
        old_snapshot = OrderResponse.model_validate(order)
        order.status = OrderStatus.PAID
        await OrderService._log_order_change(
            session=session,
            user=current_user,
            order=order,
            old_snapshot=old_snapshot,
            action='payment',
        )
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
        await session.flush()
        await session.refresh(order, attribute_names=['items'])
        old_snapshot = OrderResponse.model_validate(order)
        order.status = OrderStatus.CANCELLED
        await OrderService._log_order_change(
            session=session,
            user=current_user,
            order=order,
            old_snapshot=old_snapshot,
            action='cancel',
        )
        await cancel_reservation_by_order_and_return_stock(session, order_id)
        await session.commit()
        return order
