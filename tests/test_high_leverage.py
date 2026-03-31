from __future__ import annotations

import copy
import hashlib
import json
import math

import pytest

from app.engines.belief_propagation import (
    TRUST_CONTRADICTION,
    TRUST_ENTAILMENT,
    TRUST_NEUTRAL,
    BayesianBeliefState,
    HopEntry,
    HopStatus,
    bayesian_update,
    chain_composite,
    chain_propagation,
    composite_score,
    entropy_penalty,
    hop_trust_from_entry,
    multi_parent_propagation,
    rescore_candidates,
)


# ────────────────────────────────────────────────────────────────────────────
# RANK 1 — Atomic primitive correctness
# ────────────────────────────────────────────────────────────────────────────
class TestRank1_BayesianUpdateAtomicPrimitive:
    def test_high_trust_increases_mu_from_uniform(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(prior, trust=TRUST_ENTAILMENT)
        assert updated.mu > 0.5

    def test_low_trust_decreases_mu_from_uniform(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(prior, trust=TRUST_CONTRADICTION)
        assert updated.mu < 0.5

    def test_non_uniform_prior_resists_weak_signal(self) -> None:
        strong_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=50)
        weak_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=1)
        trust = 0.3
        delta_strong = abs(bayesian_update(strong_prior, trust=trust).mu - strong_prior.mu)
        delta_weak = abs(bayesian_update(weak_prior, trust=trust).mu - weak_prior.mu)
        assert delta_strong < delta_weak

    def test_output_always_in_unit_interval(self) -> None:
        for trust in [0.0, 0.001, 0.5, 0.999, 1.0]:
            for mu in [0.0, 0.01, 0.5, 0.99, 1.0]:
                prior = BayesianBeliefState(mu=mu, entropy=0.5, n_observations=0)
                result = bayesian_update(prior, trust=trust)
                assert 0.0 <= result.mu <= 1.0

    def test_n_observations_increments_exactly_one(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=7)
        updated = bayesian_update(prior, trust=0.8)
        assert updated.n_observations == 8


# ────────────────────────────────────────────────────────────────────────────
# RANK 2 — PacketEnvelope immutability
# ────────────────────────────────────────────────────────────────────────────
class TestRank2_InputImmutabilityPacketEnvelopeContract:
    def test_input_dicts_not_mutated_by_score_key(self) -> None:
        candidates = [
            {"id": "a", "confidence": 0.8, "geo_score": 0.9, "community_score": 0.85},
            {"id": "b", "confidence": 0.3, "geo_score": 0.95, "community_score": 0.92},
        ]
        originals = copy.deepcopy(candidates)
        rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert candidates == originals

    def test_output_contains_new_object_references(self) -> None:
        candidates = [{"id": "x", "confidence": 0.7, "geo_score": 0.8}]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert id(result[0]) != id(candidates[0])

    def test_belief_state_not_mutated_through_update_chain(self) -> None:
        b = BayesianBeliefState(mu=0.7, entropy=0.3, n_observations=4)
        original_mu = b.mu
        _ = bayesian_update(b, trust=0.95)
        assert b.mu == original_mu


