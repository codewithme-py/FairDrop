from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    InsufficientInventoryError,
    NotFoundError,
)
from app.core.security import check_ownership
from app.services.inventory.models import Product, ProductStatus, Reservation
from app.services.inventory.schemas import (
    ProductCreate,
    ProductUpdate,
    ReservationCreate,
)
from app.services.orders.models import OrderStatus
from app.services.user.models import User


class InventoryService:
    @staticmethod
    async def _get_product(
        session: AsyncSession,
        product_id: UUID,
        for_update: bool = False,
        current_user: User | None = None,
    ) -> Product:
        query = select(Product).where(Product.id == product_id)
        if for_update:
            query = query.with_for_update()
        result = await session.execute(query)
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError
        if current_user:
            check_ownership(current_user, product)
        return product

    @staticmethod
    async def change_status(
        session: AsyncSession, product_id: UUID, status: ProductStatus
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True
        )
        product.status = status
        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def create_product(
        session: AsyncSession, owner_id: UUID, product_data: ProductCreate
    ) -> Product:
        new_product = Product(**product_data.model_dump())
        new_product.owner_id = owner_id
        session.add(new_product)
        await session.commit()
        await session.refresh(new_product)
        return new_product

    @staticmethod
    async def update_product(
        session: AsyncSession,
        product_id: UUID,
        product_data: ProductUpdate,
        current_user: User,
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True, current_user=current_user
        )
        for field, value in product_data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def delete_product(
        session: AsyncSession,
        product_id: UUID,
        current_user: User,
    ) -> None:
        product = await InventoryService._get_product(
            session, product_id, for_update=True, current_user=current_user
        )
        await session.delete(product)
        await session.commit()

    @staticmethod
    async def get_product(session: AsyncSession, product_id: UUID) -> Product:
        product = await InventoryService._get_product(session, product_id)
        return product

    @staticmethod
    async def get_products(
        session: AsyncSession,
        status: ProductStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        query = select(Product)
        if status:
            query = query.where(Product.status == status)
        result = await session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
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
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.reserve_timeout_minutes
        )
        new_reservation = Reservation(
            qty_reserved=reservation_data.quantity,
            user_id=user_id,
            product_id=reservation_data.product_id,
            status=OrderStatus.PENDING,
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
