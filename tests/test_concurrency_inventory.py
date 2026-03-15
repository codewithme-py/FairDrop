import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import InsufficientInventoryError
from app.services.inventory.models import Product
from app.services.inventory.schemas import ProductCreate, ReservationCreate
from app.services.inventory.service import InventoryService
from app.services.orders.models import Order  # noqa: F401
from app.services.user.models import User


@pytest.mark.asyncio
async def test_concurrent_reservations_service_level(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as setup_session:
        user = User(id=uuid4(), email=f'test_{uuid4()}@mail.com', password_hash='foo')
        setup_session.add(user)
        await setup_session.commit()
        product_data = ProductCreate(
            name='Test Sneakers', price=Decimal('100.00'), qty_available=10
        )
        product = await InventoryService.create_product(
            setup_session, user.id, product_data
        )
        product_id = product.id
        user_id = user.id
    concurrency_level = 50

    async def worker() -> bool | Exception:
        async with db_session_factory() as session:
            request = ReservationCreate(product_id=product_id, quantity=1)
            idempotency_key = str(uuid4())
            try:
                await InventoryService.reserve_items(
                    session, user_id, idempotency_key, request
                )
                return True
            except InsufficientInventoryError:
                return False
            except Exception as e:
                return e

    start_workers = await asyncio.gather(*(worker() for _ in range(concurrency_level)))
    success_count = sum(1 for r in start_workers if r is True)
    fail_count = sum(1 for r in start_workers if r is False)
    error_count = sum(1 for r in start_workers if isinstance(r, Exception))
    assert success_count == 10
    assert fail_count == 40
    assert error_count == 0
    async with db_session_factory() as session:
        final_product = await session.get(Product, product_id)
        assert final_product is not None
        assert final_product.qty_available == 0
