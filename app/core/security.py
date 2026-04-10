from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends
from jose import jwt

from app.core.auth_schemes import header_scheme
from app.core.config import settings
from app.core.database import SessionDep
from app.core.exceptions import CredentialsError, PermissionDeniedError
from app.services.user.models import User, UserRole
from app.shared.deps import get_current_user


async def get_b2b_partner_by_api_key(
    api_key: Annotated[str | None, Depends(header_scheme)], session: SessionDep
) -> User:
    """
    Authenticate a B2B partner using an API key and return the associated user.

    Args:
        api_key: The API key provided via the X-API-Key header.
        session: The async database session.

    Returns:
        The authenticated User object.

    Raises:
        CredentialsError: If the API key is missing, invalid, the user is inactive,
            or the user is not a B2B partner account.
    """
    from app.services.user.service import UserService

    if not api_key:
        raise CredentialsError('API key is required')
    key_obj = await UserService.authenticate_api_key_b2b_partner(session, api_key)
    if not key_obj:
        raise CredentialsError('Invalid API key')
    user = key_obj.user
    if not user.is_active:
        raise CredentialsError('User is not active')
    if user.role not in (UserRole.USER_B2B, UserRole.SELLER_B2B):
        raise CredentialsError('Not a B2B partner account')
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token with the given payload and optional expiry.

    Args:
        data: The payload dictionary to encode in the token.
        expires_delta: Optional explicit expiry duration. Defaults to the configured
            access token expiry if not provided.

    Returns:
        The encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    return str(encoded_jwt)


async def check_permission(
    user: User, allowed_roles: list[UserRole], required_verified: bool = False
) -> None:
    """
    Verify that a user has the required role and verification status.

    Admin users are always granted access. Non-admin users must have a role in
    allowed_roles and, if required_verified is True, must be verified.

    Args:
        user: The user to check permissions for.
        allowed_roles: List of roles permitted to perform the action.
        required_verified: Whether the user must be verified.

    Raises:
        PermissionDeniedError: If the user is not verified when required,
            or if the user's role is not in the allowed list.
    """
    if user.role == UserRole.ADMIN:
        return
    if required_verified and not user.is_verified:
        raise PermissionDeniedError('User is not verified')
    if user.role not in allowed_roles:
        raise PermissionDeniedError(
            'User does not have permission to perform this action'
        )


def check_ownership(user: User, obj: Any) -> None:
    """
    Verify that a user owns the given object based on owner_id or user_id.

    Admin and moderator users bypass ownership checks.

    Args:
        user: The user whose ownership is being verified.
        obj: The object to check ownership of. Must have an owner_id or user_id
            attribute.

    Raises:
        ValueError: If the object has neither owner_id nor user_id.
        PermissionDeniedError: If the user is not the owner.
    """
    if user.role in (UserRole.ADMIN, UserRole.MODERATOR):
        return
    owner_attr = 'owner_id'
    if not hasattr(obj, 'owner_id') and hasattr(obj, 'user_id'):
        owner_attr = 'user_id'
    if not hasattr(obj, owner_attr):
        raise ValueError(f'Object {type(obj)} does not have owner_id or user_id')
    if getattr(obj, owner_attr) != user.id:
        raise PermissionDeniedError


class RoleChecker:
    """
    FastAPI dependency that checks if the current user has an allowed role.

    Attributes:
        allowed_roles: List of UserRole values that are permitted.
        required_verified: Whether the user must be verified.
    """

    def __init__(self, allowed_roles: list[UserRole], required_verified: bool = False):
        """
        Initialize the RoleChecker.

        Args:
            allowed_roles: List of UserRole values that are permitted.
            required_verified: Whether the user must be verified.
        """
        self.allowed_roles = allowed_roles
        self.required_verified = required_verified

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        """
        Check the current user's role against the allowed roles.

        Args:
            user: The current user, resolved via the get_current_user dependency.

        Returns:
            The same User object if the check passes.

        Raises:
            PermissionDeniedError: If the user does not have an allowed role
                or is not verified when required.
        """
        await check_permission(user, self.allowed_roles, self.required_verified)
        return user
