from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.services.inventory.models import Product, ProductStatus
from app.services.orders.models import Order, OrderItem, OrderStatus
from app.services.seller_user.service import (
    get_my_orders,
    get_my_products,
    get_my_stats,
)
from app.services.user.models import User, UserRole


@pytest.fixture
async def seller_user(db_session: Any) -> Any:
    """Create a seller user for seller service coverage tests."""
    user = User(
        id=uuid4(),
        email=f'seller_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.SELLER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def buyer_user(db_session: Any) -> Any:
    """Create a buyer user for seller service coverage tests."""
    user = User(
        id=uuid4(),
        email=f'buyer_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def seller_product(db_session: Any, seller_user: Any) -> Any:
    """Create an active product owned by the seller user."""
    product = Product(
        id=uuid4(),
        name='Seller Product',
        price=Decimal('50.00'),
        qty_available=100,
        owner_id=seller_user.id,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_get_my_products_basic(
    db_session: Any, seller_user: Any, seller_product: Any
) -> None:
    """Verify get_my_products returns all, active-filtered, and empty results."""
    prods = await get_my_products(db_session, seller_user.id)
    assert len(prods) == 1
    assert prods[0].id == seller_product.id
    prods_active = await get_my_products(
        db_session, seller_user.id, status=ProductStatus.ACTIVE
    )
    assert len(prods_active) == 1
    prods_draft = await get_my_products(
        db_session, seller_user.id, status=ProductStatus.DRAFT
    )
    assert len(prods_draft) == 0


@pytest.mark.asyncio
async def test_get_my_orders_empty(db_session: Any, seller_user: Any) -> None:
    """Verify get_my_orders returns an empty list when the seller has no orders."""
    orders = await get_my_orders(db_session, seller_user.id)
    assert orders == []


@pytest.mark.asyncio
async def test_get_my_orders_full_cycle(
    db_session: Any, seller_user: Any, buyer_user: Any, seller_product: Any
) -> None:
    """Verify get_my_orders returns orders with address masking for pending."""
    order_pending = Order(
        id=uuid4(),
        user_id=buyer_user.id,
        status=OrderStatus.PENDING,
        total_amount=Decimal('50.00'),
        shipping_address='123 Secret St',
    )
    db_session.add(order_pending)
    item_pending = OrderItem(
        id=uuid4(),
        order_id=order_pending.id,
        product_id=seller_product.id,
        product_name=seller_product.name,
        quantity=1,
        price=seller_product.price,
    )
    db_session.add(item_pending)
    order_paid = Order(
        id=uuid4(),
        user_id=buyer_user.id,
        status=OrderStatus.PAID,
        total_amount=Decimal('50.00'),
        shipping_address='456 Public Rd',
    )
    db_session.add(order_paid)
    item_paid = OrderItem(
        id=uuid4(),
        order_id=order_paid.id,
        product_id=seller_product.id,
        product_name=seller_product.name,
        quantity=1,
        price=seller_product.price,
    )
    db_session.add(item_paid)
    await db_session.commit()
    all_orders = await get_my_orders(db_session, seller_user.id)
    assert len(all_orders) == 2
    paid_res = next(o for o in all_orders if o.status == OrderStatus.PAID)
    pending_res = next(o for o in all_orders if o.status == OrderStatus.PENDING)
    assert paid_res.shipping_address == '456 Public Rd'
    assert pending_res.shipping_address is None
    paid_only = await get_my_orders(db_session, seller_user.id, status=OrderStatus.PAID)
    assert len(paid_only) == 1
    assert paid_only[0].id == order_paid.id


@pytest.mark.asyncio
async def test_get_my_stats_comprehensive(
    db_session: Any, seller_user: Any, buyer_user: Any, seller_product: Any
) -> None:
    """Verify get_my_stats counts total/active products and paid/pending orders."""
    draft_prod = Product(
        id=uuid4(),
        name='Draft Product',
        price=Decimal('10.00'),
        qty_available=10,
        owner_id=seller_user.id,
        status=ProductStatus.DRAFT,
    )
    db_session.add(draft_prod)
    order = Order(
        id=uuid4(),
        user_id=buyer_user.id,
        status=OrderStatus.PAID,
        total_amount=Decimal('10.00'),
    )
    db_session.add(order)
    db_session.add(
        OrderItem(
            id=uuid4(),
            order_id=order.id,
            product_id=seller_product.id,
            product_name=seller_product.name,
            quantity=1,
            price=seller_product.price,
        )
    )
    await db_session.commit()
    stats = await get_my_stats(db_session, seller_user.id)
    assert stats.total_products == 2
    assert stats.active_products == 1
    assert stats.paid_orders == 1
    assert stats.pending_orders == 0
