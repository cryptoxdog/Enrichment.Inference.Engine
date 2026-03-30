"""
SCORE Service — Score Explainer
revopsos-score-engine

Produces human-readable, fully transparent score explanations.
Every score comes with a breakdown showing which fields contributed,
which were missing, and the confidence of each input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from score_models import (
    FieldContribution,
    MissingField,
    ScoreRecord,
)

# ── Explanation Models ────────────────────────────────────────


@dataclass
class FieldExplanation:
    """Human-readable explanation of a single field contribution."""

    field_name: str
    dimension: str
    raw_value: Any
    contribution_pct: float
    confidence: float
    source: str
    match_detail: str
    impact_rank: int = 0

    @property
    def summary(self) -> str:
        return (
            f"{self.field_name}: contributed {self.contribution_pct:.0%} to {self.dimension} "
            f"(value={self.raw_value}, confidence={self.confidence:.2f}, source={self.source})"
        )


@dataclass
class MissingFieldExplanation:
    """Human-readable explanation of a missing field impact."""

    field_name: str
    dimension: str
    estimated_impact: float
    is_gate_critical: bool
    recommendation: str
    priority_rank: int = 0

    @property
    def summary(self) -> str:
        critical = " [GATE-CRITICAL]" if self.is_gate_critical else ""
        return (
            f"{self.field_name}: missing from {self.dimension}{critical}, "
            f"estimated +{self.estimated_impact:.0%} if present -> {self.recommendation}"
        )


@dataclass
class DimensionExplanation:
    """Full explanation for a single dimension."""

    dimension: str
    score: float
    weight: float
    weighted_contribution: float
    confidence: float
    coverage: float
    field_explanations: list[FieldExplanation] = field(default_factory=list)
    missing_explanations: list[MissingFieldExplanation] = field(default_factory=list)
    decay_factor: float = 1.0
    decayed_score: float | None = None
    narrative: str = ""

    @property
    def field_count(self) -> int:
        return len(self.field_explanations)

    @property
    def missing_count(self) -> int:
        return len(self.missing_explanations)


@dataclass
class ScoreExplanation:
    """Complete score explanation for an entity."""

    entity_id: str
    domain: str
    composite_score: float
    tier: str
    composite_confidence: float
    dimension_explanations: list[DimensionExplanation] = field(default_factory=list)
    top_contributors: list[FieldExplanation] = field(default_factory=list)
    top_missing: list[MissingFieldExplanation] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    gate_penalty_applied: bool = False
    narrative: str = ""
    scored_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "composite_score": round(self.composite_score, 4),
            "tier": self.tier,
            "composite_confidence": round(self.composite_confidence, 4),
            "gate_penalty_applied": self.gate_penalty_applied,
            "dimensions": [
                {
                    "dimension": de.dimension,
                    "score": round(de.score, 4),
                    "weight": round(de.weight, 4),
                    "weighted_contribution": round(de.weighted_contribution, 4),
                    "confidence": round(de.confidence, 4),
                    "coverage": round(de.coverage, 4),
                    "decay_factor": round(de.decay_factor, 4),
                    "fields_present": de.field_count,
                    "fields_missing": de.missing_count,
                    "narrative": de.narrative,
                }
                for de in self.dimension_explanations
            ],
            "top_contributors": [
                {
                    "field": tc.field_name,
                    "dimension": tc.dimension,
                    "contribution": round(tc.contribution_pct, 4),
                    "confidence": round(tc.confidence, 4),
                    "value": tc.raw_value,
                }
                for tc in self.top_contributors
            ],
            "top_missing": [
                {
                    "field": tm.field_name,
                    "dimension": tm.dimension,
                    "estimated_impact": round(tm.estimated_impact, 4),
                    "gate_critical": tm.is_gate_critical,
                    "recommendation": tm.recommendation,
                }
                for tm in self.top_missing
            ],
            "recommendations": self.recommendations,
            "narrative": self.narrative,
            "scored_at": self.scored_at.isoformat(),
        }


# ── Narrative Generation ──────────────────────────────────────

_TIER_DESCRIPTIONS: dict[str, str] = {
    "hot": "a strong match ready for immediate engagement",
    "warm": "a good prospect with some gaps to address",
    "cool": "a potential fit that needs more data and signals",
    "cold": "an early-stage entity with significant data gaps",
    "disqualified": "not scoreable -- critical data is missing",
}

_DIMENSION_DESCRIPTIONS: dict[str, str] = {
    "fit": "how well this entity matches your Ideal Customer Profile",
    "intent": "buying signals detected from engagement patterns",
    "engagement": "interaction level across channels",
    "readiness": "deal stage and data completeness for action",
    "graph_affinity": "similarity to successful entities in your graph",
}


def _generate_dimension_narrative(dim_exp: DimensionExplanation) -> str:
    """Generate a human-readable narrative for a dimension."""
    dim_desc = _DIMENSION_DESCRIPTIONS.get(dim_exp.dimension, dim_exp.dimension)
    parts: list[str] = []

    if dim_exp.score >= 0.80:
        parts.append(f"Strong {dim_exp.dimension} ({dim_exp.score:.0%}): {dim_desc}.")
    elif dim_exp.score >= 0.50:
        parts.append(f"Moderate {dim_exp.dimension} ({dim_exp.score:.0%}): {dim_desc}.")
    elif dim_exp.score > 0:
        parts.append(f"Weak {dim_exp.dimension} ({dim_exp.score:.0%}): {dim_desc}.")
    else:
        parts.append(f"No {dim_exp.dimension} score: {dim_desc} -- no data available.")

    if dim_exp.field_explanations:
        top = sorted(dim_exp.field_explanations, key=lambda x: x.contribution_pct, reverse=True)[:3]
        names = ", ".join(f.field_name for f in top)
        parts.append(f"Top contributors: {names}.")

    if dim_exp.missing_explanations:
        gate_missing = [m for m in dim_exp.missing_explanations if m.is_gate_critical]
        if gate_missing:
            names = ", ".join(m.field_name for m in gate_missing)
            parts.append(f"GATE-CRITICAL missing: {names}.")
        elif len(dim_exp.missing_explanations) <= 3:
            names = ", ".join(m.field_name for m in dim_exp.missing_explanations)
            parts.append(f"Missing: {names}.")
        else:
            parts.append(f"{len(dim_exp.missing_explanations)} fields missing.")

    if dim_exp.decay_factor < 0.90:
        parts.append(f"Score has decayed to {dim_exp.decay_factor:.0%} of original.")

    return " ".join(parts)


def _generate_overall_narrative(explanation: ScoreExplanation) -> str:
    """Generate the top-level narrative summary."""
    tier_desc = _TIER_DESCRIPTIONS.get(explanation.tier, "an entity")
    parts: list[str] = [
        f"This entity scored {explanation.composite_score:.0%} (tier: {explanation.tier.upper()}) "
        f"-- {tier_desc}."
    ]

    if explanation.gate_penalty_applied:
        parts.append(
            "Score is capped because gate-critical fields are missing. "
            "Fill these first for the biggest score improvement."
        )

    if explanation.top_contributors:
        top = explanation.top_contributors[0]
        parts.append(
            f"Strongest signal: {top.field_name} "
            f"(contributed {top.contribution_pct:.0%} to {top.dimension})."
        )

    if explanation.top_missing:
        top_m = explanation.top_missing[0]
        parts.append(
            f"Biggest gap: {top_m.field_name} "
            f"(estimated +{top_m.estimated_impact:.0%} to {top_m.dimension})."
        )

    return " ".join(parts)


# ── Recommendation Engine ─────────────────────────────────────

_RECOMMENDATION_TEMPLATES: dict[str, str] = {
    "enrich_field": "Enrich '{field}' to improve {dimension} score by ~{impact:.0%}",
    "verify_field": "Verify '{field}' -- low confidence ({confidence:.0%}) in {dimension}",
    "capture_signal": "Connect signal sources to populate {dimension} scoring",
    "re_score": "Re-score after enrichment to update {dimension}",
    "manual_review": "Manual review recommended for '{field}' in {dimension}",
}


def _generate_recommendations(
    missing: list[MissingFieldExplanation],
    low_confidence_fields: list[FieldExplanation],
    max_recommendations: int = 5,
) -> list[str]:
    """Generate prioritized action recommendations."""
    recs: list[str] = []

    gate_missing = sorted(
        [m for m in missing if m.is_gate_critical],
        key=lambda m: m.estimated_impact,
        reverse=True,
    )
    for m in gate_missing[:2]:
        recs.append(
            f"[CRITICAL] Enrich '{m.field_name}' -- gate-critical for {m.dimension}, "
            f"estimated +{m.estimated_impact:.0%} score improvement"
        )

    high_impact_missing = sorted(
        [m for m in missing if not m.is_gate_critical and m.estimated_impact >= 0.10],
        key=lambda m: m.estimated_impact,
        reverse=True,
    )
    for m in high_impact_missing[:2]:
        template = _RECOMMENDATION_TEMPLATES.get(
            m.recommendation, "Address '{field}' in {dimension}"
        )
        recs.append(
            template.format(
                field=m.field_name,
                dimension=m.dimension,
                impact=m.estimated_impact,
                confidence=0.0,
            )
        )

    low_conf = sorted(low_confidence_fields, key=lambda f: f.confidence)
    for lf in low_conf[:1]:
        if lf.confidence < 0.50:
            recs.append(
                f"Verify '{lf.field_name}' -- currently at {lf.confidence:.0%} confidence, "
                f"re-enrichment could improve {lf.dimension} reliability"
            )

    no_signal_dims = {m.dimension for m in missing if m.recommendation == "capture_signal"}
    for dim in sorted(no_signal_dims)[:1]:
        recs.append(f"Connect signal sources (email, website, CRM) to enable {dim} scoring")

    return recs[:max_recommendations]


# ── Core Explainer ────────────────────────────────────────────


class ScoreExplainer:
    """
    Produces fully transparent, human-readable score explanations.

    Every score record is expanded into dimension-level breakdowns,
    field-level contributions, missing field impact estimates, and
    prioritized recommendations for score improvement.
    """

    def __init__(self, max_top_fields: int = 5, max_recommendations: int = 5):
        self._max_top_fields = max_top_fields
        self._max_recommendations = max_recommendations

    def explain(
        self,
        record: ScoreRecord,
    ) -> ScoreExplanation:
        """Generate full explanation for a ScoreRecord."""
        dim_explanations: list[DimensionExplanation] = []
        all_field_explanations: list[FieldExplanation] = []
        all_missing_explanations: list[MissingFieldExplanation] = []
        low_confidence_fields: list[FieldExplanation] = []

        for dim, ds in record.dimension_scores.items():
            field_exps = self._explain_fields(ds.field_contributions)
            missing_exps = self._explain_missing(ds.missing_fields)

            weighted_contribution = ds.score * ds.weight
            dim_exp = DimensionExplanation(
                dimension=dim.value,
                score=ds.score,
                weight=ds.weight,
                weighted_contribution=weighted_contribution,
                confidence=ds.confidence,
                coverage=ds.coverage,
                field_explanations=field_exps,
                missing_explanations=missing_exps,
                decay_factor=ds.decay_factor,
                decayed_score=ds.decayed_score,
            )
            dim_exp.narrative = _generate_dimension_narrative(dim_exp)
            dim_explanations.append(dim_exp)

            all_field_explanations.extend(field_exps)
            all_missing_explanations.extend(missing_exps)
            low_confidence_fields.extend(f for f in field_exps if f.confidence < 0.50)

        all_field_explanations.sort(key=lambda f: f.contribution_pct, reverse=True)
        for rank, fe in enumerate(all_field_explanations, 1):
            fe.impact_rank = rank
        top_contributors = all_field_explanations[: self._max_top_fields]

        all_missing_explanations.sort(
            key=lambda m: (m.is_gate_critical, m.estimated_impact), reverse=True
        )
        for rank, me in enumerate(all_missing_explanations, 1):
            me.priority_rank = rank
        top_missing = all_missing_explanations[: self._max_top_fields]

        gate_penalty = any(m.is_gate_critical for m in record.missing_fields)
        recommendations = _generate_recommendations(
            all_missing_explanations, low_confidence_fields, self._max_recommendations
        )

        explanation = ScoreExplanation(
            entity_id=record.entity_id,
            domain=record.domain,
            composite_score=record.composite_score,
            tier=record.tier.value,
            composite_confidence=record.composite_confidence,
            dimension_explanations=dim_explanations,
            top_contributors=top_contributors,
            top_missing=top_missing,
            recommendations=recommendations,
            gate_penalty_applied=gate_penalty,
            scored_at=record.scored_at,
        )
        explanation.narrative = _generate_overall_narrative(explanation)
        return explanation

    def explain_batch(
        self,
        records: list[ScoreRecord],
    ) -> list[ScoreExplanation]:
        """Generate explanations for a batch of score records."""
        return [self.explain(r) for r in records]

    def compare_scores(
        self,
        before: ScoreRecord,
        after: ScoreRecord,
    ) -> dict[str, Any]:
        """Compare two score records for the same entity (before/after enrichment)."""
        exp_before = self.explain(before)
        exp_after = self.explain(after)

        dimension_deltas: dict[str, dict[str, float]] = {}
        for dim_after in exp_after.dimension_explanations:
            dim_name = dim_after.dimension
            dim_before = next(
                (d for d in exp_before.dimension_explanations if d.dimension == dim_name),
                None,
            )
            before_score = dim_before.score if dim_before else 0.0
            dimension_deltas[dim_name] = {
                "before": round(before_score, 4),
                "after": round(dim_after.score, 4),
                "delta": round(dim_after.score - before_score, 4),
            }

        resolved_fields = {m.field_name for m in before.missing_fields} - {
            m.field_name for m in after.missing_fields
        }
        new_missing = {m.field_name for m in after.missing_fields} - {
            m.field_name for m in before.missing_fields
        }

        return {
            "entity_id": after.entity_id,
            "composite_before": round(before.composite_score, 4),
            "composite_after": round(after.composite_score, 4),
            "composite_delta": round(after.composite_score - before.composite_score, 4),
            "tier_before": before.tier.value,
            "tier_after": after.tier.value,
            "tier_changed": before.tier != after.tier,
            "dimension_deltas": dimension_deltas,
            "fields_resolved": sorted(resolved_fields),
            "fields_newly_missing": sorted(new_missing),
            "missing_before": len(before.missing_fields),
            "missing_after": len(after.missing_fields),
        }

    def _explain_fields(self, contributions: list[FieldContribution]) -> list[FieldExplanation]:
        """Convert FieldContribution models to FieldExplanation dataclasses."""
        return [
            FieldExplanation(
                field_name=fc.field_name,
                dimension=fc.dimension.value,
                raw_value=fc.raw_value,
                contribution_pct=fc.contribution,
                confidence=fc.confidence,
                source=fc.source.value,
                match_detail=fc.match_detail,
            )
            for fc in contributions
        ]

    def _explain_missing(self, missing: list[MissingField]) -> list[MissingFieldExplanation]:
        """Convert MissingField models to MissingFieldExplanation dataclasses."""
        return [
            MissingFieldExplanation(
                field_name=mf.field_name,
                dimension=mf.dimension.value,
                estimated_impact=mf.impact_estimate,
                is_gate_critical=mf.is_gate_critical,
                recommendation=mf.recommendation.value,
            )
            for mf in missing
        ]
