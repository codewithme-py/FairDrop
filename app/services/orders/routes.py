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
    return await OrderService.cancel_order(
        session=session,
        order_id=order_id,
        current_user=current_user,
    )
