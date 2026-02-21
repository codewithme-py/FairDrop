import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, InsufficientInventoryError, NotFoundError
from app.services.inventory.models import Product, Reservation
from app.services.inventory.schemas import ReservationCreate


async def reserve_items(
    session: AsyncSession,
    user_id: UUID,
    idempotency_key: str,
    reservation_data: ReservationCreate,
) -> Reservation:
    result = await session.execute(
        select(Product)
        .with_for_update()
        .where(Product.id == reservation_data.product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise NotFoundError
    if product.qty_available < reservation_data.quantity:
        raise InsufficientInventoryError
    product.qty_available -= reservation_data.quantity
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=settings.reserve_timeout_minutes
    )
    new_reservation = Reservation(
        qty_reserved=reservation_data.quantity,
        user_id=user_id,
        product_id=reservation_data.product_id,
        status='pending',
        idempotency_key=idempotency_key,
        expires_at=expires_at,
    )
    session.add(new_reservation)
    try:
        await session.commit()
        await session.refresh(new_reservation)
        return new_reservation
    except IntegrityError:
        await session.rollback()
        raise ConflictError
