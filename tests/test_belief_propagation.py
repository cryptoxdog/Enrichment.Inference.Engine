from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

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

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def uniform_belief() -> BayesianBeliefState:
    return BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)


@pytest.fixture
def high_confidence_belief() -> BayesianBeliefState:
    return BayesianBeliefState(mu=0.92, entropy=0.08, n_observations=12)


@pytest.fixture
def low_confidence_belief() -> BayesianBeliefState:
    return BayesianBeliefState(mu=0.21, entropy=0.88, n_observations=3)


@pytest.fixture
def completed_hop() -> HopEntry:
    return HopEntry(
        hop_id="hop_001",
        status=HopStatus.COMPLETED,
        duration_ms=800,
        timeout_ms=2000,
        node_type="enrichment",
    )


@pytest.fixture
def timeout_risk_hop() -> HopEntry:
    return HopEntry(
        hop_id="hop_002",
        status=HopStatus.COMPLETED,
        duration_ms=1950,
        timeout_ms=2000,
        node_type="enrichment",
    )


@pytest.fixture
def failed_hop() -> HopEntry:
    return HopEntry(
        hop_id="hop_003",
        status=HopStatus.FAILED,
        duration_ms=0,
        timeout_ms=2000,
        node_type="enrichment",
    )


@pytest.fixture
def contradicted_hop() -> HopEntry:
    return HopEntry(
        hop_id="hop_004",
        status=HopStatus.CONTRADICTED,
        duration_ms=300,
        timeout_ms=2000,
        node_type="scoring",
    )


@pytest.fixture
def skipped_hop() -> HopEntry:
    return HopEntry(
        hop_id="hop_005",
        status=HopStatus.SKIPPED,
        duration_ms=0,
        timeout_ms=2000,
        node_type="routing",
    )


@pytest.fixture
def sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "cmp_001",
            "name": "Acme Corp",
            "confidence": 0.85,
            "geo_score": 0.90,
            "community_score": 0.88,
            "temporal_score": 0.75,
            "price_score": 0.70,
        },
        {
            "id": "cmp_002",
            "name": "Beta LLC",
            "confidence": 0.40,
            "geo_score": 0.95,
            "community_score": 0.97,
            "temporal_score": 0.93,
            "price_score": 0.91,
        },
        {
            "id": "cmp_003",
            "name": "Gamma Inc",
            "confidence": 0.10,
            "geo_score": 0.55,
            "community_score": 0.60,
            "temporal_score": 0.50,
            "price_score": 0.45,
        },
    ]


# ── Class 1: BayesianBeliefState ──────────────────────────────────────────────


class TestBayesianBeliefState:
    def test_construction_valid(self) -> None:
        b = BayesianBeliefState(mu=0.75, entropy=0.25, n_observations=5)
        assert b.mu == pytest.approx(0.75)
        assert b.entropy == pytest.approx(0.25)
        assert b.n_observations == 5

    def test_mu_clipped_to_unit_interval(self) -> None:
        b_high = BayesianBeliefState(mu=1.5, entropy=0.0, n_observations=1)
        b_low = BayesianBeliefState(mu=-0.3, entropy=0.0, n_observations=1)
        assert 0.0 <= b_high.mu <= 1.0
        assert 0.0 <= b_low.mu <= 1.0

    def test_entropy_clipped_to_unit_interval(self) -> None:
        b = BayesianBeliefState(mu=0.5, entropy=2.5, n_observations=0)
        assert 0.0 <= b.entropy <= 1.0

    def test_n_observations_non_negative(self) -> None:
        with pytest.raises(ValueError):
            BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=-1)

    def test_immutability(self) -> None:
        b = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        with pytest.raises(Exception):
            b.mu = 0.9  # type: ignore[misc]

    def test_posterior_score_property(self, high_confidence_belief: BayesianBeliefState) -> None:
        score = high_confidence_belief.posterior_score
        assert 0.0 <= score <= 1.0
        assert score == pytest.approx(
            high_confidence_belief.mu - high_confidence_belief.entropy, abs=1e-6
        )

    def test_posterior_score_never_negative(self, uniform_belief: BayesianBeliefState) -> None:
        score = uniform_belief.posterior_score
        assert score >= 0.0

    def test_repr_contains_mu(self) -> None:
        b = BayesianBeliefState(mu=0.88, entropy=0.12, n_observations=8)
        assert "0.88" in repr(b)


# ── Class 2: bayesian_update ──────────────────────────────────────────────────


