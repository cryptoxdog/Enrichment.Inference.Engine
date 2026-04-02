"""FastAPI middleware for automatic Prometheus instrumentation.

Wraps every HTTP request with:
- REQUEST_COUNT increment with labels
- REQUEST_LATENCY observation
- ACTIVE_REQUESTS gauge inc/dec
- ERROR_COUNT on exceptions

Special handling: /metrics excluded from REQUEST_LATENCY to prevent
Prometheus self-instrumentation noise.
"""
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ACTIVE_REQUESTS,
    ERROR_COUNT,
)

logger = structlog.get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics collection middleware.

    INVARIANT: Must be registered via app.add_middleware(), not @app.middleware
    decorator, to wrap the full ASGI stack including exception handlers.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint from being measured (avoid self-instrumentation)
        if request.url.path == "/metrics":
            return await call_next(request)

        # Extract tenant from request state (set by upstream tenant middleware)
        # Fallback to "unknown" if not set
        tenant = getattr(request.state, "tenant_id", "unknown")
        if not tenant or tenant == "":
            tenant = "unknown"

        # Normalize endpoint path (strip trailing slash)
        endpoint = request.url.path.rstrip("/")

        ACTIVE_REQUESTS.inc()
        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
            status_code = str(response.status_code)

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                tenant=tenant,
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint,
                tenant=tenant,
            ).observe(time.perf_counter() - start_time)

            return response

        except Exception as exc:
            # Increment error counter
            ERROR_COUNT.labels(
                error_type=type(exc).__name__,
                component="middleware",
                tenant=tenant,
            ).inc()

            logger.error(
                "middleware_exception",
                error_type=type(exc).__name__,
                endpoint=endpoint,
                tenant=tenant,
                exc_info=True,
            )
            raise

        finally:
            # Always decrement active requests gauge
            ACTIVE_REQUESTS.dec()