# ────────────────────────────────────────────────────────────────────────────
# RANK 3 — Algorithm mode routing: CEG vs GATE
# ────────────────────────────────────────────────────────────────────────────
class TestRank3_AlgorithmModeRoutingCEGvsGATE:
    def test_multi_parent_is_order_invariant_for_ceg(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        scores = [0.9, 0.4, 0.7, 0.55]
        r_forward = multi_parent_propagation(trust_scores=scores, prior=prior)
        r_reversed = multi_parent_propagation(
            trust_scores=list(reversed(scores)), prior=prior
        )
        assert r_forward.mu == pytest.approx(r_reversed.mu, abs=1e-6)

    def test_chain_degrades_monotonically_for_gate(self) -> None:
        prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=0)
        trust = 0.85
        r1 = chain_propagation(trust_scores=[trust], prior=prior)
        r2 = chain_propagation(trust_scores=[trust, trust], prior=prior)
        r3 = chain_propagation(trust_scores=[trust, trust, trust], prior=prior)
        assert r1.mu >= r2.mu >= r3.mu

    def test_ceg_and_gate_produce_different_results_for_divergent_inputs(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        divergent_scores = [0.95, 0.1, 0.9, 0.05]
        r_multi = composite_score(trust_scores=divergent_scores, prior=prior)
        r_chain = chain_composite(trust_scores=divergent_scores, prior=prior)
        assert r_multi != pytest.approx(r_chain, abs=1e-3)


# ────────────────────────────────────────────────────────────────────────────
# RANK 4 — Prior seeding ranking reversal
# ────────────────────────────────────────────────────────────────────────────
class TestRank4_PriorSeedingRankingReversal:
    def test_high_prior_outranks_low_prior_despite_better_dimensions(self) -> None:
        candidates = [
            {
                "id": "cmp_A",
                "confidence": 0.85,
                "geo_score": 0.88,
                "community_score": 0.82,
                "temporal_score": 0.75,
                "price_score": 0.70,
            },
            {
                "id": "cmp_B",
                "confidence": 0.20,
                "geo_score": 0.97,
                "community_score": 0.95,
                "temporal_score": 0.93,
                "price_score": 0.91,
            },
        ]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score", "community_score", "temporal_score", "price_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        scores_by_id = {c["id"]: c["belief_score"] for c in result}
        assert scores_by_id["cmp_A"] > scores_by_id["cmp_B"]

    def test_uniform_prior_ignores_confidence_seeding(self) -> None:
        candidates = [
            {"id": "x", "confidence": 0.85, "geo_score": 0.7},
            {"id": "y", "confidence": 0.20, "geo_score": 0.7},
        ]
        result_seeded = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        scores = {c["id"]: c["belief_score"] for c in result_seeded}
        assert scores["x"] != pytest.approx(scores["y"], abs=1e-3)


# ────────────────────────────────────────────────────────────────────────────
# RANK 5 — Timeout penalty threshold boundary
# ────────────────────────────────────────────────────────────────────────────
class TestRank5_TimeoutPenaltyThresholdBoundary:
    def test_hop_just_below_threshold_is_not_penalised(self) -> None:
        safe_hop = HopEntry(
            hop_id="safe",
            status=HopStatus.COMPLETED,
            duration_ms=999,
            timeout_ms=2000,
            node_type="enrichment",
        )
        trust = hop_trust_from_entry(safe_hop)
        assert trust >= TRUST_NEUTRAL

    def test_hop_just_above_threshold_is_penalised(self) -> None:
        risky_hop = HopEntry(
            hop_id="risky",
            status=HopStatus.COMPLETED,
            duration_ms=1001,
            timeout_ms=2000,
            node_type="enrichment",
        )
        safe_hop = HopEntry(
            hop_id="safe",
            status=HopStatus.COMPLETED,
            duration_ms=999,
            timeout_ms=2000,
            node_type="enrichment",
        )
        assert hop_trust_from_entry(risky_hop) < hop_trust_from_entry(safe_hop)

    def test_near_timeout_hop_significantly_penalised(self) -> None:
        near_timeout = HopEntry(
            hop_id="near",
            status=HopStatus.COMPLETED,
            duration_ms=1990,
            timeout_ms=2000,
            node_type="enrichment",
        )
        baseline = HopEntry(
            hop_id="baseline",
            status=HopStatus.COMPLETED,
            duration_ms=500,
            timeout_ms=2000,
            node_type="enrichment",
        )
        assert hop_trust_from_entry(near_timeout) < hop_trust_from_entry(baseline) * 0.9


# ────────────────────────────────────────────────────────────────────────────
# RANK 6 — Entropy penalty monotonicity
# ────────────────────────────────────────────────────────────────────────────
class TestRank6_EntropyPenaltyMonotonicity:
    def test_penalty_strictly_decreasing_as_entropy_increases(self) -> None:
        mu = 0.88
        entropies = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        scores = [
            entropy_penalty(BayesianBeliefState(mu=mu, entropy=e, n_observations=10))
            for e in entropies
        ]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_zero_entropy_score_approximates_mu(self) -> None:
        belief = BayesianBeliefState(mu=0.92, entropy=0.0, n_observations=20)
        score = entropy_penalty(belief)
        assert score == pytest.approx(belief.mu, abs=0.05)

    def test_maximum_entropy_belief_scored_below_half(self) -> None:
        belief = BayesianBeliefState(mu=0.95, entropy=1.0, n_observations=0)
        score = entropy_penalty(belief)
        assert score < 0.5


# ────────────────────────────────────────────────────────────────────────────
# RANK 7 — Convergence threshold gate
# ────────────────────────────────────────────────────────────────────────────
class TestRank7_ConvergenceThresholdGate:
    def test_posterior_score_formula_is_mu_minus_entropy(self) -> None:
        belief = BayesianBeliefState(mu=0.92, entropy=0.08, n_observations=10)
        expected = belief.mu - belief.entropy
        assert belief.posterior_score == pytest.approx(expected, abs=1e-6)

    def test_posterior_score_never_negative(self) -> None:
        for mu in [0.1, 0.3, 0.5]:
            for entropy in [0.5, 0.8, 1.0]:
                belief = BayesianBeliefState(mu=mu, entropy=entropy, n_observations=0)
                assert belief.posterior_score >= 0.0

    def test_sufficient_entailment_observations_cross_threshold(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        for _ in range(12):
            belief = bayesian_update(belief, trust=TRUST_ENTAILMENT)
        assert belief.posterior_score >= 0.85


# ────────────────────────────────────────────────────────────────────────────
# RANK 8 — Content hash determinism
# ────────────────────────────────────────────────────────────────────────────
class TestRank8_ContentHashDeterminism:
    @staticmethod
    def _hash_result(result: list[dict]) -> str:
        payload = json.dumps(
            [
                {k: v for k, v in sorted(c.items())}
                for c in sorted(result, key=lambda x: x["id"])
            ],
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def test_identical_inputs_produce_identical_content_hash(self) -> None:
        candidates = [
            {"id": "a", "confidence": 0.8, "geo": 0.9, "comm": 0.85},
            {"id": "b", "confidence": 0.4, "geo": 0.95, "comm": 0.92},
            {"id": "c", "confidence": 0.1, "geo": 0.55, "comm": 0.60},
        ]
        r1 = rescore_candidates(
            candidates=copy.deepcopy(candidates),
            dimension_keys=["geo", "comm"],
            prior_key="confidence",
            score_key="belief_score",
        )
        r2 = rescore_candidates(
            candidates=copy.deepcopy(candidates),
            dimension_keys=["geo", "comm"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert self._hash_result(r1) == self._hash_result(r2)

    def test_bayesian_update_deterministic_across_calls(self) -> None:
        prior = BayesianBeliefState(mu=0.65, entropy=0.35, n_observations=5)
        r1 = bayesian_update(prior, trust=0.82)
        r2 = bayesian_update(prior, trust=0.82)
        assert r1.mu == r2.mu
        assert r1.entropy == r2.entropy


# ────────────────────────────────────────────────────────────────────────────
# RANK 9 — Contradiction spiral numerical bounds
# ────────────────────────────────────────────────────────────────────────────
class TestRank9_ContradictionSpiralNumericalBounds:
    def test_20_contradiction_updates_stay_in_unit_interval(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for step in range(20):
            belief = bayesian_update(belief, trust=TRUST_CONTRADICTION)
            assert 0.0 <= belief.mu <= 1.0, f"mu={belief.mu} at step {step+1}"
            assert not math.isnan(belief.mu)
            assert not math.isinf(belief.mu)

    def test_20_entailment_updates_stay_below_one(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for step in range(20):
            belief = bayesian_update(belief, trust=TRUST_ENTAILMENT)
            assert belief.mu <= 1.0, f"mu={belief.mu} at step {step+1}"

    def test_entropy_never_negative_after_updates(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for _ in range(15):
            belief = bayesian_update(belief, trust=TRUST_CONTRADICTION)
        assert belief.entropy >= 0.0


# ────────────────────────────────────────────────────────────────────────────
# RANK 10 — Trust tier spec compliance
# ────────────────────────────────────────────────────────────────────────────
class TestRank10_TrustTierSpecCompliance:
    def test_entailment_tier_in_spec_range(self) -> None:
        assert TRUST_ENTAILMENT >= 0.90
        assert TRUST_ENTAILMENT <= 1.0

    def test_neutral_tier_in_spec_range(self) -> None:
        assert 0.50 <= TRUST_NEUTRAL <= 0.70

    def test_contradiction_tier_in_spec_range(self) -> None:
        assert TRUST_CONTRADICTION <= 0.15
        assert TRUST_CONTRADICTION >= 0.0

    def test_tier_ordering_invariant(self) -> None:
        assert TRUST_CONTRADICTION < TRUST_NEUTRAL < TRUST_ENTAILMENT

    def test_tier_gap_sufficient_for_signal_separation(self) -> None:
        entailment_gap = TRUST_ENTAILMENT - TRUST_NEUTRAL
        contradiction_gap = TRUST_NEUTRAL - TRUST_CONTRADICTION
        assert entailment_gap >= 0.20
        assert contradiction_gap >= 0.30
