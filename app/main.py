import structlog
from fastapi import FastAPI

from app.core.logging import setup_logging
from app.core.setup import setup_exception_handlers
from app.services.user.routes import router_v1

setup_logging()
logger = structlog.get_logger(__name__)
app = FastAPI()

setup_exception_handlers(app)

app.include_router(router_v1, prefix='/api/v1', tags=['Users'])


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/')
def root() -> dict[str, str]:
    logger.info('root health check')
    return {'message': 'Hello from fairdrop!'}
