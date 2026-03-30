"""
l9/chassis/registry.py
Handler registry — maps action names to async callables.
Each node calls register_handler() at startup; the router dispatches here.

Handler contract (L9 standard):
    async def handle_<action>(tenant: str, payload: dict) -> dict
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

_REGISTRY: dict[str, Callable[..., Coroutine]] = {}


def register_handler(
    action: str,
    handler: Callable[..., Coroutine] | None = None,
) -> Callable:
    """
    Register an action handler.

    Can be used as a decorator:
        @register_handler("enrich")
        async def handle_enrich(tenant, payload): ...

    Or called directly:
        register_handler("enrich", handle_enrich)
    """

    def _register(fn: Callable) -> Callable:
        if action in _REGISTRY:
            logger.warning("chassis.handler_overwrite", action=action)
        _REGISTRY[action] = fn
        logger.debug("chassis.handler_registered", action=action, fn=fn.__name__)
        return fn

    if handler is not None:
        return _register(handler)
    return _register


def get_handler_map() -> dict[str, Callable]:
    """Return a snapshot of the current registry (read-only view)."""
    return dict(_REGISTRY)


def clear_handlers() -> None:
    """Clear all registrations — for test isolation only."""
    _REGISTRY.clear()


def resolve(action: str) -> Callable[..., Coroutine]:
    """Resolve an action to its handler or raise KeyError."""
    if action not in _REGISTRY:
        raise KeyError(
            f"No handler registered for action '{action}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[action]
