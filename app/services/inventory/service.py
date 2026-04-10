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
    """
    Service class for product CRUD and reservation operations.

    All public methods are static and handle core inventory management
    including seller limits, moderation workflow, and stock reservation.
    """

    @staticmethod
    async def _check_seller_limit(session: AsyncSession, user: User) -> None:
        """
        Check if the user has exceeded their product listing limit.

        Args:
            session: Async database session.
            user: User whose limits should be checked.

        Raises:
            SellerLimitExceededError: If the user has reached their
                maximum product count.
        """
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
        """
        Fetch a product by ID with optional row locking and ownership check.

        Args:
            session: Async database session.
            product_id: ID of the product to fetch.
            for_update: If True, acquire a row-level lock for updates.
            current_user: Optional user for ownership verification.

        Returns:
            The Product instance.

        Raises:
            NotFoundError: If the product does not exist.
            PermissionDeniedError: If current_user does not own the product.
        """
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
        """
        Record an audit log entry for a product state change.

        Args:
            session: Async database session.
            user: User who performed the action.
            product: The modified product instance.
            old_snapshot: Product state before the change.
            action: Type of action (e.g., 'create', 'update', 'delete').
            metadata: Optional additional context data.
        """
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
        """
        Submit a product for admin moderation.

        Only products in DRAFT or REJECTED status can be submitted.

        Args:
            session: Async database session.
            product_id: ID of the product to submit.
            current_user: Authenticated user (must own the product).

        Returns:
            The product with status set to PENDING_MODERATION.

        Raises:
            ConflictError: If the product is not in DRAFT or REJECTED status.
        """
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
        """
        Create a new product for a seller after verifying listing limits.

        Args:
            session: Async database session.
            owner_id: ID of the product owner.
            product_data: Creation payload with name, price, etc.
            current_user: Authenticated seller user.

        Returns:
            The newly created product.

        Raises:
            SellerLimitExceededError: If the seller has reached their product limit.
        """
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
        """
        Update an existing product's attributes.

        Modifying an active product automatically sets it to PENDING_MODERATION.

        Args:
            session: Async database session.
            product_id: ID of the product to update.
            product_data: Partial payload with fields to update.
            current_user: Authenticated user (must own the product).

        Returns:
            The updated product.

        Raises:
            ConflictError: If the product is currently under moderation.
            NotFoundError: If the product does not exist.
            PermissionDeniedError: If the user does not own the product.
        """
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
        """
        Permanently delete a product.

        Args:
            session: Async database session.
            product_id: ID of the product to delete.
            current_user: Authenticated user (must own the product).

        Raises:
            NotFoundError: If the product does not exist.
            PermissionDeniedError: If the user does not own the product.
        """
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
        """
        Retrieve a single product by ID with images eagerly loaded.

        Args:
            session: Async database session.
            product_id: ID of the product to retrieve.

        Returns:
            The Product instance with images.

        Raises:
            NotFoundError: If the product does not exist.
        """
        product = await InventoryService._get_product(session, product_id)
        return product

    @staticmethod
    async def get_products(
        session: AsyncSession,
        status: ProductStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        """
        List products with optional status filter and pagination.

        Args:
            session: Async database session.
            status: Filter by product status; if None, returns all products.
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.

        Returns:
            List of products with images eagerly loaded.
        """
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
        """
        Reserve stock for a user against a specific product.

        Decrements available quantity and creates a Reservation record with
        an expiration time.

        Args:
            session: Async database session.
            user_id: ID of the reserving user.
            idempotency_key: Unique key to prevent duplicate reservations.
            reservation_data: Payload containing product_id and quantity.

        Returns:
            The newly created Reservation.

        Raises:
            NotFoundError: If the product does not exist.
            InsufficientInventoryError: If available stock is insufficient.
            ConflictError: If the idempotency key is already used.
        """
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
    """
    Extended inventory service with admin-level moderation operations.

    Inherits all base inventory operations and adds methods for the
    product moderation workflow (claim, approve, reject, status change).
    """

    @staticmethod
    async def change_status(
        session: AsyncSession,
        product_id: UUID,
        status: ProductStatus,
        current_user: User,
    ) -> Product:
        """
        Directly change a product's status (admin override).

        Args:
            session: Async database session.
            product_id: ID of the product to modify.
            status: New status to set.
            current_user: Admin user performing the action.

        Returns:
            The updated product.

        Raises:
            NotFoundError: If the product does not exist.
        """
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
        """
        Claim a product for moderation, assigning it to the current moderator.

        Args:
            session: Async database session.
            product_id: ID of the product to claim.
            moderator_user: Admin or moderator user claiming the product.

        Returns:
            The product with status MODERATION_IN_PROGRESS and moderator_id set.

        Raises:
            ConflictError: If the product is not in PENDING_MODERATION status.
        """
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
        """
        Approve a product under moderation, setting its status to ACTIVE.

        Args:
            session: Async database session.
            product_id: ID of the product to approve.
            moderator_user: Admin or moderator user approving the product.

        Returns:
            The product with status ACTIVE and moderator_id cleared.

        Raises:
            ConflictError: If the product is not in MODERATION_IN_PROGRESS status.
        """
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
        """
        Reject a product under moderation, providing a reason to the seller.

        Args:
            session: Async database session.
            product_id: ID of the product to reject.
            moderator_user: Admin or moderator user rejecting the product.
            reason: Explanation for the rejection.

        Returns:
            The product with status REJECTED and moderator_id cleared.

        Raises:
            ConflictError: If the product is not in MODERATION_IN_PROGRESS status.
        """
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
