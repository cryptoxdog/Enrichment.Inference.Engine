"""domain-enrichment-api — FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import verify_api_key
from .circuit_breaker import CircuitBreaker
from .config import get_settings
from .kb_resolver import KBResolver
from .logging_config import setup_logging
from .pipeline import enrich_pipeline
from .schemas import EnrichmentRequest, EnrichmentResponse, HealthResponse

logger = structlog.get_logger("main")

# ── Shared singletons ──────────────────────────
breaker: CircuitBreaker | None = None
kb: KBResolver | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global breaker, kb
    settings = get_settings()
    setup_logging(settings.log_level)
    breaker = CircuitBreaker(
        failure_threshold=settings.cb_failure_threshold,
        cooldown_seconds=settings.cb_cooldown_seconds,
    )
    kb = KBResolver(kb_dir=settings.kb_dir)
    logger.info("startup_complete", model=settings.perplexity_model)
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Domain Enrichment API",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────
@app.get("/api/v1/health", response_model=HealthResponse, tags=["ops"])
async def health():
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="2.2.0",
        model=settings.perplexity_model,
        kb_loaded=kb.index.is_loaded if kb else False,
        circuit=("closed" if breaker and breaker.allow() else "open"),
    )


# ── Enrich ─────────────────────────────────────
@app.post(
    "/api/v1/enrich",
    response_model=EnrichmentResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["enrichment"],
)
async def enrich(request: EnrichmentRequest):
    settings = get_settings()
    result = await enrich_pipeline(
        request=request,
        settings=settings,
        breaker=breaker,
        kb_resolver=kb,
    )
    return result


# ── Global error handler ───────────────────────
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal_error"})
