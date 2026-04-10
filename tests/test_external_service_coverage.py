from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.services.external.service import (
    get_external_catalog,
    get_external_order_status,
)
from app.services.inventory.models import Product, ProductStatus
from app.services.orders.models import Order, OrderStatus
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_user(db_session: Any) -> Any:
    """Create a sample user for external service tests."""
    user = User(
        id=uuid4(),
        email=f'external_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def active_product(db_session: Any, sample_user: Any) -> Any:
    """Create an active product associated with the sample user."""
    product = Product(
        id=uuid4(),
        name='External Product',
        price=Decimal('50.00'),
        qty_available=100,
        owner_id=sample_user.id,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_get_external_catalog_success(
    db_session: Any, active_product: Any
) -> None:
    """Verify get_external_catalog includes the active test product."""
    catalog = await get_external_catalog(db_session)
    assert len(catalog) >= 1
    assert any(p.id == active_product.id for p in catalog)


@pytest.mark.asyncio
async def test_get_external_order_status_cycle(
    db_session: Any, sample_user: Any
) -> None:
    """Verify get_external_order_status finds owned orders, rejects others."""
    order = Order(
        id=uuid4(),
        user_id=sample_user.id,
        status=OrderStatus.PAID,
        total_amount=Decimal('100.00'),
    )
    db_session.add(order)
    await db_session.commit()
    res = await get_external_order_status(db_session, sample_user.id, order.id)
    assert res is not None
    assert res.id == order.id
    res_none = await get_external_order_status(db_session, sample_user.id, uuid4())
    assert res_none is None
    res_wrong_user = await get_external_order_status(db_session, uuid4(), order.id)
    assert res_wrong_user is None
