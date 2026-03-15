import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.services.inventory.models  # noqa: F401
import app.services.orders.models  # noqa: F401
import app.services.user.models  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.main import app as main_app


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
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(_test_db_url(), echo=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


def _test_redis_url() -> str:
    host = os.environ.get('REDIS_HOST', 'localhost')
    return f'redis://{host}:{settings.redis_port}'


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url(_test_redis_url(), decode_responses=True)
    await redis.flushdb()
    yield redis
    await redis.flushdb()
    await redis.aclose()


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
