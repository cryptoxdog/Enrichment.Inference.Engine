"""
Enrichment package.

Provides multi-source waterfall enrichment, quality scoring,
consensus synthesis, uncertainty management, and KB context injection
for the L9 RevOps Enrichment Engine.
"""

from .consensus import ConsensusResult, merge_with_priority, synthesize
from .kb_resolver import KBContext, KBResolver
from .quality_scorer import QualityScorer
from .uncertainty import (
    UncertaintyConfig,
    UncertaintyResult,
    aggregate_uncertainties,
    apply_uncertainty,
    should_proceed,
)
from .waterfall_engine import WaterfallEngine

__all__ = [
    # Core engines
    "QualityScorer",
    "WaterfallEngine",
    # Consensus
    "ConsensusResult",
    "merge_with_priority",
    "synthesize",
    # Uncertainty
    "UncertaintyConfig",
    "UncertaintyResult",
    "aggregate_uncertainties",
    "apply_uncertainty",
    "should_proceed",
    # KB Resolver
    "KBContext",
    "KBResolver",
]
