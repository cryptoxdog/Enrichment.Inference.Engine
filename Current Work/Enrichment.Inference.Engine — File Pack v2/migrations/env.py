"""
Alembic migration environment.
Async-compatible — uses asyncpg.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from app.services.pg_models import Base
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


run_migrations_online()
