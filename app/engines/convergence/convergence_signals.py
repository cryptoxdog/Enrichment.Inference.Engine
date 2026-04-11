"""
convergence_signals.py
Inferred triple signals from GRAPH → ENRICH re-enrichment loop.

Models the external signal payload emitted by the GRAPH service after
materialization and consumed by GraphInferenceConsumer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class InferredTripleSignal(BaseModel):
    """Single inferred (subject, predicate, object) triple from GRAPH materialization."""

    subject_id: str = Field(..., description="Entity ID the triple was inferred about")
    predicate: str = Field(..., description="Relationship type, e.g. 'HAS_MATERIAL_AFFINITY'")
    object_value: Any = Field(..., description="Inferred value or target entity ID")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_rule: str = Field(..., description="Inference rule that produced this triple")
    domain: str = Field(..., description="Domain this triple belongs to")
    run_id: str = Field(..., description="Convergence run_id this belongs to")


class ConvergenceExitReason(StrEnum):
    DELTA_BELOW_THRESHOLD = "delta_below_threshold"
    NO_NEW_FIELDS = "no_new_fields"
    MAX_PASSES_REACHED = "max_passes_reached"
    EXTERNAL_SIGNAL_EMPTY = "external_signal_empty"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


class GraphInferenceEvent(BaseModel):
    """Event payload published to graph.inference.complete stream by GRAPH service."""

    entity_id: str
    domain: str
    run_id: str
    inferred_triples: list[InferredTripleSignal] = Field(default_factory=list)
    materialization_pass: int = 1
    graph_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
