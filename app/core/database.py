from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

POOL_SIZE = 10
MAX_OVERFLOW = 20

engine = create_async_engine(
    url=str(settings.database_url),
    echo=settings.debug_mode,
    future=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
)

async_session_factory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
