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
    if user.role == UserRole.ADMIN:
        return
    if required_verified and not user.is_verified:
        raise PermissionDeniedError('User is not verified')
    if user.role not in allowed_roles:
        raise PermissionDeniedError(
            'User does not have permission to perform this action'
        )


def check_ownership(user: User, obj: Any) -> None:
    if user.role in (UserRole.ADMIN, UserRole.MODERATOR):
        return
    if not hasattr(obj, 'owner_id'):
        raise ValueError(f'Object {type(obj)} does not have owner_id')
    if obj.owner_id != user.id:
        raise PermissionDeniedError


class RoleChecker:
    def __init__(self, allowed_roles: list[UserRole], required_verified: bool = False):
        self.allowed_roles = allowed_roles
        self.required_verified = required_verified

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        await check_permission(user, self.allowed_roles, self.required_verified)
        return user
