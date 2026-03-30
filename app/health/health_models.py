"""
HEALTH service data models.

Canonical Pydantic models for entity health, field health, CRM-wide health,
and the re-enrichment trigger protocol. Consumed by health_assessor,
health_field_analyzer, health_triggers, and the health API layer.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# ─── Enums ────────────────────────────────────────────────────


class HealthAction(StrEnum):
    RE_ENRICH = "re_enrich"
    VERIFY_FIELD = "verify_field"
    RESOLVE_CONFLICT = "resolve_conflict"
    FILL_MISSING = "fill_missing"
    REFRESH_STALE = "refresh_stale"
    FLAG_OUTLIER = "flag_outlier"


class TriggerReason(StrEnum):
    STALENESS = "staleness"
    LOW_CONFIDENCE = "low_confidence"
    LOW_COMPLETENESS = "low_completeness"
    INCONSISTENCY = "inconsistency"
    COMPOSITE_BELOW_THRESHOLD = "composite_below_threshold"
    SCORE_CONFIDENCE_DROP = "score_confidence_drop"
    GATE_FIELD_MISSING = "gate_field_missing"


class AssessmentScope(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"
    ENTITY = "entity"
    FIELD = "field"


# ─── Field-Level Health ──────────────────────────────────────


class FieldHealth(BaseModel):
    """Aggregate health metrics for a single field across all entities."""

    field_name: str
    fill_rate: float = Field(ge=0.0, le=1.0, description="Fraction of entities with non-null value")
    avg_confidence: float = Field(ge=0.0, le=1.0, description="Mean enrichment confidence")
    min_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    max_confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    staleness_p50_days: float = Field(ge=0.0, description="Median days since last enrichment")
    staleness_p90_days: float = Field(ge=0.0, default=0.0)
    outlier_count: int = Field(ge=0, default=0)
    total_entities: int = Field(ge=0, default=0)
    value_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Top value counts for categorical; histogram bins for numeric",
    )
    is_gate_critical: bool = Field(default=False, description="Field used in a WHERE gate")
    is_scoring_dimension: bool = Field(default=False, description="Field used in scoring")

    @property
    def health_score(self) -> float:
        fill_weight = 0.40
        conf_weight = 0.35
        stale_weight = 0.25
        stale_factor = max(0.0, 1.0 - (self.staleness_p50_days / 180.0))
        return (
            self.fill_rate * fill_weight
            + self.avg_confidence * conf_weight
            + stale_factor * stale_weight
        )


# ─── Entity-Level Health ─────────────────────────────────────


class RecommendedAction(BaseModel):
    action: HealthAction
    field_name: str | None = None
    reason: str
    priority: float = Field(ge=0.0, le=1.0, description="Higher = more urgent")


class EntityHealth(BaseModel):
    """Per-entity health assessment."""

    entity_id: str
    domain: str
    completeness: float = Field(ge=0.0, le=1.0, description="Fraction of expected fields filled")
    freshness: float = Field(ge=0.0, le=1.0, description="Decay-weighted recency")
    confidence: float = Field(ge=0.0, le=1.0, description="Avg field confidence")
    consistency: float = Field(ge=0.0, le=1.0, description="Enriched vs CRM agreement ratio")
    composite_health: float = Field(ge=0.0, le=1.0)
    last_enriched_at: datetime | None = None
    last_assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    field_count_total: int = Field(ge=0, default=0)
    field_count_filled: int = Field(ge=0, default=0)
    field_count_stale: int = Field(ge=0, default=0)
    field_count_low_confidence: int = Field(ge=0, default=0)
    gate_fields_missing: list[str] = Field(default_factory=list)
    scoring_fields_missing: list[str] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.composite_health >= 0.70

    @property
    def needs_enrichment(self) -> bool:
        return (
            self.composite_health < 0.50
            or len(self.gate_fields_missing) > 0
            or self.freshness < 0.30
        )


# ─── CRM-Wide Health ─────────────────────────────────────────


class CRMHealth(BaseModel):
    """Aggregate health across the entire CRM entity base."""

    domain: str
    total_entities: int = Field(ge=0)
    ai_readiness_score: float = Field(ge=0.0, le=1.0)
    avg_completeness: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_freshness: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    field_health: list[FieldHealth] = Field(default_factory=list)
    enrichment_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    graph_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    entities_below_threshold: int = Field(ge=0, default=0)
    entities_needing_enrichment: int = Field(ge=0, default=0)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_ai_ready(self) -> bool:
        return self.ai_readiness_score >= 0.70


# ─── Re-Enrichment Trigger ──────────────────────────────────


class EnrichmentTrigger(BaseModel):
    """Signal from HEALTH → ENRICH to queue an entity for re-enrichment."""

    trigger_id: UUID = Field(default_factory=uuid4)
    entity_id: str
    domain: str
    reason: TriggerReason
    priority: float = Field(ge=0.0, le=1.0, description="Scheduling priority")
    target_fields: list[str] = Field(
        default_factory=list, description="Specific fields to re-enrich; empty = full re-enrich"
    )
    current_health: float = Field(
        ge=0.0, le=1.0, description="Entity composite_health at trigger time"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Assessment Request/Response ─────────────────────────────


class AssessmentConfig(BaseModel):
    """Configuration for a health assessment run."""

    domain: str
    scope: AssessmentScope = AssessmentScope.FULL
    entity_ids: list[str] | None = None
    health_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    staleness_days: float = Field(default=30.0, ge=1.0)
    confidence_floor: float = Field(default=0.50, ge=0.0, le=1.0)
    auto_trigger_enrichment: bool = Field(default=True)
    weights: HealthWeights | None = None


class HealthWeights(BaseModel):
    """Customizable weights for composite health calculation."""

    completeness: float = Field(default=0.30, ge=0.0, le=1.0)
    freshness: float = Field(default=0.25, ge=0.0, le=1.0)
    confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    consistency: float = Field(default=0.20, ge=0.0, le=1.0)

    @field_validator("consistency")
    @classmethod
    def weights_sum_to_one(cls, v: float, info: Any) -> float:
        total = (
            (info.data.get("completeness") or 0.30)
            + (info.data.get("freshness") or 0.25)
            + (info.data.get("confidence") or 0.25)
            + v
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        return v


class AssessmentResult(BaseModel):
    """Output of a full or incremental health assessment run."""

    assessment_id: UUID = Field(default_factory=uuid4)
    config: AssessmentConfig
    crm_health: CRMHealth
    entity_health_summary: EntityHealthSummary
    triggers_generated: list[EnrichmentTrigger] = Field(default_factory=list)
    duration_ms: int = Field(ge=0, default=0)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EntityHealthSummary(BaseModel):
    """Aggregate stats without shipping every EntityHealth object."""

    total_assessed: int = Field(ge=0, default=0)
    healthy_count: int = Field(ge=0, default=0)
    unhealthy_count: int = Field(ge=0, default=0)
    needs_enrichment_count: int = Field(ge=0, default=0)
    avg_composite_health: float = Field(ge=0.0, le=1.0, default=0.0)
    min_composite_health: float = Field(ge=0.0, le=1.0, default=0.0)
    max_composite_health: float = Field(ge=0.0, le=1.0, default=1.0)
    health_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Bucketed: excellent(>0.9), good(0.7-0.9), fair(0.5-0.7), poor(<0.5)",
    )


# ─── Freshness Decay Utility ─────────────────────────────────


def compute_freshness(
    last_enriched_at: datetime | None,
    half_life_days: float = 30.0,
    now: datetime | None = None,
) -> float:
    """Exponential decay freshness score.

    Returns 1.0 immediately after enrichment, 0.5 at half_life_days,
    approaches 0.0 as age → ∞.
    """
    if last_enriched_at is None:
        return 0.0
    now = now or datetime.now(UTC)
    if last_enriched_at.tzinfo is None:
        last_enriched_at = last_enriched_at.replace(tzinfo=UTC)
    age_days = max(0.0, (now - last_enriched_at).total_seconds() / 86400.0)
    if half_life_days <= 0:
        return 0.0
    return math.exp(-0.693147 * age_days / half_life_days)


# ─── Composite Health Utility ─────────────────────────────────


def compute_composite_health(
    completeness: float,
    freshness: float,
    confidence: float,
    consistency: float,
    weights: HealthWeights | None = None,
) -> float:
    """Weighted composite health score."""
    w = weights or HealthWeights()
    raw = (
        completeness * w.completeness
        + freshness * w.freshness
        + confidence * w.confidence
        + consistency * w.consistency
    )
    return max(0.0, min(1.0, raw))


# ─── AI Readiness Score ──────────────────────────────────────


def compute_ai_readiness(
    avg_completeness: float,
    avg_freshness: float,
    avg_confidence: float,
    enrichment_coverage: float,
    graph_coverage: float,
    gate_field_fill_rate: float = 1.0,
) -> float:
    """CRM-wide AI readiness score.

    Weighted composite with a gate-field penalty: if gate-critical fields
    have <80% fill rate, the score is capped at 0.50 regardless of other
    dimensions.
    """
    raw = (
        avg_completeness * 0.25
        + avg_freshness * 0.15
        + avg_confidence * 0.25
        + enrichment_coverage * 0.20
        + graph_coverage * 0.15
    )
    if gate_field_fill_rate < 0.80:
        raw = min(raw, 0.50)
    return max(0.0, min(1.0, raw))
