from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    url=str(settings.database_url),
    echo=settings.debug_mode,
    future=True,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
)

async_session_factory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session as a FastAPI dependency.

    Yields:
        An async SQLAlchemy session that is automatically closed after use.
    """
    async with async_session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
