"""
Domain Enrichment API v2.3.0 — Constellation-wired.

Gap pack adaptations:
- startup warnings for missing API/LLM keys
- domain_reader created during lifespan
- orchestration register() receives domain_reader
- converge.configure() receives loaded domain specs instead of an empty mapping
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI

from .api.v1.chassis_endpoint import router as chassis_router
from .api.v1.converge import router as converge_router
from .api.v1.discover import router as discover_router
from .api.v1.fields import router as fields_router
from .core.auth import verify_api_key
from .core.config import Settings, get_settings
from .core.logging_config import setup_logging
from .core.telemetry import setup_telemetry
from .engines.domain_yaml_reader import DomainYamlReader
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
_domain_reader: DomainYamlReader | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load KB, init idempotency/persistence, configure convergence wiring."""
    global _kb, _idem, _domain_reader

    settings = get_settings()
    setup_logging(settings.log_level)
    settings.warn_missing_keys()

    _kb = KBResolver(settings.kb_dir)
    _domain_reader = DomainYamlReader(settings.domains_dir)

    try:
        _idem = IdempotencyStore(settings.redis_url)
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))
        _idem = None

    register_orchestration(kb=_kb, idem_store=_idem, domain_reader=_domain_reader)

    from .services import pg_store
    from .services.event_emitter import get_emitter

    pg_store.init_engine(settings.database_url)
    get_emitter(settings)
    logger.info("pg_store_initialized")

    from .api.v1 import converge as converge_module
    from .services.enrichment_profile import ProfileRegistry

    try:
        from .engines.convergence.loop_state import RedisLoopStateStore

        loop_state_store = (
            RedisLoopStateStore(redis_client=_idem.client) if _idem else _fallback_loop_store()
        )
    except Exception:
        loop_state_store = _fallback_loop_store()

    profile_registry = ProfileRegistry()
    domain_specs: dict[str, dict[str, object]] = {}
    if _domain_reader:
        for domain_id in _domain_reader.list_domains():
            try:
                domain_specs[domain_id] = _domain_reader.load(domain_id).raw_spec
            except Exception as exc:
                logger.warning("domain_spec_load_failed", domain=domain_id, error=str(exc))

    converge_module.configure(
        state_store=loop_state_store,
        profile_registry=profile_registry,
        domain_specs=domain_specs,
        kb_resolver=_kb,
        idem_store=_idem,
    )
    logger.info(
        "converge_module_configured",
        profiles=profile_registry.list_profiles(),
        state_backend="redis" if _idem else "memory",
        domains=sorted(domain_specs.keys()),
    )

    logger.info("api_started", version="2.3.0")

    yield

    if _idem:
        await _idem.close()
    from .services import pg_store as _pg

    await _pg.close_engine()
    _kb = None
    _idem = None
    _domain_reader = None


def _fallback_loop_store():
    """In-memory LoopStateStore used when Redis is unavailable."""
    from .engines.convergence.loop_state import LoopState, LoopStateStore

    class _InMemory(LoopStateStore):
        __slots__ = ("_data",)

        def __init__(self) -> None:
            super().__init__()
            self._data: dict[str, LoopState] = {}

        async def save(self, state: LoopState) -> None:
            self._data[state.run_id] = state

        async def load(self, run_id: str) -> LoopState | None:
            return self._data.get(run_id)

        async def list_active(self, domain: str | None = None) -> list[LoopState]:
            return [
                state for state in self._data.values() if domain is None or state.domain == domain
            ]

    return _InMemory()


app = FastAPI(
    title="L9 ENRICH - Domain Enrichment API",
    version="2.3.0",
    description=(
        "Universal domain-aware entity enrichment. "
        "Layer 2 of the L9 three-layer intelligence stack."
    ),
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
setup_telemetry(app)

app.include_router(chassis_router)
app.include_router(converge_router)
app.include_router(discover_router)
app.include_router(fields_router)


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
    succeeded = sum(1 for result in results if result.state == "completed")
    failed = sum(1 for result in results if result.state == "failed")
    tokens = sum(result.tokens_used for result in results)
    return BatchEnrichResponse(
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        total_processing_time_ms=elapsed,
        total_tokens_used=tokens,
    )
