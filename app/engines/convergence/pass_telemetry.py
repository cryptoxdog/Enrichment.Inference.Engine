"""Pass-over-pass telemetry — proves each convergence pass adds measurable value."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from ...models.field_confidence import FieldConfidenceMap
from ...models.loop_schemas import PassResult

logger = logging.getLogger(__name__)

DIMINISHING_RETURNS_MIN_IMPROVEMENT = 0.05  # 5%


class PassDelta(BaseModel):
    pass_a: int
    pass_b: int
    confidence_delta: float = 0.0
    uncertainty_delta: float = 0.0
    new_fields: int = 0
    tokens_spent: int = 0
    roi: float = 0.0


class ConvergenceReport(BaseModel):
    total_passes: int = 0
    fields_per_pass: list[int] = Field(default_factory=list)
    confidence_trajectory: list[float] = Field(default_factory=list)
    uncertainty_trajectory: list[float] = Field(default_factory=list)
    tokens_per_pass: list[int] = Field(default_factory=list)
    roi_per_pass: list[float] = Field(default_factory=list)
    deltas: list[PassDelta] = Field(default_factory=list)
    diminishing_returns_triggered: bool = False
    convergence_pass: int | None = None


class PassTelemetryCollector:
    """Accumulates PassResult snapshots and computes pass-over-pass analytics."""

    __slots__ = ("_passes",)

    def __init__(self) -> None:
        self._passes: list[PassResult] = []

    def record_pass(self, pass_result: PassResult) -> None:
        self._passes.append(pass_result)

    @property
    def pass_count(self) -> int:
        return len(self._passes)

    def confidence_delta(self, pass_a: int, pass_b: int) -> float:
        a = self._get(pass_a)
        b = self._get(pass_b)
        if a is None or b is None:
            return 0.0
        return round(b.field_confidences.avg_confidence - a.field_confidences.avg_confidence, 4)

    def uncertainty_delta(self, pass_a: int, pass_b: int) -> float:
        a = self._get(pass_a)
        b = self._get(pass_b)
        if a is None or b is None:
            return 0.0
        return round(b.uncertainty_after - a.uncertainty_after, 4)

    def diminishing_returns_check(self, window: int = 2) -> bool:
        if len(self._passes) < window + 1:
            return False
        recent = self._passes[-window:]
        improvements = []
        for i in range(1, len(recent)):
            prev_unc = recent[i - 1].uncertainty_after
            curr_unc = recent[i].uncertainty_after
            if prev_unc > 0:
                pct_improvement = (prev_unc - curr_unc) / prev_unc
            else:
                pct_improvement = 0.0
            improvements.append(pct_improvement)
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0
        return avg_improvement < DIMINISHING_RETURNS_MIN_IMPROVEMENT

    def convergence_report(self) -> ConvergenceReport:
        fields_per_pass: list[int] = []
        confidence_trajectory: list[float] = []
        uncertainty_trajectory: list[float] = []
        tokens_per_pass: list[int] = []
        roi_per_pass: list[float] = []
        deltas: list[PassDelta] = []

        for i, p in enumerate(self._passes):
            n_fields = len(p.fields_enriched) + len(p.fields_inferred)
            fields_per_pass.append(n_fields)
            confidence_trajectory.append(round(p.field_confidences.avg_confidence, 4))
            uncertainty_trajectory.append(round(p.uncertainty_after, 4))
            tokens_per_pass.append(p.tokens_used)
            roi = (n_fields / p.tokens_used) if p.tokens_used > 0 else 0.0
            roi_per_pass.append(round(roi, 6))

            if i > 0:
                prev = self._passes[i - 1]
                delta = PassDelta(
                    pass_a=prev.pass_number,
                    pass_b=p.pass_number,
                    confidence_delta=round(
                        p.field_confidences.avg_confidence - prev.field_confidences.avg_confidence, 4
                    ),
                    uncertainty_delta=round(p.uncertainty_after - prev.uncertainty_after, 4),
                    new_fields=n_fields,
                    tokens_spent=p.tokens_used,
                    roi=round(roi, 6),
                )
                deltas.append(delta)

        dr_triggered = self.diminishing_returns_check()
        conv_pass = None
        if dr_triggered and len(self._passes) >= 2:
            conv_pass = self._passes[-1].pass_number

        return ConvergenceReport(
            total_passes=len(self._passes),
            fields_per_pass=fields_per_pass,
            confidence_trajectory=confidence_trajectory,
            uncertainty_trajectory=uncertainty_trajectory,
            tokens_per_pass=tokens_per_pass,
            roi_per_pass=roi_per_pass,
            deltas=deltas,
            diminishing_returns_triggered=dr_triggered,
            convergence_pass=conv_pass,
        )

    def _get(self, pass_number: int) -> PassResult | None:
        for p in self._passes:
            if p.pass_number == pass_number:
                return p
        return None
