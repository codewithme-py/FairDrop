from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.orders.models import Order
from app.services.orders.schemas import OrderCreate, OrderResponse
from app.services.orders.service import OrderService
from app.services.user.models import User
from app.shared.decorators import idempotent
from app.shared.deps import get_current_user

router_v1 = APIRouter(prefix='/orders', tags=['Orders'])


@router_v1.post('/', response_model=OrderResponse)
@idempotent()
async def create_order_endpoint(
    request: Request,
    order_data: Annotated[OrderCreate, Body(...)],
    x_idempotency_key: Annotated[str, Header(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Order:
    """
    Create a new order from an existing reservation.

    The reservation must belong to the current user, be in PENDING status,
    and not yet expired. Stock is transferred from the reservation to the order.

    Args:
        request: FastAPI request object.
        order_data: Order creation payload with reservation ID and optional address.
        x_idempotency_key: Idempotency key for safe retries.
        session: Async database session.
        current_user: Authenticated user placing the order.

    Returns:
        The created order with its line items.
    """
    return await OrderService.create_order_from_reservation(
        session=session,
        current_user=current_user,
        order_data=order_data,
    )


@router_v1.get('/{order_id}', response_model=OrderResponse)
async def get_order_details_endpoint(
    order_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Order:
    """
    Retrieve details of a specific order.

    Users can only access their own orders. Admins and moderators may
    view any order (access is logged for audit).

    Args:
        order_id: ID of the order to retrieve.
        session: Async database session.
        current_user: Authenticated user.

    Returns:
        Order details including line items.

    Raises:
        NotFoundError: If the order does not exist.
        PermissionDeniedError: If the user does not own the order.
    """
    return await OrderService.get_order_for_details(
        session=session,
        order_id=order_id,
        current_user=current_user,
    )


@router_v1.post('/{order_id}/pay', response_model=OrderResponse)
@idempotent()
async def confirm_order_payment_endpoint(
    request: Request,
    order_id: UUID,
    x_idempotency_key: Annotated[str, Header(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Order:
    """
    Confirm payment for a pending order.

    Transitions the order from PENDING to PAID and marks the associated
    reservation as completed.

    Args:
        request: FastAPI request object.
        order_id: ID of the order to pay.
        x_idempotency_key: Idempotency key for safe retries.
        session: Async database session.
        current_user: Authenticated user (must own the order).

    Returns:
        The updated order with PAID status.

    Raises:
        ConflictError: If the order is not in PENDING status.
    """
    return await OrderService.confirm_order_payment(
        session=session,
        order_id=order_id,
        current_user=current_user,
    )


@router_v1.post('/{order_id}/cancel', response_model=OrderResponse)
@idempotent()
async def cancel_order_endpoint(
    request: Request,
    order_id: UUID,
    x_idempotency_key: Annotated[str, Header(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Order:
    """
    Cancel a pending order and return reserved stock.

    Only orders in PENDING status can be cancelled. The associated
    reservation is cancelled and stock is restored.

    Args:
        request: FastAPI request object.
        order_id: ID of the order to cancel.
        x_idempotency_key: Idempotency key for safe retries.
        session: Async database session.
        current_user: Authenticated user (must own the order).

    Returns:
        The updated order with CANCELLED status.

    Raises:
        ConflictError: If the order is not in PENDING status.
    """
    return await OrderService.cancel_order(
        session=session,
        order_id=order_id,
        current_user=current_user,
    )
