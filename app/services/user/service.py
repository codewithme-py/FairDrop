from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExists
from app.core.security import get_password_hash, verify_password
from app.services.user.models import User
from app.services.user.schemas import UserCreate


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
