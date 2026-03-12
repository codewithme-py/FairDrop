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
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Response | Any:
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
            redis_key = f'idempotency:{idempotency_key}'
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
