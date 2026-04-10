from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.orders.internal import cancel_order_by_system
from app.services.orders.models import Order, OrderStatus
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_user(db_session: Any) -> Any:
    """Create a sample user for orders internal tests."""
    user = User(
        id=uuid4(),
        email=f'test_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_order(db_session: Any, sample_user: Any) -> Any:
    """Create a sample pending order for orders internal tests."""
    order = Order(
        id=uuid4(),
        user_id=sample_user.id,
        status=OrderStatus.PENDING,
        total_amount=Decimal('100.00'),
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_cancel_order_by_system_success(
    db_session: Any, sample_order: Any
) -> None:
    """Verify cancel_order_by_system sets order status to CANCELLED."""
    await cancel_order_by_system(db_session, sample_order.id)
    await db_session.commit()
    await db_session.refresh(sample_order)
    assert sample_order.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_order_by_system_not_found(db_session: Any) -> None:
    """Verify cancel_order_by_system raises NotFoundError for a nonexistent order."""
    with pytest.raises(NotFoundError):
        await cancel_order_by_system(db_session, uuid4())
