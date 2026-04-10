import asyncio

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    """
    Synchronously verify a plain password against a bcrypt hash.

    Args:
        plain_password: The plain-text password to verify.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return bool(pwd_context.verify(plain_password, hashed_password))


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Asynchronously verify a plain password against a bcrypt hash.

    Runs the synchronous verification in a thread pool to avoid blocking
    the event loop.

    Args:
        plain_password: The plain-text password to verify.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return await asyncio.to_thread(
        verify_password_sync, plain_password, hashed_password
    )


def get_password_hash_sync(password: str) -> str:
    """
    Synchronously generate a bcrypt hash from a plain password.

    Args:
        password: The plain-text password to hash.

    Returns:
        The bcrypt hash string.
    """
    return str(pwd_context.hash(password))


async def get_password_hash(password: str) -> str:
    """
    Asynchronously generate a bcrypt hash from a plain password.

    Runs the synchronous hashing in a thread pool to avoid blocking
    the event loop.

    Args:
        password: The plain-text password to hash.

    Returns:
        The bcrypt hash string.
    """
    return await asyncio.to_thread(get_password_hash_sync, password)
