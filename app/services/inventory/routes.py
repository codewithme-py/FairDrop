from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.inventory.rate_limit import check_rate_limit
from app.services.inventory.schemas import ReservationCreate, ReservationResponse
from app.services.inventory.service import reserve_items
from app.services.user.models import User
from app.shared.decorators import idempotent
from app.shared.deps import get_current_user

router_v1 = APIRouter(prefix='/inventory', tags=['Inventory'])


@router_v1.post('/reserve', response_model=ReservationResponse)
@idempotent()
async def reservation_data(
    request: Request,
    reservation_data: ReservationCreate,
    x_idempotency_key: str = Header(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReservationResponse:
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        user_id=str(current_user.id),
        item_id=str(reservation_data.product_id),
    )
    result = await reserve_items(
        session=session,
        user_id=current_user.id,
        idempotency_key=x_idempotency_key,
        reservation_data=reservation_data,
    )
    return ReservationResponse.model_validate(result)
