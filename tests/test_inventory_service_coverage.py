from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services.inventory.models import Product, ProductStatus
from app.services.inventory.schemas import ReservationCreate
from app.services.inventory.service import InventoryAdminService, InventoryService
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_seller(db_session: Any) -> Any:
    u = User(
        id=uuid4(),
        email=f'seller_{uuid4().hex[:4]}@mail.com',
        password_hash='h',
        role=UserRole.SELLER,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def sample_moderator(db_session: Any) -> Any:
    u = User(
        id=uuid4(),
        email=f'mod_{uuid4().hex[:4]}@mail.com',
        password_hash='h',
        role=UserRole.MODERATOR,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def sample_product(db_session: Any, sample_seller: Any) -> Any:
    p = Product(
        id=uuid4(),
        owner_id=sample_seller.id,
        name='Test P',
        price=Decimal('10.00'),
        qty_available=10,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def draft_product(db_session: Any, sample_seller: Any) -> Any:
    p = Product(
        id=uuid4(),
        owner_id=sample_seller.id,
        name='Test DRAFT',
        price=Decimal('10.00'),
        qty_available=10,
        status=ProductStatus.DRAFT,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.mark.asyncio
async def test_submit_for_moderation_conflict(
    db_session: Any, sample_product: Any, sample_seller: Any
) -> None:
    # product is ACTIVE, not DRAFT/REJECTED
    with pytest.raises(ConflictError):
        await InventoryService.submit_for_moderation(
            db_session, sample_product.id, sample_seller
        )


@pytest.mark.asyncio
async def test_reserve_items_product_not_found(
    db_session: Any, sample_seller: Any
) -> None:
    res_data = ReservationCreate(product_id=uuid4(), quantity=1)
    with pytest.raises(NotFoundError):
        await InventoryService.reserve_items(
            db_session, sample_seller.id, 'some-key', res_data
        )


@pytest.mark.asyncio
async def test_claim_for_moderation_conflict(
    db_session: Any, sample_product: Any, sample_moderator: Any
) -> None:
    # product is ACTIVE, not PENDING_MODERATION
    with pytest.raises(ConflictError):
        await InventoryAdminService.claim_for_moderation(
            db_session, sample_product.id, sample_moderator
        )


@pytest.mark.asyncio
async def test_approve_product_conflict(
    db_session: Any, draft_product: Any, sample_moderator: Any
) -> None:
    # product is DRAFT, not MODERATION_IN_PROGRESS
    with pytest.raises(ConflictError):
        await InventoryAdminService.approve_product(
            db_session, draft_product.id, sample_moderator
        )


@pytest.mark.asyncio
async def test_reject_product_conflict(
    db_session: Any, draft_product: Any, sample_moderator: Any
) -> None:
    # product is DRAFT, not MODERATION_IN_PROGRESS
    with pytest.raises(ConflictError):
        await InventoryAdminService.reject_product(
            db_session, draft_product.id, sample_moderator, 'bad product'
        )
