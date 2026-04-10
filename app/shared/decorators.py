from collections.abc import Callable
from functools import wraps
from typing import Any

import orjson
from fastapi import HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.core.config import settings


def idempotent(
    ttl_seconds: int = settings.idempotent_key_lifetime_sec,
) -> Callable[[Callable], Callable]:
    """
    Decorator that ensures idempotent request handling using Redis caching.

    When a client sends a request with an X-Idempotency-Key header, the
    response is cached in Redis for the specified TTL. Subsequent requests
    with the same key return the cached response instead of re-executing the
    handler, preventing duplicate side effects.

    Args:
        ttl_seconds: Time-to-live in seconds for the cached response.
            Defaults to the value from application settings.

    Returns:
        A decorator that wraps an async handler with idempotency logic.

    Raises:
        HTTPException: 400 error if the X-Idempotency-Key header is missing.

    Example:
        >>> @router.post("/orders")
        >>> @idempotent(ttl_seconds=3600)
        >>> async def create_order(request: Request, data: OrderCreate):
        ...     ...
    """

    def decorator(func: Callable) -> Callable:
        """
        Inner decorator factory that wraps the target function.

        Args:
            func: The async callable to wrap with idempotency logic.

        Returns:
            The wrapped callable with idempotency checking.
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Response | Any:
            """
            Wrapper that checks for a cached idempotent response.

            Extracts the FastAPI Request object from args or kwargs,
            retrieves the X-Idempotency-Key header, and looks up the
            corresponding Redis key. If a cached response exists, it is
            returned directly; otherwise the handler is called and its
            response is cached.

            Args:
                *args: Positional arguments passed to the wrapped handler.
                **kwargs: Keyword arguments passed to the wrapped handler.

            Returns:
                The cached Response if the idempotency key exists,
                otherwise the result of the handler function.
            """
            request: Request | None = None
            for arg in kwargs.values():
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if not request:
                return await func(*args, **kwargs)
            idempotency_key = request.headers.get('x-idempotency-key')
            if not idempotency_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Missing X-Idempotency-Key header',
                )
            redis_client = request.app.state.redis
            redis_key = (
                f'idempotency:{request.method}:{request.url.path}:{idempotency_key}'
            )
            cached_response = await redis_client.get(redis_key)
            if cached_response:
                data = orjson.loads(cached_response)
                return Response(
                    content=orjson.dumps(data),
                    status_code=status.HTTP_200_OK,
                    media_type='application/json',
                )
            response = await func(*args, **kwargs)
            if isinstance(response, BaseModel):
                json_str_to_cache = response.model_dump_json()
            else:
                json_data = jsonable_encoder(response)
                json_str_to_cache = orjson.dumps(json_data).decode()
            await redis_client.setex(redis_key, ttl_seconds, json_str_to_cache)
            return response

        return wrapper

    return decorator
