from typing import cast

from fastapi import Request
from redis.asyncio import Redis


async def get_redis(request: Request) -> Redis:
    """
    FastAPI dependency that retrieves the Redis client from the application state.

    Args:
        request: The current HTTP request.

    Returns:
        The async Redis client instance.
    """
    return cast(Redis, request.app.state.redis)
