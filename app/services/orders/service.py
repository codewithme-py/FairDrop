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
    """
    Service class for order lifecycle operations.

    All methods are static and handle order creation, retrieval,
    payment confirmation, and cancellation.
    """

    @staticmethod
    async def _get_order(
        session: AsyncSession,
        order_id: UUID,
        current_user: User,
        for_update: bool = False,
    ) -> Order:
        """
        Fetch an order by ID with ownership verification.

        Args:
            session: Async database session.
            order_id: ID of the order to fetch.
            current_user: User requesting access (must own the order).
            for_update: If True, acquire a row-level lock.

        Returns:
            The Order instance.

        Raises:
            NotFoundError: If the order does not exist.
            PermissionDeniedError: If the user does not own the order.
        """
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
        """
        Record an audit log entry for an order state change.

        Args:
            session: Async database session.
            user: User who performed the action.
            order: The modified order instance.
            old_snapshot: Order state before the change.
            action: Type of action (e.g., 'create', 'payment', 'cancel').
        """
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
        """
        Retrieve order details with items eagerly loaded.

        Admin and moderator users can view any order; access is logged for audit.

        Args:
            session: Async database session.
            order_id: ID of the order to retrieve.
            current_user: Authenticated user requesting the order.

        Returns:
            The Order instance with items loaded.

        Raises:
            NotFoundError: If the order does not exist.
            PermissionDeniedError: If the user lacks access.
        """
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
        """
        Create an order from an existing pending reservation.

        Validates that the reservation belongs to the user, is not expired,
        and has not already been converted to an order.

        Args:
            session: Async database session.
            current_user: Authenticated user creating the order.
            order_data: Payload containing reservation ID and optional shipping address.

        Returns:
            The newly created Order with line items.

        Raises:
            NotFoundError: If the reservation or product does not exist.
            ConflictError: If the reservation is expired or already used.
        """
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
        """
        Mark a pending order as paid and complete its reservation.

        Args:
            session: Async database session.
            order_id: ID of the order to confirm payment for.
            current_user: Authenticated user (must own the order).

        Returns:
            The updated order with PAID status.

        Raises:
            ConflictError: If the order is not in PENDING status.
        """
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
        """
        Cancel a pending order and return reserved stock.

        Args:
            session: Async database session.
            order_id: ID of the order to cancel.
            current_user: Authenticated user (must own the order).

        Returns:
            The updated order with CANCELLED status.

        Raises:
            ConflictError: If the order is not in PENDING status.
        """
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
