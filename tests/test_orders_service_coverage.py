from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services.inventory.models import Reservation
from app.services.orders.models import OrderStatus
from app.services.orders.schemas import OrderCreate
from app.services.orders.service import OrderService
from app.services.user.models import UserRole


@pytest.fixture
async def sample_buyer(create_test_user: Any) -> Any:
    return await create_test_user(UserRole.USER)


@pytest.fixture
async def sample_product(sample_buyer: Any, create_test_product: Any) -> Any:
    return await create_test_product(
        owner_id=sample_buyer.id,
        name='Test',
        price='10',
        qty_available=10,
        status='ACTIVE',
    )


@pytest.mark.asyncio
async def test_get_order_not_found(db_session: Any, sample_buyer: Any) -> None:
    with pytest.raises(NotFoundError):
        await OrderService._get_order(db_session, uuid4(), sample_buyer)


@pytest.mark.asyncio
async def test_create_order_expired_reservation(
    db_session: Any, sample_buyer: Any, sample_product: Any
) -> None:
    res = Reservation(
        id=uuid4(),
        product_id=sample_product.id,
        user_id=sample_buyer.id,
        qty_reserved=1,
        status='PENDING',
        idempotency_key=str(uuid4()),
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
    )
    db_session.add(res)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await OrderService.create_order_from_reservation(
            db_session, sample_buyer, OrderCreate(reservation_id=res.id)
        )


@pytest.mark.asyncio
async def test_create_order_already_ordered_reservation(
    db_session: Any, sample_buyer: Any, sample_product: Any, create_test_order: Any
) -> None:
    order = await create_test_order(
        user_id=sample_buyer.id, status=OrderStatus.PENDING, total_amount='50'
    )

    res = Reservation(
        id=uuid4(),
        product_id=sample_product.id,
        user_id=sample_buyer.id,
        order_id=order.id,
        qty_reserved=1,
        status='PENDING',
        idempotency_key=str(uuid4()),
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15),
    )
    db_session.add(res)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await OrderService.create_order_from_reservation(
            db_session, sample_buyer, OrderCreate(reservation_id=res.id)
        )


@pytest.mark.asyncio
async def test_create_order_product_not_found(
    db_session: Any, sample_buyer: Any, sample_product: Any
) -> None:
    res = Reservation(
        id=uuid4(),
        product_id=sample_product.id,
        user_id=sample_buyer.id,
        qty_reserved=1,
        status='PENDING',
        idempotency_key=str(uuid4()),
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15),
    )
    db_session.add(res)
    await db_session.commit()

    # Mock db_session.execute to return None on the second call (when querying Product)
    from unittest.mock import patch

    class MockResult:
        def scalar_one_or_none(self) -> Any:
            return None

    original_execute = db_session.execute

    call_count = 0

    async def mock_execute(stmt: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return MockResult()
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db_session, 'execute', new=mock_execute):
        with pytest.raises(NotFoundError):
            await OrderService.create_order_from_reservation(
                db_session, sample_buyer, OrderCreate(reservation_id=res.id)
            )


@pytest.mark.asyncio
async def test_confirm_order_payment_conflict(
    db_session: Any, sample_buyer: Any, create_test_order: Any
) -> None:
    order = await create_test_order(
        user_id=sample_buyer.id, status=OrderStatus.PAID, total_amount='50'
    )

    with pytest.raises(ConflictError):
        await OrderService.confirm_order_payment(db_session, order.id, sample_buyer)


@pytest.mark.asyncio
async def test_cancel_order_conflict(
    db_session: Any, sample_buyer: Any, create_test_order: Any
) -> None:
    order = await create_test_order(
        user_id=sample_buyer.id, status=OrderStatus.CANCELLED, total_amount='50'
    )

    with pytest.raises(ConflictError):
        await OrderService.cancel_order(db_session, order.id, sample_buyer)
