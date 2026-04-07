"""
Event models for outcome feedback and corrective enrichment.

Defines OutcomeEvent and OutcomeVerdict used by the outcome delegator
to handle match rejection feedback from the Graph Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class OutcomeVerdict(StrEnum):
    """Verdict from Graph Engine match outcome."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIAL = "partial"


@dataclass
class OutcomeEvent:
    """
    Match outcome event from Graph Engine.

    Emitted when a match is accepted, rejected, or partially matched.
    Used by outcome_delegator to trigger corrective enrichment passes.
    """

    entity_id: str
    run_id: str
    verdict: OutcomeVerdict
    failed_gates: list[str] = field(default_factory=list)
    confidence_deltas: dict[str, float] = field(default_factory=dict)
    graph_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
