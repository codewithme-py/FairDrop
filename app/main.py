import structlog
from fastapi import FastAPI

from app.core.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)
app = FastAPI()


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/')
def root() -> dict[str, str]:
    logger.info('root health check')
    return {'message': 'Hello from fairdrop!'}
