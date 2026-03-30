"""
app/core/dependencies.py
FastAPI dependency injection container.
Initialises shared resources once at startup; injected per-request.
"""

from __future__ import annotations

from functools import lru_cache

from app.engines.convergence.loop_state import (
    AbstractLoopStateStore,
    PostgresLoopStateStore,
    RedisLoopStateStore,
)
from app.services.pg_store import PgStore

from app.core.config import settings


@lru_cache(maxsize=1)
def get_pg_store() -> PgStore:
    return PgStore(dsn=settings.database_url)


@lru_cache(maxsize=1)
def get_loop_state_store() -> AbstractLoopStateStore:
    if settings.redis_url:
        return RedisLoopStateStore(settings.redis_url)
    return PostgresLoopStateStore(settings.database_url)


# Module-level singletons for import by other modules
pg_store = get_pg_store()
loop_state_store = get_loop_state_store()
