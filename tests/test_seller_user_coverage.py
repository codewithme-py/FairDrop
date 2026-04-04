from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import ProductStatus
from app.services.orders.models import OrderItem, OrderStatus
from app.services.seller_user.service import (
    get_my_orders,
    get_my_products,
    get_my_stats,
)
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_seller(create_test_user: Any) -> Any:
    return await create_test_user(UserRole.SELLER)


@pytest.mark.asyncio
async def test_seller_get_my_products(
    db_session: AsyncSession, sample_seller: User, create_test_product: Any
) -> None:
    await create_test_product(
        owner_id=sample_seller.id,
        name='P1',
        price='10',
        qty_available=10,
        status=ProductStatus.ACTIVE,
    )
    await create_test_product(
        owner_id=sample_seller.id,
        name='P2',
        price='20',
        qty_available=5,
        status=ProductStatus.REJECTED,
    )

    all_prods = await get_my_products(db_session, sample_seller.id)
    assert len(all_prods) >= 2

    # Filtered
    active_prods = await get_my_products(
        db_session, sample_seller.id, status=ProductStatus.ACTIVE
    )
    assert len(active_prods) >= 1
    assert all(p.status == ProductStatus.ACTIVE for p in active_prods)


@pytest.mark.asyncio
async def test_seller_get_my_orders(
    db_session: AsyncSession,
    sample_seller: User,
    create_test_product: Any,
    create_test_order: Any,
) -> None:
    p = await create_test_product(
        owner_id=sample_seller.id,
        name='P1',
        price='10',
        qty_available=10,
        status=ProductStatus.ACTIVE,
    )

    # Empty
    empty_orders = await get_my_orders(db_session, sample_seller.id)
    assert empty_orders == []

    # With order
    order = await create_test_order(
        user_id=sample_seller.id, status=OrderStatus.PAID, total_amount='50'
    )
    order.shipping_address = 'Moscow'
    item = OrderItem(
        id=uuid4(),
        order_id=order.id,
        product_id=p.id,
        product_name='P1',
        quantity=1,
        price=Decimal('10'),
    )
    db_session.add(item)
    db_session.add(order)
    await db_session.commit()

    orders = await get_my_orders(db_session, sample_seller.id)
    assert len(orders) >= 1
    assert orders[0].shipping_address == 'Moscow'
    assert len(orders[0].seller_items) == 1

    orders_filtered = await get_my_orders(
        db_session, sample_seller.id, status=OrderStatus.PENDING
    )
    assert len(orders_filtered) == 0


@pytest.mark.asyncio
async def test_seller_get_my_orders_hidden_address(
    db_session: AsyncSession,
    sample_seller: User,
    create_test_product: Any,
    create_test_order: Any,
) -> None:
    p = await create_test_product(
        owner_id=sample_seller.id,
        name='P2',
        price='10',
        qty_available=10,
        status=ProductStatus.ACTIVE,
    )

    order = await create_test_order(
        user_id=sample_seller.id, status=OrderStatus.PENDING, total_amount='50'
    )
    order.shipping_address = 'Secret'
    item = OrderItem(
        id=uuid4(),
        order_id=order.id,
        product_id=p.id,
        product_name='P2',
        quantity=1,
        price=Decimal('10'),
    )
    db_session.add(item)
    db_session.add(order)
    await db_session.commit()

    orders = await get_my_orders(db_session, sample_seller.id)
    found = next(o for o in orders if o.id == order.id)
    assert found.shipping_address is None


@pytest.mark.asyncio
async def test_seller_get_my_stats(
    db_session: AsyncSession,
    sample_seller: User,
    create_test_product: Any,
    create_test_order: Any,
) -> None:
    p = await create_test_product(
        owner_id=sample_seller.id,
        name='P3',
        price='10',
        qty_available=10,
        status=ProductStatus.ACTIVE,
    )
    order = await create_test_order(
        user_id=sample_seller.id, status=OrderStatus.PAID, total_amount='50'
    )
    item = OrderItem(
        id=uuid4(),
        order_id=order.id,
        product_id=p.id,
        product_name='P3',
        quantity=1,
        price=Decimal('10'),
    )
    db_session.add(item)
    db_session.add(order)
    await db_session.commit()

    stats = await get_my_stats(db_session, sample_seller.id)
    assert stats.active_products >= 1
    assert stats.paid_orders >= 1
