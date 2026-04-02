"""Prometheus metric registry.

All metric objects are defined here as module-level singletons.
Never create metrics outside this file.

LABEL CONTRACT (immutable once deployed):
- tenant: resolved tenant ID string; "unknown" if resolution fails
- endpoint: normalized path (strip trailing slash)
- status_code: string integer ("200", "422", "500")
- query_type: "enrichment", "scoring", "gds", "health_check", "unknown"
- error_type: exception class name
- operation: Redis operation name ("get", "set", "delete", etc.)
"""
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter(
    "l9_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code", "tenant"],
)

REQUEST_LATENCY = Histogram(
    "l9_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint", "tenant"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_REQUESTS = Gauge(
    "l9_http_requests_active",
    "Currently in-flight HTTP requests",
)

NEO4J_QUERY_LATENCY = Histogram(
    "l9_neo4j_query_duration_seconds",
    "Neo4j query execution time",
    ["query_type", "tenant"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

REDIS_OP_LATENCY = Histogram(
    "l9_redis_op_duration_seconds",
    "Redis operation latency",
    ["operation"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05],
)

ERROR_COUNT = Counter(
    "l9_errors_total",
    "Total application errors",
    ["error_type", "component", "tenant"],
)
