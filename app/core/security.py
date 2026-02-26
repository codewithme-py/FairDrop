import asyncio
from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

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
