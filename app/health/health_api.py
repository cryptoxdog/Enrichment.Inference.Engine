"""
HEALTH service API layer.

FastAPI router exposing health assessment, field diagnostics,
CRM-wide health, and trigger management endpoints.
Constellation node: revopsos-health-monitor.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .health_models import (
    AssessmentConfig,
    AssessmentScope,
    FieldHealth,
    HealthWeights,
)
from .health_assessor import HealthAssessor, EntityDataStore, DomainSchema
from .health_field_analyzer import run_field_diagnostic
from .health_triggers import (
    TriggerEngine,
)


# ─── Module-Level State (configured at startup) ──────────────

_assessor: HealthAssessor | None = None
_trigger_engine: TriggerEngine | None = None
_data_store: EntityDataStore | None = None
_domain_schemas: dict[str, DomainSchema] = {}


def configure(
    data_store: EntityDataStore,
    domain_schemas: dict[str, DomainSchema],
    trigger_engine: TriggerEngine,
) -> None:
    """Called at application startup to inject dependencies."""
    global _assessor, _trigger_engine, _data_store, _domain_schemas
    _data_store = data_store
    _domain_schemas = domain_schemas
    _trigger_engine = trigger_engine


def _get_assessor(domain: str, config: AssessmentConfig | None = None) -> HealthAssessor:
    if _data_store is None:
        raise RuntimeError("HEALTH service not configured — call configure() at startup")
    schema = _domain_schemas.get(domain)
    if schema is None:
        raise ValueError(f"No domain schema registered for '{domain}'")
    return HealthAssessor(_data_store, schema, config)


def _get_trigger_engine() -> TriggerEngine:
    if _trigger_engine is None:
        raise RuntimeError("TriggerEngine not configured — call configure() at startup")
    return _trigger_engine


# ─── Request / Response Bodies ────────────────────────────────


class AssessEntityRequest(BaseModel):
    entity_id: str
    domain: str
    weights: HealthWeights | None = None


class AssessCRMRequest(BaseModel):
    domain: str
    scope: AssessmentScope = AssessmentScope.FULL
    entity_ids: list[str] | None = None
    health_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    staleness_days: float = Field(default=30.0, ge=1.0)
    confidence_floor: float = Field(default=0.50, ge=0.0, le=1.0)
    auto_trigger_enrichment: bool = True
    weights: HealthWeights | None = None


class AssessCRMResponse(BaseModel):
    assessment_id: str
    crm_health: dict[str, Any]
    entity_summary: dict[str, Any]
    triggers_generated: int
    duration_ms: int


class FieldDiagnosticRequest(BaseModel):
    domain: str
    field_name: str


class DispatchRequest(BaseModel):
    domain: str


class TriggerStatusResponse(BaseModel):
    domain: str
    pending_count: int
    dispatched_last_hour: int
    hourly_capacity: int
    remaining_capacity: int


# ─── Endpoint Handlers ───────────────────────────────────────


def assess_entity(request: AssessEntityRequest) -> dict[str, Any]:
    """GET /v1/health/entity/{entity_id}

    Assess a single entity's health.
    """
    config = AssessmentConfig(
        domain=request.domain,
        scope=AssessmentScope.ENTITY,
        entity_ids=[request.entity_id],
        weights=request.weights,
    )
    assessor = _get_assessor(request.domain, config)

    if _data_store is None:
        raise RuntimeError("Data store not configured")
    record = _data_store.get_entity(request.entity_id)
    if record is None:
        raise ValueError(f"Entity '{request.entity_id}' not found")

    eh = assessor.assess_entity(record)
    return eh.model_dump(mode="json")


def assess_crm(request: AssessCRMRequest) -> AssessCRMResponse:
    """POST /v1/health/assess

    Run full CRM health assessment. Optionally auto-triggers re-enrichment
    for unhealthy entities.
    """
    config = AssessmentConfig(
        domain=request.domain,
        scope=request.scope,
        entity_ids=request.entity_ids,
        health_threshold=request.health_threshold,
        staleness_days=request.staleness_days,
        confidence_floor=request.confidence_floor,
        auto_trigger_enrichment=request.auto_trigger_enrichment,
        weights=request.weights,
    )
    assessor = _get_assessor(request.domain, config)
    result = assessor.assess_full_crm()

    if request.auto_trigger_enrichment and result.triggers_generated:
        engine = _get_trigger_engine()
        engine.ingest_triggers(result.triggers_generated)

    return AssessCRMResponse(
        assessment_id=str(result.assessment_id),
        crm_health=result.crm_health.model_dump(mode="json"),
        entity_summary=result.entity_health_summary.model_dump(mode="json"),
        triggers_generated=len(result.triggers_generated),
        duration_ms=result.duration_ms,
    )


def get_crm_health(domain: str) -> dict[str, Any]:
    """GET /v1/health/crm

    Return cached or freshly computed CRM-wide health.
    For production, this would read from a materialized view / cache.
    Here it runs a lightweight assessment.
    """
    config = AssessmentConfig(domain=domain)
    assessor = _get_assessor(domain, config)
    result = assessor.assess_full_crm()
    return result.crm_health.model_dump(mode="json")


def get_field_health(domain: str) -> list[dict[str, Any]]:
    """GET /v1/health/fields

    Return field-level health metrics for all expected fields in the domain.
    """
    config = AssessmentConfig(domain=domain)
    assessor = _get_assessor(domain, config)
    result = assessor.assess_full_crm()
    return [fh.model_dump(mode="json") for fh in result.crm_health.field_health]


def get_field_diagnostic(request: FieldDiagnosticRequest) -> dict[str, Any]:
    """GET /v1/health/fields/{field_name}/diagnostic

    Deep diagnostic for a single field: distribution, outliers, recommendations.
    """
    config = AssessmentConfig(domain=request.domain)
    assessor = _get_assessor(request.domain, config)

    if _data_store is None:
        raise RuntimeError("Data store not configured")

    entity_ids = _data_store.list_entity_ids(request.domain)
    records = _data_store.get_entities(entity_ids)

    field_values: list[tuple[str, Any]] = []
    for rec in records:
        val = rec.fields.get(request.field_name)
        field_values.append((rec.entity_id, val))

    schema = _domain_schemas.get(request.domain)
    if schema is None:
        raise ValueError(f"No domain schema for '{request.domain}'")

    fh = FieldHealth(
        field_name=request.field_name,
        fill_rate=sum(1 for _, v in field_values if v is not None) / len(field_values)
        if field_values
        else 0.0,
        avg_confidence=0.0,
        staleness_p50_days=0.0,
        is_gate_critical=request.field_name in schema.gate_fields,
        is_scoring_dimension=request.field_name in schema.scoring_fields,
        total_entities=len(records),
    )

    diagnostic = run_field_diagnostic(fh, field_values, len(records))
    return diagnostic.to_dict()


def dispatch_triggers(request: DispatchRequest) -> dict[str, Any]:
    """POST /v1/health/triggers/dispatch

    Dispatch pending re-enrichment triggers to the ENRICH service.
    """
    engine = _get_trigger_engine()
    result = engine.dispatch_batch(request.domain)
    return result.to_dict()


def get_trigger_status(domain: str) -> dict[str, Any]:
    """GET /v1/health/triggers/status

    Return current trigger queue status for a domain.
    """
    engine = _get_trigger_engine()
    status = engine.get_queue_status(domain)
    return status.to_dict()


def get_ai_readiness(domain: str) -> dict[str, Any]:
    """GET /v1/health/ai-readiness

    The Seed tier conversion endpoint. Returns the AI Readiness Score
    with a breakdown of what's contributing and what's dragging it down.
    """
    config = AssessmentConfig(domain=domain)
    assessor = _get_assessor(domain, config)
    result = assessor.assess_full_crm()
    crm = result.crm_health

    gate_fields = [fh for fh in crm.field_health if fh.is_gate_critical]
    scoring_fields = [fh for fh in crm.field_health if fh.is_scoring_dimension]
    weak_fields = sorted(crm.field_health, key=lambda f: f.health_score)[:10]

    return {
        "domain": domain,
        "ai_readiness_score": crm.ai_readiness_score,
        "is_ai_ready": crm.is_ai_ready,
        "dimensions": {
            "completeness": crm.avg_completeness,
            "freshness": crm.avg_freshness,
            "confidence": crm.avg_confidence,
            "enrichment_coverage": crm.enrichment_coverage,
            "graph_coverage": crm.graph_coverage,
        },
        "gate_fields": [
            {"name": f.field_name, "fill_rate": f.fill_rate, "health": round(f.health_score, 4)}
            for f in gate_fields
        ],
        "scoring_fields": [
            {"name": f.field_name, "fill_rate": f.fill_rate, "health": round(f.health_score, 4)}
            for f in scoring_fields
        ],
        "weakest_fields": [
            {
                "name": f.field_name,
                "fill_rate": f.fill_rate,
                "confidence": f.avg_confidence,
                "staleness_days": f.staleness_p50_days,
                "health": round(f.health_score, 4),
            }
            for f in weak_fields
        ],
        "total_entities": crm.total_entities,
        "entities_below_threshold": crm.entities_below_threshold,
        "entities_needing_enrichment": crm.entities_needing_enrichment,
        "assessed_at": crm.assessed_at.isoformat(),
    }
