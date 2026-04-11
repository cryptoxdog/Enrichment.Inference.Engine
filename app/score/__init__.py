"""
SCORE Service — Multi-dimensional entity scoring.

Exports:
    ScoreEngine         — Core scoring engine
    DecayEngine         — Temporal decay processor
    ScoreExplainer      — Human-readable explanations
    score_models        — All data models (ScoreRecord, ScoringProfile, etc.)
    score_icp_plastics  — Plastics recycling domain ICP
    router              — FastAPI router for /score endpoints
"""

from .score_decay import DecayEngine, DecayReport, DimensionDecayResult
from .score_engine import ScoreEngine
from .score_explainer import ScoreExplainer, ScoreExplanation
from .score_models import (
    BatchScoreRequest,
    BatchScoreResponse,
    DecayConfig,
    DimensionScore,
    FieldContribution,
    ICPDefinition,
    ICPFieldCriterion,
    ICPFieldType,
    MissingField,
    RecommendationType,
    ScoreDimension,
    ScoreProvenance,
    ScoreRecord,
    ScoreSource,
    ScoreTier,
    ScoringProfile,
)

__all__ = [
    "BatchScoreRequest",
    "BatchScoreResponse",
    "DecayConfig",
    "DecayEngine",
    "DecayReport",
    "DimensionDecayResult",
    "DimensionScore",
    "FieldContribution",
    "ICPDefinition",
    "ICPFieldCriterion",
    "ICPFieldType",
    "MissingField",
    "RecommendationType",
    "ScoreDimension",
    "ScoreEngine",
    "ScoreExplainer",
    "ScoreExplanation",
    "ScoreProvenance",
    "ScoreRecord",
    "ScoreSource",
    "ScoreTier",
    "ScoringProfile",
]
