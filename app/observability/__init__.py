"""Observability module: metrics, health checks, and instrumentation.

Exports all Prometheus metric objects as module-level singletons.
Import pattern: `from app.observability import REQUEST_COUNT`
"""
from app.observability.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ACTIVE_REQUESTS,
    NEO4J_QUERY_LATENCY,
    REDIS_OP_LATENCY,
    ERROR_COUNT,
)

__all__ = [
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "ACTIVE_REQUESTS",
    "NEO4J_QUERY_LATENCY",
    "REDIS_OP_LATENCY",
    "ERROR_COUNT",
]
