# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [app, startup]
# tags: [L9_STARTUP, lifecycle, packet-safe]
# owner: platform
# status: active
# --- /L9_META ---
"""
app/main.py

FastAPI entrypoint for the Enrichment.Inference.Engine node.

GAP #03: startup calls ConvergenceController.configure() before traffic.
GAP #01: startup calls startup_result_store(); shutdown calls shutdown.

Architecture boundary:
  - POST /v1/execute  (chassis_endpoint)
  - GET  /v1/health   (chassis health probe)
  - POST /v1/converge (convergence loop — this node's primary domain action)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import chassis_endpoint, converge, intake
from app.core.config import get_settings
from app.engines.convergence_controller import ConvergenceController
from app.services.result_store import shutdown_result_store, startup_result_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup -> serve -> shutdown lifecycle."""
    settings = get_settings()

    await ConvergenceController.configure(settings=settings)
    logger.info("convergence_controller_configured")

    await startup_result_store()
    logger.info("result_store_ready")

    yield

    await shutdown_result_store()
    logger.info("result_store_closed")


app = FastAPI(
    title="L9 Enrichment Inference Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.include_router(chassis_endpoint.router, prefix="/v1")
app.include_router(converge.router, prefix="/v1")
app.include_router(intake.router, prefix="/v1")
