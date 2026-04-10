import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.audit_log.models import AuditLog
from app.core.config import settings
from app.core.database import Base
from app.services.inventory.models import Product, Reservation
from app.services.media.models import ProductImage
from app.services.orders.models import Order, OrderItem
from app.services.user.models import User

config = context.config

config.set_main_option('sqlalchemy.url', str(settings.database_url))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Configures Alembic with a URL string only, without creating an Engine.
    This mode emits SQL to stdout rather than executing against a database,
    useful for generating migration scripts to review before execution.
    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Configure the Alembic context with the given connection and run migrations.

    Args:
        connection: The SQLAlchemy connection to use for executing migrations.
    """

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations using an async connection.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode by executing async migrations.
    """

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
