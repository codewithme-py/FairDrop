import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import PermissionDeniedError
from app.services.user.models import User, UserRole
from app.shared.deps import get_current_user

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    return bool(pwd_context.verify(plain_password, hashed_password))


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(
        verify_password_sync, plain_password, hashed_password
    )


def get_password_hash_sync(password: str) -> str:
    return str(pwd_context.hash(password))


async def get_password_hash(password: str) -> str:
    return await asyncio.to_thread(get_password_hash_sync, password)


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
