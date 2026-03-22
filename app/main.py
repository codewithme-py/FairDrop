import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware
from structlog.contextvars import bind_contextvars

from app.core.admin.admin import register_admin_views
from app.core.admin.admin_auth import authentication_backend
from app.core.config import settings
from app.core.database import engine
from app.core.logging import setup_logging
from app.core.lua_scripts import RATE_LIMIT_LUA_SCRIPT
from app.core.s3 import init_s3_bucket
from app.core.setup import setup_exception_handlers
from app.services.inventory.routes import router_v1 as inventory_router_v1
from app.services.media.routes import router_v1 as media_router_v1
from app.services.orders.routes import router_v1 as order_router_v1
from app.services.user.routes import router_v1 as user_router_v1

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    client = Redis.from_url(settings.redis_url, decode_responses=True, encoding='utf-8')
    app.state.redis = client
    app.state.rate_limit_script = client.register_script(RATE_LIMIT_LUA_SCRIPT)
    await init_s3_bucket()
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
    default_response_class=ORJSONResponse,
)

Instrumentator().instrument(app).expose(app)

setup_exception_handlers(app)

admin = Admin(
    app,
    engine,
    authentication_backend=authentication_backend,
    title='FairDrop Admin Panel',
)

register_admin_views(admin)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)


@app.middleware('http')
async def add_request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(uuid.uuid4())
    bind_contextvars(
        request_id=request_id,
        remote_ip=request.client.host if request.client else 'unknown',
    )
    try:
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
    except Exception as e:
        logger.error('request failed', exc_info=True)
        raise e
    return response


app.include_router(user_router_v1, prefix='/api/v1', tags=['Users'])
app.include_router(order_router_v1, prefix='/api/v1', tags=['Orders'])
app.include_router(inventory_router_v1, prefix='/api/v1', tags=['Inventory'])
app.include_router(media_router_v1, prefix='/api/v1', tags=['Media'])


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/')
def root() -> dict[str, str]:
    logger.info('root health check')
    return {'message': 'Hello from fairdrop!'}
