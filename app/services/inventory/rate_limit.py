from fastapi import HTTPException, status
from redis.commands.core import AsyncScript

from app.core.config import settings

USER_EXCEEDED_LIMIT = 'User limit exceeded'
GLOBAL_EXCEEDED_LIMIT = 'Global limit exceeded'


async def check_rate_limit(
    rate_limit_script: AsyncScript,
    user_id: int | str,
    item_id: int | str,
    user_limit: int = settings.rate_limit_user_rps,
    item_limit: int = settings.rate_limit_global_rps,
    ttl: int = settings.rate_limit_ttl_seconds,
) -> bool:
    user_key = f'rate_limit:user:{user_id}'
    item_key = f'rate_limit:item:{item_id}'
    result = await rate_limit_script(
        keys=[user_key, item_key], args=[user_limit, item_limit, ttl]
    )
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