class TestBayesianUpdate:
    def test_high_trust_increases_mu(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        updated = bayesian_update(belief, trust=0.9)
        assert updated.mu > belief.mu

    def test_low_trust_decreases_mu(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        updated = bayesian_update(belief, trust=0.1)
        assert updated.mu < belief.mu

    def test_neutral_trust_leaves_mu_near_prior(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        updated = bayesian_update(belief, trust=TRUST_NEUTRAL)
        assert updated.mu == pytest.approx(belief.mu, abs=0.05)

    def test_uniform_prior_with_entailment(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(belief, trust=TRUST_ENTAILMENT)
        assert updated.mu > 0.5
        assert updated.entropy < 1.0

    def test_uniform_prior_with_contradiction(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(belief, trust=TRUST_CONTRADICTION)
        assert updated.mu < 0.5

    def test_n_observations_increments(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=3)
        updated = bayesian_update(belief, trust=0.8)
        assert updated.n_observations == 4

    def test_output_mu_in_unit_interval(self) -> None:
        for trust in [0.0, 0.01, 0.5, 0.99, 1.0]:
            belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
            updated = bayesian_update(belief, trust=trust)
            assert 0.0 <= updated.mu <= 1.0, f"mu out of range for trust={trust}"

    def test_trust_zero_produces_minimum_belief(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        updated = bayesian_update(belief, trust=0.0)
        assert updated.mu < 0.2

    def test_trust_one_produces_near_maximum_belief(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        updated = bayesian_update(belief, trust=1.0)
        assert updated.mu > 0.8

    def test_non_uniform_prior_dominates_weak_trust(self) -> None:
        strong_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=50)
        weak_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=1)
        trust = 0.3
        strong_updated = bayesian_update(strong_prior, trust=trust)
        weak_updated = bayesian_update(weak_prior, trust=trust)
        delta_strong = abs(strong_updated.mu - strong_prior.mu)
        delta_weak = abs(weak_updated.mu - weak_prior.mu)
        assert delta_strong < delta_weak

    def test_determinism(self) -> None:
        belief = BayesianBeliefState(mu=0.65, entropy=0.35, n_observations=5)
        r1 = bayesian_update(belief, trust=0.78)
        r2 = bayesian_update(belief, trust=0.78)
        assert r1.mu == r2.mu
        assert r1.entropy == r2.entropy

    def test_input_not_mutated(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=2)
        original_mu = belief.mu
        bayesian_update(belief, trust=0.9)
        assert belief.mu == original_mu


# ── Class 3: multi_parent_propagation ─────────────────────────────────────────


class TestMultiParentPropagation:
    def test_returns_belief_state(self) -> None:
        result = multi_parent_propagation(
            trust_scores=[0.9, 0.85, 0.80],
            prior=BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0),
        )
        assert isinstance(result, BayesianBeliefState)

    def test_uniform_trust_scores(self) -> None:
        trust = 0.8
        result = multi_parent_propagation(
            trust_scores=[trust, trust, trust],
            prior=BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0),
        )
        assert result.mu == pytest.approx(trust, abs=0.15)

    def test_independent_dimension_order_invariance(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        scores = [0.9, 0.7, 0.5, 0.4]
        r1 = multi_parent_propagation(trust_scores=scores, prior=prior)
        r2 = multi_parent_propagation(trust_scores=list(reversed(scores)), prior=prior)
        assert r1.mu == pytest.approx(r2.mu, abs=1e-6)
        assert r1.entropy == pytest.approx(r2.entropy, abs=1e-6)

    def test_single_parent_equals_bayesian_update(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        trust = 0.87
        result_multi = multi_parent_propagation(trust_scores=[trust], prior=prior)
        result_bayes = bayesian_update(prior, trust=trust)
        assert result_multi.mu == pytest.approx(result_bayes.mu, abs=1e-4)

    def test_empty_trust_scores_raises(self) -> None:
        with pytest.raises((ValueError, ZeroDivisionError)):
            multi_parent_propagation(
                trust_scores=[],
                prior=BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0),
            )

    def test_all_contradiction_scores_lowers_mu(self) -> None:
        prior = BayesianBeliefState(mu=0.8, entropy=0.2, n_observations=0)
        result = multi_parent_propagation(
            trust_scores=[TRUST_CONTRADICTION] * 4,
            prior=prior,
        )
        assert result.mu < prior.mu

    def test_high_confidence_prior_resists_noise(self) -> None:
        strong_prior = BayesianBeliefState(mu=0.92, entropy=0.05, n_observations=100)
        noisy_scores = [0.4, 0.6, 0.55, 0.45]
        result = multi_parent_propagation(trust_scores=noisy_scores, prior=strong_prior)
        assert result.mu > 0.70


# ── Class 4: chain_propagation ────────────────────────────────────────────────


class TestChainPropagation:
    def test_returns_belief_state(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = chain_propagation(trust_scores=[0.9, 0.85, 0.80], prior=prior)
        assert isinstance(result, BayesianBeliefState)

    def test_chain_degrades_over_hops(self) -> None:
        prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=0)
        trust = 0.85
        r1 = chain_propagation(trust_scores=[trust], prior=prior)
        r2 = chain_propagation(trust_scores=[trust, trust], prior=prior)
        r3 = chain_propagation(trust_scores=[trust, trust, trust], prior=prior)
        assert r1.mu >= r2.mu >= r3.mu

    def test_chain_vs_multi_parent_differs(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        scores = [0.9, 0.5, 0.3]
        r_chain = chain_propagation(trust_scores=scores, prior=prior)
        r_multi = multi_parent_propagation(trust_scores=scores, prior=prior)
        assert r_chain.mu != pytest.approx(r_multi.mu, abs=1e-3)

    def test_high_trust_chain_preserves_belief(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = chain_propagation(trust_scores=[TRUST_ENTAILMENT] * 5, prior=prior)
        assert result.mu > 0.75

    def test_single_hop_chain(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        trust = 0.9
        result = chain_propagation(trust_scores=[trust], prior=prior)
        assert 0.0 <= result.mu <= 1.0

    def test_empty_trust_scores_raises(self) -> None:
        with pytest.raises((ValueError, IndexError)):
            chain_propagation(
                trust_scores=[],
                prior=BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0),
            )

    def test_chain_result_in_unit_interval(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        result = chain_propagation(
            trust_scores=[0.9, 0.8, 0.2, 0.95, 0.1], prior=prior
        )
        assert 0.0 <= result.mu <= 1.0


# ── Class 5: composite_score and chain_composite ──────────────────────────────


class TestCompositeScores:
    def test_composite_score_multi_parent_mode(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = composite_score(trust_scores=[0.9, 0.85, 0.8], prior=prior)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_chain_composite_chain_mode(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = chain_composite(trust_scores=[0.9, 0.85, 0.8], prior=prior)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_composite_vs_chain_divergent_inputs(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        scores = [0.95, 0.1, 0.9, 0.05]
        r_composite = composite_score(trust_scores=scores, prior=prior)
        r_chain = chain_composite(trust_scores=scores, prior=prior)
        assert r_composite != pytest.approx(r_chain, abs=1e-3)

    def test_composite_score_uniform_inputs(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = composite_score(trust_scores=[0.8, 0.8, 0.8, 0.8], prior=prior)
        assert result == pytest.approx(0.8, abs=0.15)

    def test_chain_composite_high_trust(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = chain_composite(trust_scores=[TRUST_ENTAILMENT] * 3, prior=prior)
        assert result > 0.75

    def test_chain_composite_low_trust_penalizes(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        result = chain_composite(
            trust_scores=[TRUST_CONTRADICTION] * 3, prior=prior
        )
        assert result < 0.3

    def test_composite_determinism(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        scores = [0.9, 0.8, 0.7]
        r1 = composite_score(trust_scores=scores, prior=prior)
        r2 = composite_score(trust_scores=scores, prior=prior)
        assert r1 == r2


# ── Class 6: hop_trust_from_entry ─────────────────────────────────────────────


class TestHopTrustFromEntry:
    def test_completed_hop_returns_entailment_tier(
        self, completed_hop: HopEntry
    ) -> None:
        trust = hop_trust_from_entry(completed_hop)
        assert trust >= TRUST_NEUTRAL

    def test_failed_hop_returns_contradiction_tier(
        self, failed_hop: HopEntry
    ) -> None:
        trust = hop_trust_from_entry(failed_hop)
        assert trust <= TRUST_CONTRADICTION + 0.05

    def test_contradicted_hop_returns_contradiction_tier(
        self, contradicted_hop: HopEntry
    ) -> None:
        trust = hop_trust_from_entry(contradicted_hop)
        assert trust <= TRUST_CONTRADICTION + 0.05

    def test_skipped_hop_returns_neutral_tier(
        self, skipped_hop: HopEntry
    ) -> None:
        trust = hop_trust_from_entry(skipped_hop)
        assert trust == pytest.approx(TRUST_NEUTRAL, abs=0.10)

    def test_timeout_risk_degrades_trust(
        self, completed_hop: HopEntry, timeout_risk_hop: HopEntry
    ) -> None:
        normal_trust = hop_trust_from_entry(completed_hop)
        risk_trust = hop_trust_from_entry(timeout_risk_hop)
        assert normal_trust > risk_trust

    def test_timeout_penalty_threshold(self) -> None:
        safe_hop = HopEntry(
            hop_id="h_safe",
            status=HopStatus.COMPLETED,
            duration_ms=900,
            timeout_ms=2000,
            node_type="enrichment",
        )
        risky_hop = HopEntry(
            hop_id="h_risky",
            status=HopStatus.COMPLETED,
            duration_ms=1100,
            timeout_ms=2000,
            node_type="enrichment",
        )
        safe_trust = hop_trust_from_entry(safe_hop)
        risky_trust = hop_trust_from_entry(risky_hop)
        assert safe_trust > risky_trust

    def test_trust_in_unit_interval(self, completed_hop: HopEntry) -> None:
        trust = hop_trust_from_entry(completed_hop)
        assert 0.0 <= trust <= 1.0

    def test_trust_constants_ordering(self) -> None:
        assert TRUST_CONTRADICTION < TRUST_NEUTRAL < TRUST_ENTAILMENT
        assert TRUST_CONTRADICTION >= 0.0
        assert TRUST_ENTAILMENT <= 1.0

    def test_pending_hop_handled(self) -> None:
        pending = HopEntry(
            hop_id="h_pending",
            status=HopStatus.PENDING,
            duration_ms=0,
            timeout_ms=2000,
            node_type="enrichment",
        )
        trust = hop_trust_from_entry(pending)
        assert 0.0 <= trust <= 1.0


# ── Class 7: rescore_candidates ───────────────────────────────────────────────


class TestRescoreCandidates:
    def test_returns_list_of_dicts(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score", "community_score", "temporal_score", "price_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert isinstance(result, list)
        assert all(isinstance(c, dict) for c in result)

    def test_score_key_added_to_each_candidate(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        for candidate in result:
            assert "belief_score" in candidate
            assert isinstance(candidate["belief_score"], float)
            assert 0.0 <= candidate["belief_score"] <= 1.0

    def test_input_candidates_not_mutated(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        original = copy.deepcopy(sample_candidates)
        rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert sample_candidates == original

    def test_high_prior_candidate_ranks_above_low_prior_despite_better_dims(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score", "community_score", "temporal_score", "price_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        result_by_id = {c["id"]: c for c in result}
        assert result_by_id["cmp_001"]["belief_score"] > result_by_id["cmp_002"]["belief_score"]

    def test_sorted_descending_by_score(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        scores = [c["belief_score"] for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_missing_prior_key_defaults_to_uniform(self) -> None:
        candidates = [
            {"id": "x", "dim1": 0.8, "dim2": 0.9},
        ]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["dim1", "dim2"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert "belief_score" in result[0]

    def test_missing_dimension_key_uses_neutral_trust(self) -> None:
        candidates = [{"id": "y", "confidence": 0.7}]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert result[0]["belief_score"] >= 0.0

    def test_empty_candidates_returns_empty_list(self) -> None:
        result = rescore_candidates(
            candidates=[],
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert result == []

    def test_single_candidate(self) -> None:
        candidates = [{"id": "z", "confidence": 0.75, "geo_score": 0.88}]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert len(result) == 1
        assert 0.0 <= result[0]["belief_score"] <= 1.0


# ── Class 8: entropy_penalty ──────────────────────────────────────────────────


class TestEntropyPenalty:
    def test_returns_float_in_unit_interval(self) -> None:
        belief = BayesianBeliefState(mu=0.8, entropy=0.4, n_observations=5)
        result = entropy_penalty(belief)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_low_entropy_belief_has_high_penalised_score(self) -> None:
        low_entropy = BayesianBeliefState(mu=0.9, entropy=0.05, n_observations=20)
        high_entropy = BayesianBeliefState(mu=0.9, entropy=0.85, n_observations=0)
        assert entropy_penalty(low_entropy) > entropy_penalty(high_entropy)

    def test_maximum_entropy_heavily_penalised(self) -> None:
        belief = BayesianBeliefState(mu=0.95, entropy=1.0, n_observations=0)
        score = entropy_penalty(belief)
        assert score < 0.5

    def test_zero_entropy_identity(self) -> None:
        belief = BayesianBeliefState(mu=0.88, entropy=0.0, n_observations=10)
        score = entropy_penalty(belief)
        assert score == pytest.approx(belief.mu, abs=0.05)

    def test_penalty_increases_monotonically_with_entropy(self) -> None:
        entropies = [0.0, 0.25, 0.5, 0.75, 1.0]
        scores = [
            entropy_penalty(BayesianBeliefState(mu=0.8, entropy=e, n_observations=5))
            for e in entropies
        ]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


# ── Class 9: PacketEnvelope safety ────────────────────────────────────────────


class TestPacketEnvelopeSafety:
    def test_belief_state_never_mutated_by_update(self) -> None:
        original = BayesianBeliefState(mu=0.7, entropy=0.3, n_observations=4)
        original_mu = original.mu
        _ = bayesian_update(original, trust=0.9)
        assert original.mu == original_mu

    def test_rescore_shallow_copy_semantics(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        originals = [dict(c) for c in sample_candidates]
        rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        for orig, current in zip(originals, sample_candidates):
            assert "belief_score" not in current or orig == {
                k: v for k, v in current.items() if k != "belief_score"
            }

    def test_rescore_output_new_objects(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        result_ids = {id(c) for c in result}
        input_ids = {id(c) for c in sample_candidates}
        assert result_ids.isdisjoint(input_ids)

    def test_content_hash_determinism_across_calls(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        def _hash_result(result: list[dict]) -> str:
            payload = json.dumps(
                [{k: v for k, v in sorted(c.items())} for c in result],
                sort_keys=True,
                default=str,
            )
            return hashlib.sha256(payload.encode()).hexdigest()

        r1 = rescore_candidates(
            candidates=copy.deepcopy(sample_candidates),
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        r2 = rescore_candidates(
            candidates=copy.deepcopy(sample_candidates),
            dimension_keys=["geo_score", "community_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert _hash_result(r1) == _hash_result(r2)


# ── Class 10: Spec Compliance ──────────────────────────────────────────────────


class TestSpecCompliance:
    def test_trust_tier_constants_defined(self) -> None:
        assert hasattr(TRUST_ENTAILMENT, "__float__")
        assert hasattr(TRUST_NEUTRAL, "__float__")
        assert hasattr(TRUST_CONTRADICTION, "__float__")

    def test_trust_tier_ordering(self) -> None:
        assert TRUST_CONTRADICTION < TRUST_NEUTRAL < TRUST_ENTAILMENT

    def test_trust_tier_semantic_values(self) -> None:
        assert TRUST_ENTAILMENT >= 0.90
        assert 0.50 <= TRUST_NEUTRAL <= 0.70
        assert TRUST_CONTRADICTION <= 0.15

    def test_hop_status_enum_values(self) -> None:
        assert HopStatus.COMPLETED in HopStatus
        assert HopStatus.FAILED in HopStatus
        assert HopStatus.CONTRADICTED in HopStatus
        assert HopStatus.SKIPPED in HopStatus
        assert HopStatus.PENDING in HopStatus

    def test_ceg_scoring_uses_multi_parent_not_chain(
        self, sample_candidates: list[dict[str, Any]]
    ) -> None:
        dims = ["geo_score", "community_score", "temporal_score", "price_score"]
        result = rescore_candidates(
            candidates=sample_candidates,
            dimension_keys=dims,
            prior_key="confidence",
            score_key="belief_score",
        )
        c = sample_candidates[0]
        prior_mu = c.get("confidence", 0.5)
        prior = BayesianBeliefState(
            mu=prior_mu,
            entropy=1.0 - prior_mu,
            n_observations=0,
        )
        trust_scores = [c.get(k, TRUST_NEUTRAL) for k in dims]
        expected_belief = multi_parent_propagation(
            trust_scores=trust_scores, prior=prior
        )
        result_map = {r["id"]: r for r in result}
        assert result_map["cmp_001"]["belief_score"] == pytest.approx(
            entropy_penalty(expected_belief), abs=1e-4
        )

    def test_convergence_threshold_gate(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        for _ in range(10):
            belief = bayesian_update(belief, trust=TRUST_ENTAILMENT)
        assert belief.posterior_score >= 0.85

    def test_contradiction_spiral_stays_bounded(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for _ in range(20):
            belief = bayesian_update(belief, trust=TRUST_CONTRADICTION)
        assert belief.mu >= 0.0
        assert belief.mu <= 1.0
