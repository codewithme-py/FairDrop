from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.external.schemas import (
    ExternalOrderResponse,
    ExternalProductRead,
)
from app.services.external.service import (
    get_external_catalog,
    get_external_order_status,
)
from app.services.user.models import User
from app.shared.deps import get_api_key_user

router_v1 = APIRouter(prefix='/external', tags=['Partner API'])


@router_v1.get('/catalog', response_model=list[ExternalProductRead])
async def fetch_catalog(
    session: AsyncSession = Depends(get_session),
    current_partner: User = Depends(get_api_key_user),
) -> list[ExternalProductRead]:
    """
    Retrieve the active product catalog for an authenticated B2B partner.

    Args:
        session: Async database session.
        current_partner: Partner user authenticated via API key.

    Returns:
        List of active products with name, price, and available quantity.
    """
    products = await get_external_catalog(session)
    return [ExternalProductRead.model_validate(p) for p in products]


@router_v1.get('/orders/{order_id}/status', response_model=ExternalOrderResponse)
async def fetch_order_status(
    order_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_partner: User = Depends(get_api_key_user),
) -> ExternalOrderResponse:
    """
    Retrieve the status of a specific order owned by the authenticated partner.

    Args:
        order_id: Unique identifier of the order.
        session: Async database session.
        current_partner: Partner user authenticated via API key.

    Returns:
        Order status and last-updated timestamp.

    Raises:
        HTTPException: 404 if the order is not found or the partner lacks access.
    """
    order = await get_external_order_status(session, current_partner.id, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Order not found or access denied',
        )
    return ExternalOrderResponse.model_validate(order)
