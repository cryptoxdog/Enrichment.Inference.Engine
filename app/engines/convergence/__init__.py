"""Convergence loop engines."""

from .convergence_signals import (
    ConvergenceExitReason,
    GraphInferenceEvent,
    InferredTripleSignal,
)
from .cost_tracker import CostSummary, CostTracker
from .loop_state import (
    LoopState,
    LoopStateStore,
    LoopStatus,
    PostgresLoopStateStore,
    RedisLoopStateStore,
)
from .pass_telemetry import (
    ConvergenceReport,
    PassDelta,
    PassTelemetryCollector,
)
from .schema_proposer import (
    ApprovalDecision,
    FieldProposal,
    GateProposal,
    SchemaProposalSet,
    ScoringDimensionProposal,
    apply,
    propose,
)

__all__ = [
    # convergence_signals.py
    "InferredTripleSignal",
    "ConvergenceExitReason",
    "GraphInferenceEvent",
    # cost_tracker.py
    "CostSummary",
    "CostTracker",
    # pass_telemetry.py
    "PassDelta",
    "ConvergenceReport",
    "PassTelemetryCollector",
    # loop_state.py
    "LoopStatus",
    "LoopState",
    "LoopStateStore",
    "RedisLoopStateStore",
    "PostgresLoopStateStore",
    # schema_proposer.py
    "FieldProposal",
    "GateProposal",
    "ScoringDimensionProposal",
    "SchemaProposalSet",
    "ApprovalDecision",
    "propose",
    "apply",
]
