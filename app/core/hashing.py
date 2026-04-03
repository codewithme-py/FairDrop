import asyncio

from passlib.context import CryptContext

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
