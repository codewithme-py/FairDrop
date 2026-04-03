from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import logger
from app.services.inventory.tasks import release_expired_reservations
from app.services.media.tasks import sanitize_and_activate_image_task


async def startup(ctx: dict) -> None:
    engine = create_async_engine(str(settings.database_url))
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    ctx['session_maker'] = session_maker
    logger.info('ARQ startup complete, session_maker added to ctx')


async def shutdown(ctx: dict) -> None:
    engine = ctx['session_maker'].kw['bind']
    await engine.dispose()
    logger.info('ARQ shutdown complete, session_maker removed from ctx')


class WorkerSettings(RedisSettings):
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs: list = [cron(release_expired_reservations, minute=None)]
    functions: list = [sanitize_and_activate_image_task]
