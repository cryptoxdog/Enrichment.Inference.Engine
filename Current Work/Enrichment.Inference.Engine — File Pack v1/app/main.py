"""
app/main.py  (v2.3.0 — constellation-wired)
============================================
Single ingress for all ENRICH traffic:
  POST /api/v1/enrich          — single entity (Salesforce + Odoo)
  POST /api/v1/enrich/batch    — batch up to 50 (Odoo nightly cron)
  POST /v1/execute             — L9 chassis PacketEnvelope (node-to-node)
  POST /v1/outcomes            — match outcome feedback loop
  GET  /v1/health              — health + KB + circuit breaker status

Changes from v2.2.0:
  - orchestration_layer.register() wires all handlers at startup
  - /v1/execute chassis endpoint added (inter-node traffic)
  - /v1/outcomes endpoint closes ENRICH→GRAPH feedback loop
  - /v1/converge, /v1/scan endpoints from converge.py router included
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI

# Import chassis + converge routers
from .api.v1.chassis_endpoint import router as chassis_router
from .api.v1.converge import router as converge_router
from .core.auth import verify_api_key
from .core.config import Settings, get_settings
from .core.logging_config import setup_logging
from .engines.enrichment_orchestrator import breaker, enrich_batch, enrich_entity
from .engines.orchestration_layer import register as register_orchestration
from .middleware.rate_limiter import RateLimitMiddleware
from .models.schemas import (
    BatchEnrichRequest,
    BatchEnrichResponse,
    EnrichRequest,
    EnrichResponse,
    HealthCheckResponse,
)
from .services.idempotency import IdempotencyStore
from .services.kb_resolver import KBResolver

logger = structlog.get_logger("main")

_kb: KBResolver | None = None
_idem: IdempotencyStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load KB, connect Redis, register orchestration layer."""
    global _kb, _idem

    settings = get_settings()
    setup_logging(settings.log_level)

    _kb = KBResolver(settings.kb_dir)

    try:
        _idem = IdempotencyStore(settings.redis_url)
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as e:
        logger.warning("redis_unavailable", error=str(e))
        _idem = None

    # Wire chassis handlers — this is the line that connects everything
    register_orchestration(kb=_kb, idem_store=_idem)

    logger.info(
        "api_started",
        version="2.3.0",
        kb_files=len(_kb.index.files_loaded),
        kb_polymers=len(_kb.index.polymers),
        constellation_handlers=["enrich", "enrichbatch", "converge", "discover", "enrich_and_sync"],
    )

    yield

    if _idem:
        await _idem.close()
    _kb = None
    _idem = None


app = FastAPI(
    title="L9 ENRICH — Domain Enrichment API",
    version="2.3.0",
    description=(
        "Universal domain-aware entity enrichment. "
        "Layer 2 of the L9 three-layer intelligence stack. "
        "Serves Salesforce Apex callouts, Odoo async_executor, "
        "and any L9 constellation node via PacketEnvelope."
    ),
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# ── Chassis + converge routers ────────────────────────────────────
app.include_router(chassis_router)
app.include_router(converge_router)


# ── Legacy HTTP routes (Salesforce / Odoo direct calls) ───────────
@app.get("/api/v1/health", response_model=HealthCheckResponse)
async def health_check():
    kb = _kb or KBResolver("/dev/null")
    return HealthCheckResponse(
        status="ok",
        version="2.3.0",
        kb_loaded=kb.index.is_loaded,
        kb_polymers=len(kb.index.polymers),
        kb_grades=kb.index.total_grades,
        kb_rules=kb.index.total_rules,
        circuit_breaker_state=breaker.state,
    )


@app.post(
    "/api/v1/enrich",
    response_model=EnrichResponse,
    dependencies=[Depends(verify_api_key)],
)
async def enrich_single(
    request: EnrichRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    return await enrich_entity(request, settings, _kb, _idem)


@app.post(
    "/api/v1/enrich/batch",
    response_model=BatchEnrichResponse,
    dependencies=[Depends(verify_api_key)],
)
async def enrich_batch_endpoint(
    request: BatchEnrichRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    start = time.monotonic()
    results = await enrich_batch(request.entities, settings, _kb, _idem)
    elapsed = int((time.monotonic() - start) * 1000)

    succeeded = sum(1 for r in results if r.state == "completed")
    failed = sum(1 for r in results if r.state == "failed")
    tokens = sum(r.tokens_used for r in results)

    return BatchEnrichResponse(
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        total_processing_time_ms=elapsed,
        total_tokens_used=tokens,
    )
