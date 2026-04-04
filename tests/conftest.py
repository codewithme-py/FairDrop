import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base
from app.core.security import create_access_token
from app.main import app as main_app
from app.services.user.models import User, UserRole


def _test_db_url() -> str:
    """
    Build test DB URL with DB_HOST override.
    settings.database_url may contain docker container name (db_fairdrop).
    Tests run locally or in CI where postgres is on localhost.
    """
    host = os.environ.get('DB_HOST', 'localhost')
    return (
        f'postgresql+asyncpg://{settings.db_user}:{settings.db_password}'
        f'@{host}:{settings.db_port}/{settings.db_name}'
    )


@pytest_asyncio.fixture
async def db_engine() -> Any:
    engine = create_async_engine(_test_db_url(), echo=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine: AsyncEngine) -> Any:
    return async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> Any:
    async with db_session_factory() as session:
        yield session


def _test_redis_url() -> str:
    host = os.environ.get('REDIS_HOST', 'localhost')
    return f'redis://{host}:{settings.redis_port}'


@pytest_asyncio.fixture
async def redis_client() -> Any:
    redis = Redis.from_url(_test_redis_url(), decode_responses=True)
    await redis.flushdb()
    yield redis
    await redis.flushdb()
    await redis.aclose()


@pytest_asyncio.fixture
async def create_test_user(db_session: AsyncSession) -> Any:
    async def _create(
        role: UserRole = UserRole.USER, is_verified: bool = True, email_prefix: str = ''
    ) -> User:
        prefix = email_prefix or role.lower()
        user = User(
            email=f'{prefix}_{uuid4().hex[:8]}@example.com',
            password_hash='...',
            role=role,
            is_verified=is_verified,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create


@pytest_asyncio.fixture
async def create_auth_headers(create_test_user: Callable[..., Awaitable[User]]) -> Any:
    async def _create(
        role: UserRole = UserRole.USER, is_verified: bool = True, email_prefix: str = ''
    ) -> dict[str, str]:
        user = await create_test_user(
            role=role, is_verified=is_verified, email_prefix=email_prefix
        )
        token = create_access_token({'sub': user.email, 'role': user.role})
        return {'Authorization': f'Bearer {token}'}

    return _create


@pytest_asyncio.fixture
async def admin_headers(
    create_auth_headers: Callable[..., Awaitable[dict[str, str]]],
) -> Any:
    return await create_auth_headers(UserRole.ADMIN, email_prefix='admin')


@pytest_asyncio.fixture
async def seller_headers(
    create_auth_headers: Callable[..., Awaitable[dict[str, str]]],
) -> Any:
    return await create_auth_headers(UserRole.SELLER, email_prefix='seller')


@pytest_asyncio.fixture
async def unverified_seller_headers(
    create_auth_headers: Callable[..., Awaitable[dict[str, str]]],
) -> Any:
    return await create_auth_headers(
        UserRole.SELLER, is_verified=False, email_prefix='unverified'
    )


@pytest_asyncio.fixture
async def buyer_headers(
    create_auth_headers: Callable[..., Awaitable[dict[str, str]]],
) -> Any:
    return await create_auth_headers(UserRole.USER, email_prefix='buyer')


@pytest_asyncio.fixture
async def b2b_user_headers(
    create_auth_headers: Callable[..., Awaitable[dict[str, str]]],
) -> Any:
    return await create_auth_headers(UserRole.USER_B2B, email_prefix='b2b')


@pytest_asyncio.fixture
async def create_test_product(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Any]]:
    from app.services.inventory.models import Product, ProductStatus

    async def _create(
        owner_id: Any,
        name: str = 'Test Product',
        price: str = '10.00',
        qty_available: int = 10,
        status: Any = ProductStatus.ACTIVE,
    ) -> Product:
        product = Product(
            owner_id=owner_id,
            name=name,
            description='Test Desc',
            price=Decimal(price),
            qty_available=qty_available,
            status=status,
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)
        return product

    return _create


@pytest_asyncio.fixture
async def create_test_order(db_session: AsyncSession) -> Callable[..., Awaitable[Any]]:
    from app.services.orders.models import Order, OrderStatus

    async def _create(
        user_id: Any,
        status: OrderStatus = OrderStatus.PENDING,
        total_amount: str = '0.00',
    ) -> Order:
        order = Order(
            id=uuid4(),
            user_id=user_id,
            status=status,
            total_amount=Decimal(total_amount),
        )
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        return order

    return _create


@pytest_asyncio.fixture
async def create_test_inventory(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Any]]:
    from app.services.inventory.models import Product

    async def _create(product_id: Any, qty: int = 100) -> Product:
        # Since Inventory was likely replaced by Product.qty_available,
        # we update the product
        result = await db_session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if product:
            product.qty_available = qty
            await db_session.commit()
            await db_session.refresh(product)
            return product
        raise ValueError(f'Product {product_id} not found')

    return _create


@pytest_asyncio.fixture
async def async_client(
    db_session_factory: async_sessionmaker[AsyncSession], redis_client: Redis
) -> AsyncGenerator[AsyncClient, None]:
    from app.core.database import get_session
    from app.core.lua_scripts import RATE_LIMIT_LUA_SCRIPT

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

    main_app.dependency_overrides[get_session] = override_get_session
    main_app.state.redis = redis_client
    main_app.state.rate_limit_script = redis_client.register_script(
        RATE_LIMIT_LUA_SCRIPT
    )
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        yield client
