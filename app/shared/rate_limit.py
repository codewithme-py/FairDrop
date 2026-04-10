from fastapi import HTTPException, status
from redis.commands.core import AsyncScript

from app.core.config import settings

USER_EXCEEDED_LIMIT = 'Rate limit exceeded for this identifier'
GLOBAL_EXCEEDED_LIMIT = 'Global rate limit exceeded'


async def check_rate_limit(
    rate_limit_script: AsyncScript,
    keys: list[str],
    limits: list[int],
    ttl: int = settings.rate_limit_ttl_seconds,
) -> bool:
    """
    Check whether a request exceeds rate limits using a Redis Lua script.

    Executes a Lua script in Redis that atomically increments counters for
    the provided keys and compares them against the supplied limits. A
    single-user limit check is supported; an optional second key with a
    very high limit is used internally to satisfy the Lua script's
    expectation of two keys.

    Args:
        rate_limit_script: A registered Redis Lua script that performs the
            atomic rate limit check.
        keys: A list of Redis keys identifying the rate limit buckets.
            Only the first key is meaningful; a dummy second key is appended
            internally.
        limits: A list of maximum allowed request counts corresponding to
            each key. The first limit applies to the user/identifier; the
            second is a dummy global limit set very high.
        ttl: Time-to-live in seconds for the rate limit counters. Defaults
            to the value from application settings.

    Returns:
        True if the request is within the allowed rate limits.

    Raises:
        HTTPException: 429 error with a user-specific message if the
            identifier-specific limit is exceeded (result 0).
        HTTPException: 429 error with a global message if the global limit
            is exceeded (result -1).
    """
    if len(keys) == 1:
        keys.append(f'rate_limit:dummy:{keys[0]}')
        limits.append(999_999_999)
    result = await rate_limit_script(keys=keys, args=[*limits, ttl])
    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=USER_EXCEEDED_LIMIT
        )
    elif result == -1:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=GLOBAL_EXCEEDED_LIMIT,
        )
    return True
