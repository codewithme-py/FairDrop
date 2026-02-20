from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.lua_scripts import RATE_LIMIT_LUA_SCRIPT
from app.core.setup import setup_exception_handlers
from app.services.user.routes import router_v1

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    redis_url = f'redis://{settings.redis_host}:{settings.redis_port}'
    client = Redis.from_url(redis_url, decode_responses=True, encoding='utf-8')
    app.state.redis = client
    app.state.rate_limit_script = client.register_script(RATE_LIMIT_LUA_SCRIPT)
    try:
        logger.info('redis connected')
        yield
    finally:
        await client.aclose()
        logger.info('redis disconnected')


app = FastAPI(
    title='FairDrop',
    description='FairDrop API HL B2B Dropshipping Platform',
    version='0.1.0',
    lifespan=lifespan,
)

setup_exception_handlers(app)

app.include_router(router_v1, prefix='/api/v1', tags=['Users'])


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/')
def root() -> dict[str, str]:
    logger.info('root health check')
    return {'message': 'Hello from fairdrop!'}
