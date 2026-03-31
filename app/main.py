# app/main.py
"""
L9 Enrichment Engine — FastAPI application entry point.

Mounts:
    POST /v1/execute  — primary action dispatch (PacketEnvelope ingress)
    GET  /v1/health   — liveness + readiness probe
    POST /v1/converge — multi-pass convergence loop trigger
    GET  /v1/fields   — domain field schema introspection
    POST /v1/discover — batch field discovery for schema evolution

Startup:
    - PostgreSQL async engine initialized via pg_store.init_engine()
    - Redis event emitter singleton created
    - PacketRouter singleton created
    - spec.yaml loaded and validated
    - Structured logging configured (structlog + JSON renderer in production)

Shutdown:
    - pg_store.close_engine()
    - Redis backend connection closed
    - httpx client pools drained via PacketRouter

Design constraints (L9 engine boundary):
    - No auth middleware (chassis concern)
    - No rate limiting (chassis concern)
    - No tenant routing (chassis concern)
    - No Docker/K8s/CI/CD scaffolding (platform concern)
    - No OpenTelemetry instrumentation bootstrapping (platform concern)
    - Structured logging only — no print(), no stdlib logging.basicConfig()
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
import yaml
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from .core.config import Settings, get_settings
from .engines.converge import ConvergenceRouter
from .engines.discover import DiscoverRouter
from .engines.fields import FieldsRouter
from .engines.router import ActionRouter
from .services import pg_store
from .services.event_emitter import get_emitter
from .engines.packet_router import get_router

logger = structlog.get_logger("main")


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup: initialize all infrastructure singletons in dependency order.
    Shutdown: drain connections in reverse order.

    Order matters:
    1. Settings validated first — all downstream init depends on them.
    2. pg_store engine — persistence layer, needed by all handlers.
    3. Spec loaded — action router cannot be built without spec.yaml.
    4. Action router — builds handler registry from spec.
    5. Convergence / field / discover routers.
    6. Event emitter — fire-and-forget, non-blocking.
    7. Packet router — inter-node comms; initialized after local services.
    """
    settings: Settings = get_settings()

    # ── 1. Structured logging ──────────────────────────────────────────────
    _configure_logging(settings)
    log = structlog.get_logger("lifespan")
    log.info("engine_starting", environment=settings.environment, version=settings.version)

    # ── 2. PostgreSQL ──────────────────────────────────────────────────────
    pg_store.init_engine(
        database_url=settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    log.info("pg_store_initialized")

    # ── 3. Spec ────────────────────────────────────────────────────────────
    spec = _load_spec(settings.spec_path)
    app.state.spec = spec
    log.info("spec_loaded", domain_count=len(spec.get("domains", {})))

    # ── 4. Action router ───────────────────────────────────────────────────
    action_router = ActionRouter(spec=spec, settings=settings)
    app.state.action_router = action_router
    log.info("action_router_initialized", actions=list(action_router.handler_map.keys()))

    # ── 5. Convergence / field routers ─────────────────────────────────────
    app.state.convergence_router = ConvergenceRouter(spec=spec, settings=settings)
    app.state.fields_router = FieldsRouter(spec=spec)
    app.state.discover_router = DiscoverRouter(spec=spec, settings=settings)

    # ── 6. Event emitter ───────────────────────────────────────────────────
    emitter = get_emitter(settings)
    app.state.emitter = emitter
    log.info("event_emitter_initialized")

    # ── 7. Packet router ───────────────────────────────────────────────────
    packet_router = get_router(settings)
    app.state.packet_router = packet_router
    log.info("packet_router_initialized")

    log.info("engine_ready")
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    log.info("engine_shutting_down")
    await pg_store.close_engine()
    log.info("pg_store_closed")
    if hasattr(emitter, "_backend") and hasattr(emitter._backend, "close"):
        await emitter._backend.close()
    log.info("event_emitter_closed")
    if hasattr(packet_router, "close"):
        await packet_router.close()
    log.info("packet_router_closed")
    log.info("engine_stopped")


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="L9 Enrichment Engine",
        version=settings.version,
        description=(
            "Spec-driven entity enrichment engine for the L9 constellation. "
            "Implements PacketEnvelope ingress, multi-pass convergence, "
            "Bayesian belief propagation, and schema evolution."
        ),
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # ── Exception handlers ────────────────────────────────────────────────
    app.add_exception_handler(ValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(_build_execute_router())
    app.include_router(_build_health_router())
    app.include_router(_build_converge_router())
    app.include_router(_build_fields_router())
    app.include_router(_build_discover_router())

    return app


app = create_app()


# ── Request/Response models ───────────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    """
    PacketEnvelope ingress model for POST /v1/execute.

    action:        identifies the handler to invoke (maps to handle_<action> in spec)
    tenant_id:     L9 tenant propagation — required on all requests
    payload:       domain-specific input, validated by the handler's Pydantic schema
    correlation_id: optional caller-supplied trace ID for lineage propagation
    content_hash:  optional SHA-256 of (action + tenant_id + payload) for integrity check
    """

    action: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=256)
    content_hash: str | None = Field(default=None, max_length=64)


class ExecuteResponse(BaseModel):
    """
    PacketEnvelope egress model for POST /v1/execute.

    success:            True if the handler completed without raising
    action:             echoed from request for routing confirmation
    tenant_id:          echoed for lineage
    correlation_id:     propagated from request or generated
    result:             handler output — always a dict
    processing_time_ms: wall-clock time for the handler invocation
    content_hash:       SHA-256 of result for downstream integrity verification
    error:              present only when success=False
    """

    success: bool
    action: str
    tenant_id: str
    correlation_id: str | None
    result: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: int
    content_hash: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    checks: dict[str, str]
    uptime_seconds: float


class ConvergeRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    entity_id: str = Field(..., min_length=1, max_length=256)
    object_type: str = Field(..., min_length=1, max_length=128)
    domain: str = Field(..., min_length=1, max_length=128)
    initial_payload: dict[str, Any] = Field(default_factory=dict)
    max_passes: int = Field(default=5, ge=1, le=20)
    max_budget_tokens: int = Field(default=50_000, ge=1000, le=500_000)
    correlation_id: str | None = Field(default=None, max_length=256)


class FieldsRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=128)
    object_type: str | None = Field(default=None, max_length=128)
    include_scoring_dims: bool = Field(default=False)
    include_gate_specs: bool = Field(default=False)


class DiscoverRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    domain: str = Field(..., min_length=1, max_length=128)
    batch_run_id: str = Field(..., min_length=1, max_length=256)
    sample_payloads: list[dict[str, Any]] = Field(..., min_length=1, max_length=1000)
    min_fill_rate: float = Field(default=0.10, ge=0.0, le=1.0)
    min_avg_confidence: float = Field(default=0.50, ge=0.0, le=1.0)
    correlation_id: str | None = Field(default=None, max_length=256)


# ── Routers ───────────────────────────────────────────────────────────────────


def _build_execute_router():
    from fastapi import APIRouter

    router = APIRouter()

    @router.post(
        "/v1/execute",
        response_model=ExecuteResponse,
        status_code=status.HTTP_200_OK,
        summary="Execute an engine action via PacketEnvelope",
        description=(
            "Primary ingress for all L9 constellation traffic. "
            "Routes action to the registered handler, validates via spec.yaml, "
            "and returns a PacketEnvelope-compliant response with lineage metadata."
        ),
        tags=["Engine"],
    )
    async def execute(request: ExecuteRequest, http_request: Request) -> ExecuteResponse:
        log = structlog.get_logger("execute").bind(
            action=request.action,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
        )
        log.info("execute_request_received")

        action_router: ActionRouter = http_request.app.state.action_router

        if request.action not in action_router.handler_map:
            log.warning("unknown_action", action=request.action)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: '{request.action}'. "
                       f"Valid actions: {sorted(action_router.handler_map.keys())}",
            )

        # Content-hash integrity check (optional — only when caller supplies hash)
        if request.content_hash:
            import hashlib
            import json as _json
            payload_json = _json.dumps(request.payload, sort_keys=True, default=str)
            expected_hash = hashlib.sha256(
                f"{request.action}:{request.tenant_id}:{payload_json}".encode()
            ).hexdigest()
            if expected_hash != request.content_hash:
                log.warning(
                    "content_hash_mismatch",
                    expected=expected_hash,
                    received=request.content_hash,
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="content_hash mismatch — payload integrity check failed.",
                )

        t_start = time.monotonic()
        try:
            handler = action_router.handler_map[request.action]
            result: dict[str, Any] = await handler(
                tenant=request.tenant_id,
                payload=request.payload,
            )
        except HTTPException:
            raise
        except Exception as exc:
            processing_ms = int((time.monotonic() - t_start) * 1000)
            log.error(
                "execute_handler_error",
                error=str(exc),
                processing_ms=processing_ms,
                exc_info=True,
            )
            return ExecuteResponse(
                success=False,
                action=request.action,
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
                result={},
                processing_time_ms=processing_ms,
                error=str(exc),
            )

        processing_ms = int((time.monotonic() - t_start) * 1000)

        # Derive result content hash for downstream lineage
        import hashlib
        import json as _json
        result_json = _json.dumps(result, sort_keys=True, default=str)
        result_hash = hashlib.sha256(result_json.encode()).hexdigest()

        # Fire-and-forget enrichment completion event
        emitter = http_request.app.state.emitter
        await emitter.emit_enrichment_completed(
            tenant_id=request.tenant_id,
            entity_id=result.get("entity_id", "unknown"),
            domain=result.get("domain"),
            fields=result.get("fields", {}),
            confidence=float(result.get("confidence", 0.0)),
            tokens_used=int(result.get("tokens_used", 0)),
        )

        log.info(
            "execute_completed",
            processing_ms=processing_ms,
            result_keys=list(result.keys()),
            content_hash=result_hash[:16],
        )

        return ExecuteResponse(
            success=True,
            action=request.action,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            result=result,
            processing_time_ms=processing_ms,
            content_hash=result_hash,
        )

    return router


def _build_health_router():
    from fastapi import APIRouter

    _start_time = time.monotonic()
    router = APIRouter()

    @router.get(
        "/v1/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        summary="Liveness and readiness probe",
        description=(
            "Returns engine liveness status and readiness checks for all "
            "infrastructure dependencies (PostgreSQL, Redis, spec.yaml). "
            "Returns HTTP 200 when ready, HTTP 503 when any critical check fails."
        ),
        tags=["Operations"],
    )
    async def health(http_request: Request) -> HealthResponse:
        settings: Settings = get_settings()
        checks: dict[str, str] = {}
        all_ready = True

        # PostgreSQL check
        try:
            import sqlalchemy
            async with pg_store.get_session() as session:
                await session.execute(sqlalchemy.text("SELECT 1"))
            checks["postgresql"] = "ok"
        except Exception as exc:
            checks["postgresql"] = f"error: {exc}"
            all_ready = False

        # Redis / event emitter check
        try:
            emitter = http_request.app.state.emitter
            if hasattr(emitter, "_backend") and hasattr(emitter._backend, "_client"):
                await emitter._backend._client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            # Redis is non-critical (fire-and-forget) — do not fail readiness

        # Spec check
        try:
            spec = http_request.app.state.spec
            domain_count = len(spec.get("domains", {}))
            checks["spec"] = f"ok ({domain_count} domains)"
        except Exception as exc:
            checks["spec"] = f"error: {exc}"
            all_ready = False

        # Action router check
        try:
            action_router = http_request.app.state.action_router
            handler_count = len(action_router.handler_map)
            checks["action_router"] = f"ok ({handler_count} handlers)"
        except Exception as exc:
            checks["action_router"] = f"error: {exc}"
            all_ready = False

        uptime = time.monotonic() - _start_time
        response = HealthResponse(
            status="ready" if all_ready else "degraded",
            version=settings.version,
            environment=settings.environment,
            checks=checks,
            uptime_seconds=round(uptime, 2),
        )

        if not all_ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=response.model_dump(),
            )

        return response

    return router


def _build_converge_router():
    from fastapi import APIRouter

    router = APIRouter()

    @router.post(
        "/v1/converge",
        status_code=status.HTTP_200_OK,
        summary="Multi-pass convergence loop",
        description=(
            "Triggers the multi-pass enrichment convergence loop for a single entity. "
            "Runs up to max_passes Bayesian update cycles, checkpointing after each pass, "
            "terminating when posterior_score >= 0.85 or budget is exhausted. "
            "Returns final EnrichResponse with convergence metadata."
        ),
        tags=["Engine"],
    )
    async def converge(request: ConvergeRequest, http_request: Request) -> dict[str, Any]:
        log = structlog.get_logger("converge").bind(
            tenant_id=request.tenant_id,
            entity_id=request.entity_id,
            domain=request.domain,
            correlation_id=request.correlation_id,
        )
        log.info("converge_request_received", max_passes=request.max_passes)

        convergence_router: ConvergenceRouter = http_request.app.state.convergence_router

        t_start = time.monotonic()
        try:
            result = await convergence_router.run(
                tenant_id=request.tenant_id,
                entity_id=request.entity_id,
                object_type=request.object_type,
                domain=request.domain,
                initial_payload=request.initial_payload,
                max_passes=request.max_passes,
                max_budget_tokens=request.max_budget_tokens,
            )
        except Exception as exc:
            processing_ms = int((time.monotonic() - t_start) * 1000)
            log.error("converge_error", error=str(exc), processing_ms=processing_ms, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Convergence loop failed: {exc}",
            )

        processing_ms = int((time.monotonic() - t_start) * 1000)

        # Emit convergence completion event
        emitter = http_request.app.state.emitter
        await emitter.emit_convergence_completed(
            tenant_id=request.tenant_id,
            entity_id=request.entity_id,
            domain=request.domain,
            pass_count=result.get("pass_count", 0),
            convergence_reason=result.get("convergence_reason", "unknown"),
            total_tokens=result.get("total_tokens", 0),
            total_cost_usd=float(result.get("total_cost_usd", 0.0)),
        )

        log.info(
            "converge_completed",
            pass_count=result.get("pass_count"),
            convergence_reason=result.get("convergence_reason"),
            processing_ms=processing_ms,
        )

        return {**result, "processing_time_ms": processing_ms}

    return router


def _build_fields_router():
    from fastapi import APIRouter

    router = APIRouter()

    @router.get(
        "/v1/fields",
        status_code=status.HTTP_200_OK,
        summary="Domain field schema introspection",
        description=(
            "Returns the field schema for a given domain as defined in spec.yaml. "
            "Includes field types, required flags, confidence thresholds, "
            "and optionally scoring dimensions and GATE specs. "
            "Used by clients to validate payloads before submitting to /v1/execute."
        ),
        tags=["Schema"],
    )
    async def get_fields(
        domain: str,
        object_type: str | None = None,
        include_scoring_dims: bool = False,
        include_gate_specs: bool = False,
        http_request: Request = None,
    ) -> dict[str, Any]:
        fields_router: FieldsRouter = http_request.app.state.fields_router

        try:
            result = await fields_router.get_fields(
                domain=domain,
                object_type=object_type,
                include_scoring_dims=include_scoring_dims,
                include_gate_specs=include_gate_specs,
            )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain '{domain}' not found in spec. "
                       f"Available domains: {fields_router.available_domains}",
            )

        return result

    return router


def _build_discover_router():
    from fastapi import APIRouter

    router = APIRouter()

    @router.post(
        "/v1/discover",
        status_code=status.HTTP_200_OK,
        summary="Batch field discovery for schema evolution",
        description=(
            "Analyzes a batch of enrichment payloads to discover emergent fields "
            "not present in spec.yaml. Outputs schema proposals with fill rate, "
            "average confidence, value distribution, and suggested GATE/scoring specs. "
            "Proposals are persisted and routed to human approval workflow."
        ),
        tags=["Schema"],
    )
    async def discover(request: DiscoverRequest, http_request: Request) -> dict[str, Any]:
        log = structlog.get_logger("discover").bind(
            tenant_id=request.tenant_id,
            domain=request.domain,
            batch_run_id=request.batch_run_id,
            sample_count=len(request.sample_payloads),
        )
        log.info("discover_request_received")

        discover_router: DiscoverRouter = http_request.app.state.discover_router

        t_start = time.monotonic()
        try:
            result = await discover_router.run(
                tenant_id=request.tenant_id,
                domain=request.domain,
                batch_run_id=request.batch_run_id,
                sample_payloads=request.sample_payloads,
                min_fill_rate=request.min_fill_rate,
                min_avg_confidence=request.min_avg_confidence,
            )
        except Exception as exc:
            processing_ms = int((time.monotonic() - t_start) * 1000)
            log.error("discover_error", error=str(exc), processing_ms=processing_ms, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Field discovery failed: {exc}",
            )

        processing_ms = int((time.monotonic() - t_start) * 1000)
        proposals_count = len(result.get("proposals", []))

        # Emit schema proposed event
        emitter = http_request.app.state.emitter
        await emitter.emit_schema_proposed(
            tenant_id=request.tenant_id,
            domain=request.domain,
            batch_run_id=request.batch_run_id,
            proposals_count=proposals_count,
        )

        log.info(
            "discover_completed",
            proposals_count=proposals_count,
            processing_ms=processing_ms,
        )

        return {**result, "processing_time_ms": processing_ms}

    return router


# ── Exception handlers ────────────────────────────────────────────────────────


async def _validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    logger.warning("validation_error", errors=exc.errors(), path=str(request.url.path))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Request validation failed",
            "detail": exc.errors(),
        },
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=str(request.url.path),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal engine error",
            "detail": str(exc) if get_settings().environment != "production" else "Internal error",
        },
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_spec(spec_path: str) -> dict[str, Any]:
    """
    Load and validate spec.yaml from the given path.

    Raises RuntimeError with a clear message if:
    - File does not exist
    - File is not valid YAML
    - File is missing required top-level keys

    Required top-level keys: domains, actions
    """
    import os

    if not os.path.exists(spec_path):
        raise RuntimeError(
            f"spec.yaml not found at '{spec_path}'. "
            "Set SPEC_PATH environment variable to the correct location."
        )

    with open(spec_path, "r", encoding="utf-8") as f:
        try:
            spec = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise RuntimeError(f"spec.yaml parse error: {exc}") from exc

    if not isinstance(spec, dict):
        raise RuntimeError("spec.yaml must be a YAML mapping at the top level.")

    required_keys = {"domains", "actions"}
    missing = required_keys - set(spec.keys())
    if missing:
        raise RuntimeError(
            f"spec.yaml is missing required top-level keys: {sorted(missing)}. "
            f"Present keys: {sorted(spec.keys())}"
        )

    return spec


def _configure_logging(settings: Settings) -> None:
    """
    Configure structlog for the application.

    Production: JSON renderer for log aggregation pipelines.
    Development: ConsoleRenderer for human-readable terminal output.

    Processors:
    - add_log_level: always include log level in every event
    - add_logger_name: always include logger name for tracing
    - TimeStamper(iso): ISO-8601 timestamps
    - StackInfoRenderer: include stack info for errors
    - ExceptionRenderer: serialize exceptions into JSON
    - JSONRenderer / ConsoleRenderer: environment-dependent final renderer
    """
    import logging

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(
        logging.DEBUG if settings.environment == "development" else logging.INFO
    )
