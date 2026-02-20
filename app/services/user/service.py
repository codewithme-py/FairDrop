import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.exceptions import CredentialsError, UserAlreadyExists
from app.core.security import get_password_hash, verify_password
from app.services.user.models import RefreshToken, User
from app.services.user.schemas import UserCreate

URLSAFE_PARAM = 32


class UserService:
    @staticmethod
    async def create_user(session: AsyncSession, user_create: UserCreate) -> User:
        result = await session.execute(
            select(User).where(User.email == user_create.email)
        )
        if result.scalar_one_or_none():
            raise UserAlreadyExists
        hashed_password = get_password_hash(user_create.password)
        user = User(email=user_create.email, password_hash=hashed_password)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def authenticate_user(
        session: AsyncSession, email: str, password: str
    ) -> User | None:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def create_refresh_token(session: AsyncSession, user_id: UUID) -> str:
        token = secrets.token_urlsafe(URLSAFE_PARAM)
        expires_at = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )
        refresh_token = RefreshToken(
            user_id=user_id, token=token, expires_at=expires_at
        )
        session.add(refresh_token)
        await session.commit()
        return token

    @staticmethod
    async def refresh_access_token(session: AsyncSession, refresh_token: str) -> User:
        result = await session.execute(
            select(RefreshToken)
            .options(joinedload(RefreshToken.user))
            .where(RefreshToken.token == refresh_token)
        )
        token_obj = result.scalar_one_or_none()
        if not token_obj or token_obj.expires_at < datetime.utcnow():
            raise CredentialsError()
        user = token_obj.user
        await session.delete(token_obj)
        await session.commit()
        return user
