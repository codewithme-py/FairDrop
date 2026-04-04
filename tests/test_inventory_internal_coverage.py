from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.inventory.internal import (
    cancel_reservation_and_return_stock,
    cancel_reservation_by_order_and_return_stock,
    ensure_product_exists,
    mark_reservation_as_completed,
    mark_reservation_by_order_as_completed,
)
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import Order, OrderStatus
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_user(db_session: Any) -> Any:
    user = User(
        id=uuid4(),
        email=f'test_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.SELLER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_product(db_session: Any, sample_user: Any) -> Any:
    product = Product(
        name='Test Product',
        price=Decimal('10.00'),
        qty_available=100,
        owner_id=sample_user.id,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def sample_order(db_session: Any, sample_user: Any) -> Any:
    order = Order(
        id=uuid4(),
        user_id=sample_user.id,
        status=OrderStatus.PENDING,
        total_amount=Decimal('50.00'),
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest.fixture
async def sample_reservation(
    db_session: Any, sample_product: Any, sample_user: Any
) -> Any:
    res = Reservation(
        id=uuid4(),
        product_id=sample_product.id,
        user_id=sample_user.id,
        order_id=None,
        qty_reserved=5,
        status='PENDING',
        idempotency_key=str(uuid4()),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db_session.add(res)
    await db_session.commit()
    await db_session.refresh(res)
    return res


@pytest.fixture
async def reservation_with_order(
    db_session: Any, sample_product: Any, sample_user: Any, sample_order: Any
) -> Any:
    res = Reservation(
        id=uuid4(),
        product_id=sample_product.id,
        user_id=sample_user.id,
        order_id=sample_order.id,
        qty_reserved=5,
        status='PENDING',
        idempotency_key=str(uuid4()),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db_session.add(res)
    await db_session.commit()
    await db_session.refresh(res)
    return res


@pytest.mark.asyncio
async def test_mark_reservation_as_completed_success(
    db_session: Any, sample_reservation: Any
) -> None:
    await mark_reservation_as_completed(db_session, sample_reservation.id)
    await db_session.commit()
    await db_session.refresh(sample_reservation)
    assert sample_reservation.status == OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_mark_reservation_as_completed_not_found(db_session: Any) -> None:
    with pytest.raises(NotFoundError):
        await mark_reservation_as_completed(db_session, uuid4())


@pytest.mark.asyncio
async def test_mark_reservation_by_order_as_completed_success(
    db_session: Any, reservation_with_order: Any
) -> None:
    await mark_reservation_by_order_as_completed(
        db_session, reservation_with_order.order_id
    )
    await db_session.commit()
    await db_session.refresh(reservation_with_order)
    assert reservation_with_order.status == OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_mark_reservation_by_order_as_completed_not_found(
    db_session: Any,
) -> None:
    with pytest.raises(NotFoundError):
        await mark_reservation_by_order_as_completed(db_session, uuid4())


@pytest.mark.asyncio
async def test_cancel_reservation_and_return_stock_success(
    db_session: Any, sample_reservation: Any, sample_product: Any
) -> None:
    initial_qty = sample_product.qty_available
    await cancel_reservation_and_return_stock(db_session, sample_reservation.id)
    await db_session.commit()
    await db_session.refresh(sample_reservation)
    await db_session.refresh(sample_product)

    assert sample_reservation.status == OrderStatus.CANCELLED
    assert sample_product.qty_available == initial_qty + sample_reservation.qty_reserved


@pytest.mark.asyncio
async def test_cancel_reservation_and_return_stock_not_found(db_session: Any) -> None:
    with pytest.raises(NotFoundError):
        await cancel_reservation_and_return_stock(db_session, uuid4())


@pytest.mark.asyncio
async def test_cancel_reservation_by_order_and_return_stock_success(
    db_session: Any, reservation_with_order: Any, sample_product: Any
) -> None:
    initial_qty = sample_product.qty_available
    await cancel_reservation_by_order_and_return_stock(
        db_session, reservation_with_order.order_id
    )
    await db_session.commit()
    await db_session.refresh(reservation_with_order)
    await db_session.refresh(sample_product)

    assert reservation_with_order.status == OrderStatus.CANCELLED
    expected_qty = initial_qty + reservation_with_order.qty_reserved
    assert sample_product.qty_available == expected_qty


@pytest.mark.asyncio
async def test_cancel_reservation_by_order_and_return_stock_not_found(
    db_session: Any,
) -> None:
    with pytest.raises(NotFoundError):
        await cancel_reservation_by_order_and_return_stock(db_session, uuid4())


@pytest.mark.asyncio
async def test_ensure_product_exists_success(
    db_session: Any, sample_product: Any
) -> None:
    await ensure_product_exists(db_session, sample_product.id)


@pytest.mark.asyncio
async def test_ensure_product_exists_not_found(db_session: Any) -> None:
    with pytest.raises(NotFoundError):
        await ensure_product_exists(db_session, uuid4())
