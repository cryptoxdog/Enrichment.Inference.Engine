# tests/test_belief_propagation_toth.py
"""
Belief Propagation (ToTh) Test Suite

Coverage:
    - Bayesian update correctness
    - Multi-parent composite scoring
    - Chain propagation
    - Hop trust derivation
    - Candidate rescoring
    - Edge cases and bounds

Note: Tests the engine/scoring/belief_propagation module (ToTh float-based API),
distinct from app/engines/belief_propagation (Pydantic BayesianBeliefState API).
"""

import pytest

from engine.scoring.belief_propagation import (
    TRUST_CONTRADICTION,
    TRUST_ENTAILMENT,
    TRUST_NEUTRAL,
    bayesian_update,
    chain_composite,
    composite_score,
    hop_trust_from_entry,
    propagate_chain,
    rescore_candidates,
)


class TestBayesianUpdate:
    """Test Bayesian belief update primitive."""

    def test_neutral_prior_strong_evidence(self):
        """Neutral prior + strong evidence → high posterior."""
        result = bayesian_update(0.5, 0.9)
        assert 0.89 < result < 0.91

    def test_strong_prior_strong_evidence(self):
        """Strong prior + strong evidence → very high posterior."""
        result = bayesian_update(0.8, 0.9)
        assert 0.97 < result < 0.98

    def test_weak_prior_strong_evidence(self):
        """Weak prior + strong evidence → moderate posterior."""
        result = bayesian_update(0.2, 0.9)
        assert 0.68 < result < 0.70

    def test_neutral_prior_weak_evidence(self):
        """Neutral prior + weak evidence → low posterior."""
        result = bayesian_update(0.5, 0.2)
        assert 0.19 < result < 0.21

    def test_extremes(self):
        """Test extreme values."""
        assert bayesian_update(1.0, 1.0) == 1.0
        assert bayesian_update(0.0, 0.0) == 0.0
        assert bayesian_update(0.0, 1.0) == 0.0

    def test_bounds_validation(self):
        """Invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            bayesian_update(-0.1, 0.5)
        with pytest.raises(ValueError):
            bayesian_update(0.5, 1.1)


class TestCompositeScore:
    """Test multi-parent belief fusion."""

    def test_high_confidence_low_entropy(self):
        """Consistent high signals → high composite score."""
        score = composite_score([0.9, 0.85, 0.8], prior=0.5)
        assert score > 0.8  # High belief, low entropy penalty

    def test_mixed_signals_high_entropy(self):
        """Mixed signals → entropy penalty reduces score."""
        score = composite_score([0.9, 0.5, 0.2], prior=0.5)
        assert score < 0.5  # Entropy penalty dominates

    def test_strong_prior_consistent_evidence(self):
        """Strong prior + consistent evidence → near-maximum score."""
        score = composite_score([0.95] * 5, prior=0.8)
        assert score > 0.94

    def test_empty_signals_returns_prior(self):
        """Empty signals → return prior."""
        assert composite_score([], prior=0.7) == 0.7

    def test_single_signal(self):
        """Single signal → Bayesian update of prior."""
        score = composite_score([0.9], prior=0.5)
        assert 0.85 < score < 0.95


class TestChainComposite:
    """Test chain hop trace quality scoring."""

    def test_consistent_high_trust_path(self):
        """All hops high trust → high chain quality."""
        score = chain_composite([0.95, 0.95, 0.95], prior=0.6)
        assert score > 0.94

    def test_middle_hop_uncertainty(self):
        """Middle hop uncertainty degrades quality."""
        score = chain_composite([0.95, 0.6, 0.95], prior=0.6)
        assert 0.6 < score < 0.7  # Entropy penalty from mixed signals

    def test_degrading_trust_chain(self):
        """Degrading trust → lower quality."""
        score = chain_composite([0.9, 0.7, 0.5], prior=0.5)
        assert 0.4 < score < 0.6


class TestPropagateChain:
    """Test chain terminal confidence (no entropy penalty)."""

    def test_strong_accumulation(self):
        """Strong sequential evidence → high terminal confidence."""
        result = propagate_chain([0.9, 0.85, 0.8], prior=0.5)
        assert result > 0.98

    def test_weak_terminal_hop(self):
        """Weak terminal hop dominates final confidence."""
        result = propagate_chain([0.9, 0.5, 0.2], prior=0.5)
        assert result < 0.25

    def test_empty_chain_returns_prior(self):
        """Empty chain → return prior."""
        assert propagate_chain([], prior=0.7) == 0.7


class TestHopTrustFromEntry:
    """Test GATE HopEntry trust derivation."""

    def test_completed_fast(self):
        """Fast completion → high trust."""
        trust = hop_trust_from_entry("COMPLETED", 1000, 30000)
        assert trust == TRUST_ENTAILMENT

    def test_completed_near_timeout(self):
        """Near timeout → degraded trust."""
        trust = hop_trust_from_entry("COMPLETED", 25000, 30000)
        assert TRUST_NEUTRAL < trust < TRUST_ENTAILMENT

    def test_completed_at_timeout(self):
        """At timeout → neutral trust."""
        trust = hop_trust_from_entry("COMPLETED", 30000, 30000)
        assert trust == pytest.approx(TRUST_NEUTRAL, abs=0.01)

    def test_pending_status(self):
        """PENDING → neutral trust."""
        trust = hop_trust_from_entry("PENDING", 5000, 30000)
        assert trust == TRUST_NEUTRAL

    def test_failed_status(self):
        """FAILED → contradiction trust."""
        trust = hop_trust_from_entry("FAILED", 5000, 30000)
        assert trust == TRUST_CONTRADICTION

    def test_timeout_status(self):
        """TIMEOUT → contradiction trust."""
        trust = hop_trust_from_entry("TIMEOUT", 30000, 30000)
        assert trust == TRUST_CONTRADICTION

    def test_unknown_status(self):
        """Unknown status → neutral trust."""
        trust = hop_trust_from_entry("UNKNOWN", 5000, 30000)
        assert trust == TRUST_NEUTRAL


class TestRescoreCandidates:
    """Test CEG candidate rescoring."""

    def test_higher_prior_wins(self):
        """Higher prior beats slightly lower dimensions."""
        candidates = [
            {"id": "A", "geo": 0.9, "temporal": 0.85, "confidence": 0.7},
            {"id": "B", "geo": 0.95, "temporal": 0.9, "confidence": 0.5},
        ]
        rescored = rescore_candidates(candidates, ["geo", "temporal"])
        assert rescored[0]["id"] == "A"  # Higher prior dominates

    def test_sorting_descending(self):
        """Results sorted by belief_score descending."""
        candidates = [
            {"id": "A", "score": 0.5},
            {"id": "B", "score": 0.9},
            {"id": "C", "score": 0.7},
        ]
        rescored = rescore_candidates(candidates, ["score"])
        assert [c["id"] for c in rescored] == ["B", "C", "A"]

    def test_empty_candidates(self):
        """Empty list → return empty list."""
        assert rescore_candidates([], ["score"]) == []

    def test_missing_dimensions(self):
        """Missing dimensions treated as 0.0."""
        candidates = [{"id": "A", "geo": 0.9}]
        rescored = rescore_candidates(candidates, ["geo", "missing"])
        assert "belief_score" in rescored[0]

    def test_immutability(self):
        """Original candidates not mutated."""
        candidates = [{"id": "A", "geo": 0.9}]
        original_id = id(candidates[0])
        rescored = rescore_candidates(candidates, ["geo"])
        assert id(rescored[0]) != original_id
        assert "belief_score" not in candidates[0]

    def test_custom_prior_key(self):
        """Custom prior_key used correctly."""
        candidates = [{"id": "A", "score": 0.8, "custom_prior": 0.9}]
        rescored = rescore_candidates(
            candidates, ["score"], prior_key="custom_prior"
        )
        assert rescored[0]["belief_score"] > 0.85

    def test_custom_score_key(self):
        """Custom score_key used correctly."""
        candidates = [{"id": "A", "score": 0.8}]
        rescored = rescore_candidates(candidates, ["score"], score_key="my_score")
        assert "my_score" in rescored[0]
        assert "belief_score" not in rescored[0]
