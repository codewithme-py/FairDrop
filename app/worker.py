from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import logger
from app.services.inventory.tasks import release_expired_reservations
from app.services.media.tasks import sanitize_and_activate_image_task


async def startup(ctx: dict) -> None:
    """Initialize resources for the worker."""
    try:
        engine = create_async_engine(
            str(settings.database_url),
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        ctx['session_maker'] = session_maker
        logger.info(
            'ARQ worker startup complete', database_url=settings.database_url_masked
        )
    except Exception as e:
        logger.error('ARQ worker startup failed', error=str(e))
        raise


async def shutdown(ctx: dict) -> None:
    """Cleanup resources on worker shutdown."""
    if 'session_maker' in ctx:
        engine = ctx['session_maker'].kw['bind']
        await engine.dispose()
        logger.info('ARQ worker shutdown: database engine disposed')


class WorkerSettings(RedisSettings):
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs: list = [cron(release_expired_reservations, minute=None)]
    functions: list = [sanitize_and_activate_image_task]
