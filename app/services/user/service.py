import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.exceptions import (
    CredentialsError,
    NotFoundError,
    PermissionDeniedError,
    UserAlreadyExists,
    VerificationRequestAlreadyExists,
)
from app.core.hashing import get_password_hash, verify_password
from app.services.user.models import (
    APIKeyB2BPartner,
    RefreshToken,
    User,
    UserRole,
    VerificationRequest,
    VerificationStatus,
)
from app.services.user.schemas import UserCreate

URLSAFE_PARAM = 32
KEY_LENGTH_PREFIX = 12


class UserService:
    @staticmethod
    async def create_user(session: AsyncSession, user_create: UserCreate) -> User:
        result = await session.execute(
            select(User).where(User.email == user_create.email)
        )
        if result.scalar_one_or_none():
            raise UserAlreadyExists
        hashed_password = await get_password_hash(user_create.password)
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
        if not user or not await verify_password(password, user.password_hash):
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

    @staticmethod
    async def create_api_key_b2b_partner(
        session: AsyncSession, user_id: UUID, name: str
    ) -> tuple[APIKeyB2BPartner, str]:
        raw_key = secrets.token_urlsafe(URLSAFE_PARAM)
        key_prefix = raw_key[:KEY_LENGTH_PREFIX]
        hashed_key = await get_password_hash(raw_key)
        create_api_key_b2b_partner = APIKeyB2BPartner(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )
        session.add(create_api_key_b2b_partner)
        await session.commit()
        await session.refresh(create_api_key_b2b_partner)
        return create_api_key_b2b_partner, raw_key

    @staticmethod
    async def authenticate_api_key_b2b_partner(
        session: AsyncSession, raw_key: str
    ) -> APIKeyB2BPartner | None:
        key_prefix = raw_key[:KEY_LENGTH_PREFIX]
        result = await session.execute(
            select(APIKeyB2BPartner)
            .options(joinedload(APIKeyB2BPartner.user))
            .where(
                APIKeyB2BPartner.key_prefix == key_prefix,
                APIKeyB2BPartner.is_active,
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key and await verify_password(raw_key, api_key.hashed_key):
            api_key.last_used_at = datetime.now(UTC)
            await session.commit()
            return api_key
        return None

    @staticmethod
    async def delete_api_key_b2b_partner(
        session: AsyncSession,
        user_id: UUID,
        key_id: UUID,
    ) -> None:
        result = await session.execute(
            select(APIKeyB2BPartner).where(
                APIKeyB2BPartner.user_id == user_id,
                APIKeyB2BPartner.id == key_id,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise NotFoundError()
        await session.delete(api_key)
        await session.commit()
        return None

    @staticmethod
    async def create_verification_request(
        session: AsyncSession,
        user_id: UUID,
        target_role: UserRole,
        docs_url: dict | None = None,
    ) -> VerificationRequest:
        result = await session.execute(
            select(VerificationRequest).where(
                VerificationRequest.user_id == user_id,
                VerificationRequest.status == VerificationStatus.PENDING,
            )
        )
        if result.scalar_one_or_none():
            raise VerificationRequestAlreadyExists()
        if target_role in (UserRole.ADMIN, UserRole.MODERATOR):
            raise PermissionDeniedError('Cannot request administrative roles')
        verification_request = VerificationRequest(
            user_id=user_id,
            target_role=target_role,
            docs_url=docs_url,
        )
        session.add(verification_request)
        await session.commit()
        await session.refresh(verification_request)
        return verification_request
