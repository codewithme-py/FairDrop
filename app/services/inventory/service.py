from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.audit_log.service import audit_log_service
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    InsufficientInventoryError,
    NotFoundError,
    SellerLimitExceededError,
)
from app.core.security import check_ownership
from app.services.inventory.models import Product, ProductStatus, Reservation
from app.services.inventory.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ReservationCreate,
)
from app.services.orders.models import OrderStatus
from app.services.user.models import User, UserRole


class InventoryService:
    @staticmethod
    async def _check_seller_limit(session: AsyncSession, user: User) -> None:
        """Check if the user has exceeded their product listing limit."""
        if user.role in (UserRole.ADMIN, UserRole.MODERATOR):
            return
        query = select(Product).where(Product.owner_id == user.id)
        result = await session.execute(query)
        product_count = len(result.scalars().all())
        limit = settings.unverified_seller_limit
        if user.role in (UserRole.SELLER, UserRole.SELLER_B2B) and user.is_verified:
            limit = settings.verified_seller_limit
        if product_count >= limit:
            raise SellerLimitExceededError(
                f'Limit of {limit} products reached for your account type'
            )

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
        else:
            query = query.options(joinedload(Product.images))
        result = await session.execute(query)
        product = result.unique().scalar_one_or_none()
        if not product:
            raise NotFoundError
        if current_user:
            check_ownership(current_user, product)
        return product

    @staticmethod
    async def _log_product_change(
        session: AsyncSession,
        user: User,
        product: Product,
        old_snapshot: ProductRead | None,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await audit_log_service.log_object_change(
            session=session,
            actor_id=user.id,
            target_id=product.id,
            target_type='product',
            action=action,
            old_obj=old_snapshot,
            new_obj=ProductRead.model_validate(product),
            extra_data=metadata,
        )

    @staticmethod
    async def submit_for_moderation(
        session: AsyncSession, product_id: UUID, current_user: User
    ) -> Product:
        product_under_moderation = await InventoryService._get_product(
            session, product_id, for_update=True, current_user=current_user
        )
        if product_under_moderation.status not in (
            ProductStatus.DRAFT,
            ProductStatus.REJECTED,
        ):
            raise ConflictError
        product_under_moderation_snapshot = ProductRead.model_validate(
            product_under_moderation
        )
        product_under_moderation.status = ProductStatus.PENDING_MODERATION
        product_under_moderation.moderator_id = None
        await InventoryService._log_product_change(
            session=session,
            user=current_user,
            product=product_under_moderation,
            old_snapshot=product_under_moderation_snapshot,
            action='submit_for_moderation',
        )
        await session.commit()
        await session.refresh(product_under_moderation)
        return product_under_moderation

    @staticmethod
    async def create_product(
        session: AsyncSession,
        owner_id: UUID,
        product_data: ProductCreate,
        current_user: User,
    ) -> Product:
        await InventoryService._check_seller_limit(session, current_user)
        new_product = Product(**product_data.model_dump())
        new_product.owner_id = owner_id
        session.add(new_product)
        await session.flush()
        await InventoryService._log_product_change(
            session=session,
            user=current_user,
            product=new_product,
            old_snapshot=None,
            action='create',
        )
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
        if product.status in (
            ProductStatus.PENDING_MODERATION,
            ProductStatus.MODERATION_IN_PROGRESS,
        ):
            raise ConflictError('Cannot edit product while it is under moderation')
        old_snapshot = ProductRead.model_validate(product)
        for field, value in product_data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        if product.status == ProductStatus.ACTIVE:
            product.status = ProductStatus.PENDING_MODERATION
            product.moderator_id = None
        await InventoryService._log_product_change(
            session=session,
            user=current_user,
            product=product,
            old_snapshot=old_snapshot,
            action='update',
        )
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
        await InventoryService._log_product_change(
            session=session,
            user=current_user,
            product=product,
            old_snapshot=ProductRead.model_validate(product),
            action='delete',
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
        query = select(Product).options(joinedload(Product.images))
        if status:
            query = query.where(Product.status == status)
        result = await session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().unique().all())

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


class InventoryAdminService(InventoryService):
    @staticmethod
    async def change_status(
        session: AsyncSession,
        product_id: UUID,
        status: ProductStatus,
        current_user: User,
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True
        )
        old_snapshot = ProductRead.model_validate(product)
        product.status = status
        await InventoryService._log_product_change(
            session=session,
            user=current_user,
            product=product,
            old_snapshot=old_snapshot,
            action='update',
        )
        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def claim_for_moderation(
        session: AsyncSession, product_id: UUID, moderator_user: User
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True
        )
        if product.status != ProductStatus.PENDING_MODERATION:
            raise ConflictError
        old_snapshot = ProductRead.model_validate(product)
        product.status = ProductStatus.MODERATION_IN_PROGRESS
        product.moderator_id = moderator_user.id
        await InventoryService._log_product_change(
            session=session,
            user=moderator_user,
            product=product,
            old_snapshot=old_snapshot,
            action='claim_for_moderation',
        )
        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def approve_product(
        session: AsyncSession, product_id: UUID, moderator_user: User
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True
        )
        if product.status != ProductStatus.MODERATION_IN_PROGRESS:
            raise ConflictError
        old_snapshot = ProductRead.model_validate(product)
        product.status = ProductStatus.ACTIVE
        product.moderator_id = None
        await InventoryService._log_product_change(
            session=session,
            user=moderator_user,
            product=product,
            old_snapshot=old_snapshot,
            action='approve',
        )
        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def reject_product(
        session: AsyncSession,
        product_id: UUID,
        moderator_user: User,
        reason: str,
    ) -> Product:
        product = await InventoryService._get_product(
            session, product_id, for_update=True
        )
        if product.status != ProductStatus.MODERATION_IN_PROGRESS:
            raise ConflictError
        old_snapshot = ProductRead.model_validate(product)
        product.status = ProductStatus.REJECTED
        product.moderator_id = None
        await InventoryService._log_product_change(
            session=session,
            user=moderator_user,
            product=product,
            old_snapshot=old_snapshot,
            action='reject',
            metadata={'reason': reason},
        )
        await session.commit()
        await session.refresh(product)
        return product
