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
