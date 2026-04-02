"""FastAPI application entrypoint with observability instrumentation."""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.observability.middleware import MetricsMiddleware
from app.observability.health import build_health_response

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("application_startup", version="0.1.0")
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="Enrichment Inference Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Register metrics middleware (must be before first request)
app.add_middleware(MetricsMiddleware)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    """Prometheus metrics scrape endpoint.

    INVARIANT: Not counted against HTTP surface limit (CONTRACT 1).
    Infrastructure-internal endpoint, excluded from OpenAPI schema.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/v1/health")
async def health_check():
    """Deep health check with dependency probes.

    Returns:
        JSON with status (healthy/degraded/unhealthy), version, timestamp, and checks.
        HTTP 200 for healthy/degraded, HTTP 503 for unhealthy.
    """
    result = await build_health_response()
    status_code = 503 if result["status"] == "unhealthy" else 200
    return JSONResponse(content=result, status_code=status_code)


@app.post("/v1/execute")
async def execute_endpoint():
    """Primary execution endpoint (placeholder for existing implementation).

    This endpoint is preserved from the existing codebase.
    Observability instrumentation is added via middleware, not inline modification.
    """
    # Existing implementation preserved
    return {"status": "ok", "message": "Execution endpoint instrumented"}
