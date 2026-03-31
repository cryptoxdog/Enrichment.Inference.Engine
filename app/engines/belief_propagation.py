from __future__ import annotations

import logging
import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ── Trust Tier Constants ─────────────────────────────────────────────────────

TRUST_ENTAILMENT: float = 0.95
TRUST_NEUTRAL: float = 0.60
TRUST_CONTRADICTION: float = 0.10

# ── Enums ─────────────────────────────────────────────────────────────────────


class HopStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CONTRADICTED = "contradicted"
    SKIPPED = "skipped"
    PENDING = "pending"


# ── Models ────────────────────────────────────────────────────────────────────


class BayesianBeliefState(BaseModel):
    """
    Immutable belief state produced and consumed by the propagation engine.

    mu           — posterior mean probability in [0, 1]
    entropy      — normalized belief entropy in [0, 1]; 1.0 = maximum uncertainty
    n_observations — count of evidence updates applied to this belief
    """

    mu: float = Field(ge=0.0, le=1.0)
    entropy: float = Field(ge=0.0, le=1.0)
    n_observations: int = Field(ge=0)

    model_config = {"frozen": True}

    @field_validator("mu", mode="before")
    @classmethod
    def clamp_mu(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("entropy", mode="before")
    @classmethod
    def clamp_entropy(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @property
    def posterior_score(self) -> float:
        """
        Stopping criterion for the convergence loop.
        posterior_score = mu - entropy, clamped to [0, 1].
        Convergence threshold per spec: >= 0.85.
        """
        return max(0.0, min(1.0, self.mu - self.entropy))


class HopEntry(BaseModel):
    """
    Represents a single hop in a GATE trace.
    Used by hop_trust_from_entry to derive a trust scalar.
    """

    hop_id: str
    status: HopStatus
    duration_ms: float = Field(ge=0.0)
    timeout_ms: float = Field(gt=0.0)
    node_type: str

    model_config = {"frozen": True}


# ── Core Primitive ────────────────────────────────────────────────────────────


def bayesian_update(
    belief: BayesianBeliefState,
    trust: float,
) -> BayesianBeliefState:
    """
    Apply a single Bayesian evidence update to a belief state.

    The update weight decays as (1 / (n_observations + 1)), so strong priors
    (high n_observations) resist weak trust signals more than flat priors.

    Args:
        belief: Current immutable belief state.
        trust:  Trust scalar in [0, 1] representing evidence strength.

    Returns:
        New BayesianBeliefState — input is never mutated.
    """
    if not (0.0 <= trust <= 1.0):
        raise ValueError(f"trust must be in [0, 1], got {trust!r}")

    weight = 1.0 / (belief.n_observations + 1)
    new_mu = belief.mu + weight * (trust - belief.mu)
    new_mu = max(0.0, min(1.0, new_mu))

    # Entropy decreases as observations accumulate; trust extremes reduce entropy faster.
    signal_strength = abs(trust - 0.5) * 2.0  # 0 at neutral, 1 at extremes
    entropy_decay = weight * signal_strength
    new_entropy = max(0.0, min(1.0, belief.entropy * (1.0 - entropy_decay)))

    return BayesianBeliefState(
        mu=new_mu,
        entropy=new_entropy,
        n_observations=belief.n_observations + 1,
    )


# ── Aggregation Modes ─────────────────────────────────────────────────────────


def multi_parent_propagation(
    trust_scores: list[float],
    prior: BayesianBeliefState,
) -> BayesianBeliefState:
    """
    Aggregate INDEPENDENT evidence sources (CEG scoring dimensions).

    Uses the multi-parent formula: average trust across all parents, then
    apply a single Bayesian update from that aggregate signal.
    Order-invariant by design — independent evidence must commute.

    Args:
        trust_scores: Trust scalars from each independent dimension.
        prior:        Seeded prior belief (e.g., from neo4j confidence property).

    Returns:
        Updated BayesianBeliefState.

    Raises:
        ValueError: If trust_scores is empty.
    """
    if not trust_scores:
        raise ValueError("trust_scores must be non-empty for multi_parent_propagation")

    aggregate_trust = sum(trust_scores) / len(trust_scores)
    return bayesian_update(prior, trust=aggregate_trust)


def chain_propagation(
    trust_scores: list[float],
    prior: BayesianBeliefState,
) -> BayesianBeliefState:
    """
    Propagate CAUSALLY ORDERED evidence (GATE hop trace).

    Each hop is applied sequentially — each update's output is the next
    update's input. Confidence degrades monotonically with chain length
    for constant trust values.

    Args:
        trust_scores: Trust scalars ordered from first to last hop.
        prior:        Initial belief state before the chain begins.

    Returns:
        Terminal BayesianBeliefState after all hops applied.

    Raises:
        ValueError: If trust_scores is empty.
    """
    if not trust_scores:
        raise ValueError("trust_scores must be non-empty for chain_propagation")

    belief = prior
    for trust in trust_scores:
        belief = bayesian_update(belief, trust=trust)
    return belief


# ── Scalar Composite Functions ────────────────────────────────────────────────


def composite_score(
    trust_scores: list[float],
    prior: BayesianBeliefState,
) -> float:
    """
    Multi-parent composite score for CEG dimension aggregation.

    Returns the entropy-penalised posterior score after multi-parent propagation.
    Use this for CEG candidate dimension scoring — NOT for GATE hop traces.

    Args:
        trust_scores: Independent dimension trust scalars.
        prior:        Seeded prior belief.

    Returns:
        Float in [0, 1] representing the penalised belief score.
    """
    belief = multi_parent_propagation(trust_scores=trust_scores, prior=prior)
    return entropy_penalty(belief)


def chain_composite(
    trust_scores: list[float],
    prior: BayesianBeliefState,
) -> float:
    """
    Chain composite score for GATE hop trace quality assessment.

    Returns the entropy-penalised posterior score after chain propagation.
    Use this for GATE hop traces — NOT for CEG dimension scoring.

    Args:
        trust_scores: Hop trust scalars in causal order.
        prior:        Initial belief before the trace begins.

    Returns:
        Float in [0, 1] representing the penalised chain quality score.
    """
    belief = chain_propagation(trust_scores=trust_scores, prior=prior)
    return entropy_penalty(belief)


# ── Uncertainty Discount ──────────────────────────────────────────────────────


def entropy_penalty(belief: BayesianBeliefState) -> float:
    """
    Apply an uncertainty discount to a belief state.

    entropy_penalty(b) = b.mu * (1 - b.entropy)

    Properties:
    - Monotonically decreasing in entropy for fixed mu.
    - Equals mu when entropy=0 (zero uncertainty).
    - Approaches 0 as entropy→1 regardless of mu.
    - Always in [0, 1].

    Args:
        belief: The belief state to score.

    Returns:
        Float in [0, 1].
    """
    return belief.mu * (1.0 - belief.entropy)


# ── GATE Integration Helper ───────────────────────────────────────────────────


def hop_trust_from_entry(hop: HopEntry) -> float:
    """
    Derive a trust scalar from a HopEntry's status and duration profile.

    Trust tier mapping (per spec):
        COMPLETED    → TRUST_ENTAILMENT (0.95), subject to timeout penalty
        SKIPPED      → TRUST_NEUTRAL    (0.60)
        PENDING      → TRUST_NEUTRAL    (0.60)
        FAILED       → TRUST_CONTRADICTION (0.10)
        CONTRADICTED → TRUST_CONTRADICTION (0.10)

    Timeout penalty:
        Applied when duration_ms / timeout_ms > 0.5 (50% utilisation threshold).
        Trust is linearly degraded from full tier value to 0.5 × tier value
        as the ratio approaches 1.0. This signals that the node operated under
        resource pressure — a precursor to timeout cascades.

    Args:
        hop: Immutable HopEntry with status and timing fields.

    Returns:
        Trust scalar in [0, 1].
    """
    status_trust_map: dict[HopStatus, float] = {
        HopStatus.COMPLETED: TRUST_ENTAILMENT,
        HopStatus.SKIPPED: TRUST_NEUTRAL,
        HopStatus.PENDING: TRUST_NEUTRAL,
        HopStatus.FAILED: TRUST_CONTRADICTION,
        HopStatus.CONTRADICTED: TRUST_CONTRADICTION,
    }

    base_trust = status_trust_map.get(hop.status, TRUST_NEUTRAL)

    if hop.status == HopStatus.COMPLETED:
        utilisation = hop.duration_ms / hop.timeout_ms
        if utilisation > 0.5:
            # Linear penalty: at utilisation=0.5 → no penalty; at utilisation=1.0 → 50% reduction
            penalty_factor = (utilisation - 0.5) / 0.5  # 0.0 → 1.0
            base_trust = base_trust * (1.0 - 0.5 * penalty_factor)

    return max(0.0, min(1.0, base_trust))


# ── CEG Integration: Candidate Re-Scorer ─────────────────────────────────────


def rescore_candidates(
    candidates: list[dict[str, Any]],
    dimension_keys: list[str],
    prior_key: str,
    score_key: str,
) -> list[dict[str, Any]]:
    """
    Re-score and rank candidate dicts using Bayesian belief propagation.

    Algorithm:
        1. For each candidate, read its prior from prior_key (defaults to 0.5
           if absent, giving uniform belief).
        2. Build a seeded BayesianBeliefState from the prior.
        3. Collect dimension trust scores from dimension_keys (defaults to
           TRUST_NEUTRAL for absent keys).
        4. Apply multi_parent_propagation (independent dimensions — CEG contract).
        5. Apply entropy_penalty to produce the final score.
        6. Return new dict objects with score_key added — inputs are NEVER mutated
           (PacketEnvelope immutability contract).
        7. Sort descending by score_key.

    Args:
        candidates:     List of candidate dicts from the Neo4j query result.
        dimension_keys: Keys for independent scoring dimensions (geo, community, etc.).
        prior_key:      Key holding the candidate's existing confidence [0, 1].
        score_key:      Output key to add to each returned dict.

    Returns:
        New list of new dicts (inputs untouched), sorted descending by score_key.
    """
    if not candidates:
        return []

    scored: list[dict[str, Any]] = []

    for c in candidates:
        prior_mu = float(c.get(prior_key, 0.5))
        prior_mu = max(0.0, min(1.0, prior_mu))
        prior = BayesianBeliefState(
            mu=prior_mu,
            entropy=max(0.0, 1.0 - prior_mu),
            n_observations=0,
        )

        trust_scores = [
            float(c.get(k, TRUST_NEUTRAL)) for k in dimension_keys
        ]

        belief = multi_parent_propagation(trust_scores=trust_scores, prior=prior)
        score = entropy_penalty(belief)

        # PacketEnvelope immutability: never mutate input dict
        scored.append({**c, score_key: score})

    scored.sort(key=lambda x: x[score_key], reverse=True)
    logger.debug(
        "rescore_candidates complete",
        extra={"n_candidates": len(scored), "score_key": score_key},
    )
    return scored
