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
    """
    Service class for user-related operations.

    All methods are static and cover the full user lifecycle including
    registration, authentication, token refresh, API key management,
    and role verification requests.
    """

    @staticmethod
    async def create_user(session: AsyncSession, user_create: UserCreate) -> User:
        """
        Register a new user with email and password.

        Args:
            session: Async database session.
            user_create: Registration payload with email and password.

        Returns:
            The newly created User instance.

        Raises:
            UserAlreadyExists: If a user with the same email already exists.
        """
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
        """
        Verify user credentials.

        Args:
            session: Async database session.
            email: User email address.
            password: Plain-text password to verify.

        Returns:
            The User instance if credentials are valid, None otherwise.
        """
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not await verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def create_refresh_token(session: AsyncSession, user_id: UUID) -> str:
        """
        Generate and persist a new refresh token for a user.

        Args:
            session: Async database session.
            user_id: ID of the user to create a token for.

        Returns:
            The raw refresh token string.
        """
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
        """
        Validate a refresh token, return the user, and consume the token.

        Args:
            session: Async database session.
            refresh_token: The refresh token string to validate.

        Returns:
            The User associated with the refresh token.

        Raises:
            CredentialsError: If the token is invalid or expired.
        """
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
        """
        Create a new B2B API key for a user.

        Args:
            session: Async database session.
            user_id: ID of the user to create the key for.
            name: Human-readable name for the key.

        Returns:
            Tuple of (APIKeyB2BPartner database object, raw secret key string).
        """
        raw_key = secrets.token_urlsafe(URLSAFE_PARAM)
        key_prefix = raw_key[:KEY_LENGTH_PREFIX]

        from app.core.hashing import get_password_hash_sync

        hashed_key = get_password_hash_sync(raw_key)

        api_key_obj = APIKeyB2BPartner(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )

        session.add(api_key_obj)
        await session.commit()
        await session.refresh(api_key_obj)
        return api_key_obj, raw_key

    @staticmethod
    async def authenticate_api_key_b2b_partner(
        session: AsyncSession, raw_key: str
    ) -> APIKeyB2BPartner | None:
        """
        Authenticate a B2B API key and update its last-used timestamp.

        Args:
            session: Async database session.
            raw_key: The full raw API key string.

        Returns:
            The APIKeyB2BPartner instance if valid, None otherwise.
        """
        key_prefix = raw_key[:KEY_LENGTH_PREFIX]
        result = await session.execute(
            select(APIKeyB2BPartner)
            .options(joinedload(APIKeyB2BPartner.user))
            .where(
                APIKeyB2BPartner.key_prefix == key_prefix, APIKeyB2BPartner.is_active
            )
        )
        api_keys = result.scalars().all()

        from app.core.hashing import verify_password

        for api_key in api_keys:
            if await verify_password(raw_key, api_key.hashed_key):
                # Update last used
                api_key.last_used_at = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()
                return api_key
        return None

    @staticmethod
    async def delete_api_key_b2b_partner(
        session: AsyncSession,
        user_id: UUID,
        key_id: UUID,
    ) -> None:
        """
        Delete a B2B API key owned by the specified user.

        Args:
            session: Async database session.
            user_id: ID of the key owner.
            key_id: ID of the API key to delete.

        Raises:
            NotFoundError: If the key does not exist or is not owned by the user.
        """
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
        """
        Create a role upgrade/verification request for a user.

        A user can only have one pending request at a time. Admin and
        moderator roles cannot be requested.

        Args:
            session: Async database session.
            user_id: ID of the requesting user.
            target_role: The role being requested.
            docs_url: Optional dictionary of verification document URLs.

        Returns:
            The newly created VerificationRequest.

        Raises:
            VerificationRequestAlreadyExists: If a pending request already exists.
            PermissionDeniedError: If the target role is ADMIN or MODERATOR.
        """
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

    @staticmethod
    async def get_verification_requests(
        session: AsyncSession,
        user_id: UUID,
    ) -> list[VerificationRequest]:
        """
        List all verification requests for a user, ordered newest first.

        Args:
            session: Async database session.
            user_id: ID of the user.

        Returns:
            List of VerificationRequest objects.
        """
        result = await session.execute(
            select(VerificationRequest)
            .where(VerificationRequest.user_id == user_id)
            .order_by(VerificationRequest.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_latest_verification_request(
        session: AsyncSession,
        user_id: UUID,
    ) -> VerificationRequest | None:
        """
        Retrieve the most recent verification request for a user.

        Args:
            session: Async database session.
            user_id: ID of the user.

        Returns:
            The latest VerificationRequest, or None if no requests exist.
        """
        result = await session.execute(
            select(VerificationRequest)
            .where(VerificationRequest.user_id == user_id)
            .order_by(VerificationRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
