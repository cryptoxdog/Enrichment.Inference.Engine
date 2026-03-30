"""
app/services/score/scorer.py
SCORE service scaffold — consumes ENRICH field_confidence + GRAPH affinity.
Computes multi-dimensional entity scores: fit, intent, engagement, readiness, graph_affinity.
Currently a STUB — wires to field_confidence output and exposes the scoring shape.
[PROPOSED] Full implementation follows graph integration (Phase 3 of roadmap).
"""

from __future__ import annotations

from app.models.field_confidence import FieldConfidenceMap
from pydantic import BaseModel, Field


class ScoreDimension(BaseModel):
    name: str
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_score: float = 0.0
    contributing_fields: list[str] = Field(default_factory=list)


class EntityScore(BaseModel):
    entity_id: str
    tenant_id: str
    domain: str
    fit_score: float = Field(ge=0.0, le=1.0, default=0.0)
    intent_score: float = Field(ge=0.0, le=1.0, default=0.0)
    engagement_score: float = Field(ge=0.0, le=1.0, default=0.0)
    readiness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    graph_affinity: float = Field(ge=0.0, le=1.0, default=0.0)
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    dimensions: list[ScoreDimension] = Field(default_factory=list)
    tier: str = "unscored"  # prospect / qualified / priority / champion
    score_version: str = "0.1.0-stub"


def compute_readiness_from_enrichment(
    entity_id: str,
    tenant_id: str,
    domain: str,
    confidence_map: FieldConfidenceMap,
    expected_fields: list[str] | None = None,
) -> EntityScore:
    """
    Compute readiness score from enrichment coverage + confidence.
    Readiness = (avg_confidence * 0.6) + (coverage_ratio * 0.4)
    This is the ENRICH-derived component — graph_affinity added by GRAPH node.
    """
    avg_conf = confidence_map.avg_confidence()
    coverage = confidence_map.coverage_ratio(expected_fields or [])
    readiness = round(avg_conf * 0.6 + coverage * 0.4, 4)

    # Tier assignment (stub — full logic in SCORE service)
    if readiness >= 0.85:
        tier = "champion"
    elif readiness >= 0.70:
        tier = "priority"
    elif readiness >= 0.55:
        tier = "qualified"
    else:
        tier = "prospect"

    return EntityScore(
        entity_id=entity_id,
        tenant_id=tenant_id,
        domain=domain,
        readiness_score=readiness,
        composite_score=readiness,  # stub: composite = readiness until other dims added
        tier=tier,
        dimensions=[
            ScoreDimension(
                name="readiness",
                raw_score=readiness,
                weight=1.0,
                weighted_score=readiness,
                contributing_fields=list(confidence_map.fields.keys()),
            )
        ],
    )
