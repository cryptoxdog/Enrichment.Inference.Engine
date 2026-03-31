# engine/scoring/__init__.py
"""Scoring module — belief propagation and composite scoring."""

from .belief_propagation import (
    bayesian_update,
    chain_composite,
    composite_score,
    hop_trust_from_entry,
    propagate_chain,
    rescore_candidates,
)

__all__ = [
    "bayesian_update",
    "chain_composite",
    "composite_score",
    "hop_trust_from_entry",
    "propagate_chain",
    "rescore_candidates",
]
