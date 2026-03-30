"""
l9/chassis/lifecycle.py
Startup and shutdown orchestration for any constellation node.

Usage (in FastAPI lifespan):
    from l9.chassis import startup, shutdown

    @asynccontextmanager
    async def lifespan(app):
        await startup()
        yield
        await shutdown()
"""

from __future__ import annotations

import structlog

from .registry import get_handler_map

logger = structlog.get_logger(__name__)

_startup_hooks: list = []
_shutdown_hooks: list = []


def on_startup(fn):
    """Register an async startup hook."""
    _startup_hooks.append(fn)
    return fn


def on_shutdown(fn):
    """Register an async shutdown hook."""
    _shutdown_hooks.append(fn)
    return fn


async def startup() -> None:
    """Run all registered startup hooks and log registered handlers."""
    for hook in _startup_hooks:
        await hook()
    handlers = get_handler_map()
    logger.info("chassis.started", handlers=sorted(handlers.keys()))


async def shutdown() -> None:
    """Run all registered shutdown hooks in reverse order."""
    for hook in reversed(_shutdown_hooks):
        await hook()
    logger.info("chassis.shutdown")
