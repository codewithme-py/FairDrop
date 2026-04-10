import asyncio
import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.services.inventory.models import Product, Reservation
from app.services.inventory.schemas import ProductCreate
from app.services.inventory.service import InventoryService
from app.services.inventory.tasks import release_expired_reservations
from app.services.orders.models import OrderStatus
from app.services.user.models import User


async def test_arq_concurrent_expiry_no_double_return(
    db_engine: AsyncEngine, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Verify concurrent ARQ expiry workers do not double-return inventory stock."""
    async with db_session_factory() as clean_up_session:
        await clean_up_session.execute(
            delete(Reservation).where(Reservation.status == OrderStatus.PENDING)
        )
        await clean_up_session.commit()
    async with db_session_factory() as setup_session:
        user = User(id=uuid4(), email=f'test_{uuid4()}@mail.com', password_hash='foo')
        setup_session.add(user)
        await setup_session.commit()
        product_data = ProductCreate(
            name='Test Plate carrier', price=Decimal('100.00'), qty_available=0
        )
        product = await InventoryService.create_product(
            setup_session, user.id, product_data, current_user=user
        )
        for _ in range(10):
            reservation = Reservation(
                qty_reserved=1,
                status=OrderStatus.PENDING,
                idempotency_key=str(uuid4()),
                expires_at=datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(minutes=60),
                user_id=user.id,
                product_id=product.id,
            )
            setup_session.add(reservation)
        product_id = product.id
        await setup_session.commit()
    worker_session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=True,
    )
    ctx = {'session_maker': worker_session_factory}
    await asyncio.gather(
        release_expired_reservations(ctx),
        release_expired_reservations(ctx),
    )
    async with db_session_factory() as session:
        reservations = await session.execute(
            select(Product.qty_available).where(Product.id == product_id)
        )
        assert reservations.scalar_one() == 10
        reservations = await session.execute(
            select(Reservation.status).where(Reservation.product_id == product_id)
        )
        statuses = reservations.scalars().all()
        assert all(s == OrderStatus.EXPIRED for s in statuses)
