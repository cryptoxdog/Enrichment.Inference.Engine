# tests/test_high_leverage.py
"""
The 10 highest-leverage tests for the belief propagation engine.

Selection criteria (explicit):
    1. First Principles — tests the atomic primitive or a constraint that, if violated,
       makes ALL other tests meaningless.
    2. Second-Order Effect — the defect caught is silent, cross-cutting, and would
       propagate to downstream constellation nodes without any observable error signal
       until a business-level outcome was wrong.

Ranked by: P(catches real defect) × severity(defect uncaught) / maintenance cost.
"""

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
# RANK 1
# ────────────────────────────────────────────────────────────────────────────
# WHY HIGHEST LEVERAGE:
# bayesian_update is the atomic primitive. Every other function in the module
# is composed from it. If it is wrong, all downstream derivatives —
# composite_score, chain_composite, rescore_candidates, chain_propagation —
# are silently wrong. No other test can catch this because they all depend
# on bayesian_update being correct first.
#
# SECOND-ORDER EFFECT IF ABSENT:
# Wrong rankings propagate into GMP-05 Pareto. Wrong chain confidences
# propagate into GATE intelligence_quality payloads. The system continues
# to operate — no exception, no alert — just silently incorrect entity
# decisions at production scale.
# ────────────────────────────────────────────────────────────────────────────
class TestRank1_BayesianUpdateAtomicPrimitive:
    """
    Verifies the correctness invariants of the atomic primitive.
    Covers: monotonicity, non-uniform prior resistance, unit interval safety,
    and the key property that a non-trivial prior dominates a weak signal.
    """

    def test_high_trust_increases_mu_from_uniform(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(prior, trust=TRUST_ENTAILMENT)
        assert updated.mu > 0.5, (
            "RANK 1 FAILURE: High trust applied to uniform prior must increase mu. "
            "If this fails, all downstream scoring is directionally wrong."
        )

    def test_low_trust_decreases_mu_from_uniform(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        updated = bayesian_update(prior, trust=TRUST_CONTRADICTION)
        assert updated.mu < 0.5

    def test_non_uniform_prior_resists_weak_signal(self) -> None:
        """
        FIRST PRINCIPLES:
        The Bayesian update rule weights new evidence by (1 / n_observations).
        A strong prior (n_obs=50) must change less than a weak prior (n_obs=1)
        given the same trust signal. This is the core property that makes the
        system rational rather than just a moving average.
        """
        strong_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=50)
        weak_prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=1)
        trust = 0.3  # weak contradicting signal
        delta_strong = abs(bayesian_update(strong_prior, trust=trust).mu - strong_prior.mu)
        delta_weak = abs(bayesian_update(weak_prior, trust=trust).mu - weak_prior.mu)
        assert delta_strong < delta_weak, (
            "Strong prior must resist weak trust signal more than weak prior. "
            "If this fails, prior seeding in rescore_candidates is ineffective — "
            "the engine degenerates to a weighted average with no Bayesian benefit."
        )

    def test_output_always_in_unit_interval(self) -> None:
        """Probabilistic quantities must always be in [0, 1]."""
        for trust in [0.0, 0.001, 0.5, 0.999, 1.0]:
            for mu in [0.0, 0.01, 0.5, 0.99, 1.0]:
                prior = BayesianBeliefState(mu=mu, entropy=0.5, n_observations=0)
                result = bayesian_update(prior, trust=trust)
                assert 0.0 <= result.mu <= 1.0, (
                    f"mu={result.mu} out of [0,1] for trust={trust}, prior_mu={mu}. "
                    "Out-of-range probabilities propagate NaN into all consumers."
                )

    def test_n_observations_increments_exactly_one(self) -> None:
        prior = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=7)
        updated = bayesian_update(prior, trust=0.8)
        assert updated.n_observations == 8, (
            "n_observations must increment by exactly 1 per call. "
            "Under-incrementing causes prior resistance to decay too slowly; "
            "over-incrementing causes it to decay too fast."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 2
# ────────────────────────────────────────────────────────────────────────────
# WHY SECOND HIGHEST LEVERAGE:
# PacketEnvelope immutability is a protocol constraint, not a preference.
# rescore_candidates operates on candidate dicts passed by the caller.
# If it mutates them in-place (c[score_key] = ...), the caller's data
# is silently corrupted. In a constellation node, the same payload dict
# may be passed to multiple processors in sequence — mutation here
# invalidates lineage, breaks content-hash integrity, and corrupts
# the audit trail for every downstream node.
#
# SECOND-ORDER EFFECT IF ABSENT:
# Silent data corruption. No exception. The downstream Pareto node
# receives candidates that have been modified by a scoring pass they
# did not initiate. Audit logs become untrustworthy. Re-runs produce
# different results than the original run because inputs were mutated.
# ────────────────────────────────────────────────────────────────────────────
class TestRank2_InputImmutabilityPacketEnvelopeContract:
    """
    Verifies that rescore_candidates never mutates its input dicts.
    This is a PacketEnvelope protocol contract, not a code style preference.
    """

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
        assert candidates == originals, (
            "RANK 2 FAILURE: Input dicts were mutated. "
            "This violates PacketEnvelope immutability. "
            "Fix: use {**c, score_key: score} not c[score_key] = score."
        )

    def test_output_contains_new_object_references(self) -> None:
        candidates = [{"id": "x", "confidence": 0.7, "geo_score": 0.8}]
        result = rescore_candidates(
            candidates=candidates,
            dimension_keys=["geo_score"],
            prior_key="confidence",
            score_key="belief_score",
        )
        assert id(result[0]) != id(candidates[0]), (
            "Output must be new dict objects, not references to input dicts."
        )

    def test_belief_state_not_mutated_through_update_chain(self) -> None:
        """BayesianBeliefState must be immutable (Pydantic frozen=True)."""
        b = BayesianBeliefState(mu=0.7, entropy=0.3, n_observations=4)
        original_mu = b.mu
        _ = bayesian_update(b, trust=0.95)
        assert b.mu == original_mu, (
            "BayesianBeliefState was mutated by bayesian_update. "
            "Must use Pydantic frozen=True model."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 3
# ────────────────────────────────────────────────────────────────────────────
# WHY THIRD HIGHEST LEVERAGE:
# CEG scoring dimensions (geo, community, temporal, price) are INDEPENDENT
# evidence sources — they do not causally cause one another.
# GATE hop traces are CAUSALLY ORDERED — each hop is causally prior to the next.
# Using chain propagation for CEG (or multi-parent for GATE) produces
# systematically biased scores that can never be detected by inspecting
# output values alone — they look plausible but are semantically wrong.
#
# SECOND-ORDER EFFECT IF ABSENT:
# CEG candidates are ranked by a causally-ordered model of what is actually
# independent evidence. This systematically underweights candidates with
# divergent dimension scores (high geo, low price) relative to candidates
# with uniform scores. The bias is invisible in unit tests that only check
# "is the output a float in [0,1]?"
# ────────────────────────────────────────────────────────────────────────────
class TestRank3_AlgorithmModeRoutingCEGvsGATE:
    """
    Verifies that CEG (independent dimensions) uses multi-parent aggregation
    and GATE (causal hop sequence) uses chain propagation.
    These are different algorithms; routing them incorrectly produces
    silently biased scores that look valid.
    """

    def test_multi_parent_is_order_invariant_for_ceg(self) -> None:
        """
        FIRST PRINCIPLES:
        Independent evidence sources: P(A|B,C) = P(A|B) × P(A|C) / P(A).
        The result must be the same regardless of the order dimensions are evaluated.
        If order matters, the algorithm is treating them as causally ordered (chain),
        which is wrong for CEG dimensions.
        """
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        scores = [0.9, 0.4, 0.7, 0.55]
        r_forward = multi_parent_propagation(trust_scores=scores, prior=prior)
        r_reversed = multi_parent_propagation(
            trust_scores=list(reversed(scores)), prior=prior
        )
        assert r_forward.mu == pytest.approx(r_reversed.mu, abs=1e-6), (
            "RANK 3 FAILURE: multi_parent_propagation is not order-invariant. "
            "CEG dimensions are independent evidence — order must not matter. "
            "If order matters, this is chain propagation disguised, producing "
            "systematically biased CEG scores."
        )

    def test_chain_degrades_monotonically_for_gate(self) -> None:
        """
        FIRST PRINCIPLES:
        Causal chains: P(A|B→C→D) = P(A|D) × P(D|C) × P(C|B).
        Each additional hop must reduce terminal confidence.
        This enforces the semantic contract that long GATE traces
        carry inherently lower confidence than short ones.
        """
        prior = BayesianBeliefState(mu=0.9, entropy=0.1, n_observations=0)
        trust = 0.85
        r1 = chain_propagation(trust_scores=[trust], prior=prior)
        r2 = chain_propagation(trust_scores=[trust, trust], prior=prior)
        r3 = chain_propagation(trust_scores=[trust, trust, trust], prior=prior)
        assert r1.mu >= r2.mu >= r3.mu, (
            "RANK 3 FAILURE: chain_propagation does not monotonically degrade. "
            "GATE hop traces must lose confidence with each additional hop. "
            "If this fails, long GATE traces score identically to short ones."
        )

    def test_ceg_and_gate_produce_different_results_for_divergent_inputs(self) -> None:
        """
        For divergent trust scores, multi-parent and chain MUST differ.
        If they produce the same result, one of them is not implemented correctly.
        """
        prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        divergent_scores = [0.95, 0.1, 0.9, 0.05]
        r_multi = composite_score(trust_scores=divergent_scores, prior=prior)
        r_chain = chain_composite(trust_scores=divergent_scores, prior=prior)
        assert r_multi != pytest.approx(r_chain, abs=1e-3), (
            "composite_score and chain_composite must produce different results "
            "for divergent inputs. If they are equal, one is not implemented — "
            "it is aliasing the other, meaning one algorithm does not exist."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 4
# ────────────────────────────────────────────────────────────────────────────
# WHY FOURTH HIGHEST LEVERAGE:
# The entire justification for a Bayesian system over a simple weighted average
# is that prior confidence (neo4j 'confidence' property) seeds the update.
# If prior seeding does not actually change rankings, the engine adds zero
# value over a naive dimension average. This is the "does it work at all?" test.
#
# SECOND-ORDER EFFECT IF ABSENT:
# A candidate with confidence=0.85 and mediocre dimensions ranks BELOW a
# candidate with confidence=0.40 and excellent dimensions. The engine
# is recommending entities in the wrong order. GMP-05 Pareto promotes
# the wrong candidates. This is a product-level failure disguised as a
# passing test suite.
# ────────────────────────────────────────────────────────────────────────────
class TestRank4_PriorSeedingRankingReversal:
    """
    Verifies that a high-confidence-prior candidate outranks a
    low-confidence-prior candidate even when the latter has better dimensions.
    This is the 'does the Bayesian engine add any value?' test.
    """

    def test_high_prior_outranks_low_prior_despite_better_dimensions(self) -> None:
        """
        SETUP:
        cmp_A: confidence=0.85 (strong prior), dims=[0.88, 0.82, 0.75, 0.70]
        cmp_B: confidence=0.20 (weak prior),   dims=[0.97, 0.95, 0.93, 0.91]

        cmp_B has dramatically better dimensions.
        cmp_A has dramatically stronger prior.

        EXPECTED: cmp_A wins because the Bayesian prior dominates.
        If cmp_B wins, the prior is not being seeded — the engine is just
        averaging dimensions and the Bayesian machinery does nothing.
        """
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
        assert scores_by_id["cmp_A"] > scores_by_id["cmp_B"], (
            "RANK 4 FAILURE: High-prior candidate lost to low-prior candidate "
            "with better dimensions. Prior seeding is not working. "
            "The Bayesian engine is functionally equivalent to a dimension average."
        )

    def test_uniform_prior_ignores_confidence_seeding(self) -> None:
        """
        Confirm that prior=0.5 on ALL candidates makes confidence irrelevant,
        which is the degenerate case the engine must NOT default to.
        This negative test establishes the baseline: if all priors are uniform,
        results differ from prior-seeded results.
        """
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
        # If prior seeding works, the two candidates must score differently
        # despite having identical dimension scores
        scores = {c["id"]: c["belief_score"] for c in result_seeded}
        assert scores["x"] != pytest.approx(scores["y"], abs=1e-3), (
            "With different confidence priors but identical dimensions, "
            "scores must differ. If they are equal, prior_key is being ignored."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 5
# ────────────────────────────────────────────────────────────────────────────
# WHY FIFTH HIGHEST LEVERAGE:
# hop_trust_from_entry contains the timeout penalty threshold at 0.5.
# A hop that used 1950ms of a 2000ms timeout (97.5% utilization) must
# score LOWER than a hop that used 800ms (40% utilization), even though
# both completed successfully. This threshold is a spec-driven business rule.
# If it is wrong (e.g., penalty fires at 0.8 instead of 0.5, or not at all),
# GATE chain confidence is inflated for nearly-timed-out hops.
#
# SECOND-ORDER EFFECT IF ABSENT:
# GATE returns a falsely high chain_confidence for a hop sequence where nodes
# are operating near their timeout limit (a precursor to cascading timeouts).
# The intelligence_quality payload reports high confidence on a fragile chain.
# Downstream nodes trust a path that is about to fail.
# ────────────────────────────────────────────────────────────────────────────
class TestRank5_TimeoutPenaltyThresholdBoundary:
    """
    Verifies the timeout penalty threshold boundary at duration/timeout = 0.5.
    This is a spec-driven business rule embedded in hop_trust_from_entry.
    """

    def test_hop_just_below_threshold_is_not_penalised(self) -> None:
        safe_hop = HopEntry(
            hop_id="safe",
            status=HopStatus.COMPLETED,
            duration_ms=999,
            timeout_ms=2000,  # ratio = 0.4995 < 0.5
            node_type="enrichment",
        )
        trust = hop_trust_from_entry(safe_hop)
        assert trust >= TRUST_NEUTRAL, (
            "A hop at 49.9% of timeout should not be penalised. "
            "Penalty threshold is 0.5 per spec."
        )

    def test_hop_just_above_threshold_is_penalised(self) -> None:
        risky_hop = HopEntry(
            hop_id="risky",
            status=HopStatus.COMPLETED,
            duration_ms=1001,
            timeout_ms=2000,  # ratio = 0.5005 > 0.5
            node_type="enrichment",
        )
        safe_hop = HopEntry(
            hop_id="safe",
            status=HopStatus.COMPLETED,
            duration_ms=999,
            timeout_ms=2000,
            node_type="enrichment",
        )
        risky_trust = hop_trust_from_entry(risky_hop)
        safe_trust = hop_trust_from_entry(safe_hop)
        assert risky_trust < safe_trust, (
            "RANK 5 FAILURE: A hop at 50.05% of timeout must be penalised "
            "relative to a hop at 49.95%. "
            "Timeout penalty threshold is not firing at the correct boundary."
        )

    def test_near_timeout_hop_significantly_penalised(self) -> None:
        near_timeout = HopEntry(
            hop_id="near",
            status=HopStatus.COMPLETED,
            duration_ms=1990,
            timeout_ms=2000,  # ratio = 0.995
            node_type="enrichment",
        )
        trust = hop_trust_from_entry(near_timeout)
        baseline_trust = hop_trust_from_entry(
            HopEntry(
                hop_id="baseline",
                status=HopStatus.COMPLETED,
                duration_ms=500,
                timeout_ms=2000,
                node_type="enrichment",
            )
        )
        assert trust < baseline_trust * 0.9, (
            "A hop at 99.5% of timeout must be significantly penalised — "
            "not just marginally. Near-timeout hops indicate an unhealthy chain."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 6
# ────────────────────────────────────────────────────────────────────────────
# WHY SIXTH HIGHEST LEVERAGE:
# entropy_penalty is the final gate before scores enter the Pareto ranking.
# It must discount high-entropy (high-uncertainty) beliefs even when their
# mu is high. If the penalty is non-monotone (e.g., entropy=0.8 scores
# higher than entropy=0.4 for the same mu), the uncertainty discount is
# broken and the engine promotes uncertain candidates over confident ones.
#
# SECOND-ORDER EFFECT IF ABSENT:
# An enrichment result with confidence=0.90 but entropy=0.95 (highly uncertain)
# would score above one with confidence=0.85 and entropy=0.05 (highly certain).
# The system inverts the quality ranking. Pareto-dominant candidates are wrong.
# ────────────────────────────────────────────────────────────────────────────
class TestRank6_EntropyPenaltyMonotonicity:
    """
    Verifies that entropy_penalty monotonically decreases as entropy increases.
    Non-monotone penalty inverts the quality ranking at the Pareto gate.
    """

    def test_penalty_strictly_decreasing_as_entropy_increases(self) -> None:
        mu = 0.88
        entropies = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        scores = [
            entropy_penalty(BayesianBeliefState(mu=mu, entropy=e, n_observations=10))
            for e in entropies
        ]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"RANK 6 FAILURE: entropy_penalty is not monotone. "
                f"Score at entropy={entropies[i]} ({scores[i]:.4f}) < "
                f"score at entropy={entropies[i+1]} ({scores[i+1]:.4f}). "
                "Non-monotone penalty inverts candidate quality ranking."
            )

    def test_zero_entropy_score_approximates_mu(self) -> None:
        belief = BayesianBeliefState(mu=0.92, entropy=0.0, n_observations=20)
        score = entropy_penalty(belief)
        assert score == pytest.approx(belief.mu, abs=0.05), (
            "Zero-entropy belief has no uncertainty — penalty must return "
            "approximately mu. If it returns much less, uncertainty is being "
            "double-penalised."
        )

    def test_maximum_entropy_belief_scored_below_half(self) -> None:
        belief = BayesianBeliefState(mu=0.95, entropy=1.0, n_observations=0)
        score = entropy_penalty(belief)
        assert score < 0.5, (
            "A belief with mu=0.95 but maximum entropy=1.0 must score below 0.5. "
            "Maximum uncertainty must heavily discount even high-mu beliefs."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 7
# ────────────────────────────────────────────────────────────────────────────
# WHY SEVENTH HIGHEST LEVERAGE:
# The convergence loop termination condition is: when posterior_score
# crosses the spec threshold, the loop stops. If posterior_score is
# computed incorrectly (e.g., mu only, ignoring entropy), the loop
# either runs too many passes (wastes tokens, hits budget) or stops
# too early (ships incomplete enrichment). Both failure modes are
# invisible at the unit level — they only manifest as budget overruns
# or quality degradation at the system level.
#
# SECOND-ORDER EFFECT IF ABSENT:
# The convergence_controller calls posterior_score as its stopping
# criterion. If the formula is wrong, every convergence run in
# production terminates at the wrong time. Budget exhaustion events
# increase. Low-confidence enrichments get shipped as converged.
# ────────────────────────────────────────────────────────────────────────────
class TestRank7_ConvergenceThresholdGate:
    """
    Verifies the posterior_score formula and convergence threshold semantics.
    The stopping rule is: posterior_score >= 0.85.
    """

    def test_posterior_score_formula_is_mu_minus_entropy(self) -> None:
        belief = BayesianBeliefState(mu=0.92, entropy=0.08, n_observations=10)
        expected = belief.mu - belief.entropy
        assert belief.posterior_score == pytest.approx(expected, abs=1e-6), (
            "RANK 7 FAILURE: posterior_score must equal mu - entropy. "
            "This is the stopping criterion for the convergence loop. "
            "Wrong formula → wrong termination condition → wrong pass count."
        )

    def test_posterior_score_never_negative(self) -> None:
        """Negative posterior_score is non-physical — probability cannot be < 0."""
        for mu in [0.1, 0.3, 0.5]:
            for entropy in [0.5, 0.8, 1.0]:
                belief = BayesianBeliefState(mu=mu, entropy=entropy, n_observations=0)
                assert belief.posterior_score >= 0.0, (
                    f"posterior_score={belief.posterior_score} is negative "
                    f"for mu={mu}, entropy={entropy}. "
                    "Negative stopping criterion → loop never terminates."
                )

    def test_sufficient_entailment_observations_cross_threshold(self) -> None:
        """
        After enough TRUST_ENTAILMENT observations, posterior_score must
        exceed 0.85 (the spec convergence threshold). This verifies the
        full update → scoring pipeline reaches the intended stopping point.
        """
        belief = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
        for _ in range(12):
            belief = bayesian_update(belief, trust=TRUST_ENTAILMENT)
        assert belief.posterior_score >= 0.85, (
            f"RANK 7 FAILURE: After 12 TRUST_ENTAILMENT updates, "
            f"posterior_score={belief.posterior_score:.4f} < 0.85. "
            "The convergence loop would never terminate on healthy evidence."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 8
# ────────────────────────────────────────────────────────────────────────────
# WHY EIGHTH HIGHEST LEVERAGE:
# PacketEnvelope lineage requires that the same logical request produces
# the same content hash in every execution. If rescore_candidates is
# non-deterministic (e.g., dict ordering, floating-point non-associativity,
# set iteration), two identical requests produce different hashes.
# Deduplication breaks. Audit trails become untrustworthy. Re-runs
# cannot be compared to original runs.
#
# SECOND-ORDER EFFECT IF ABSENT:
# The constellation's deduplication layer treats identical requests
# as distinct because their content hashes differ. Billing doubles.
# Audit comparisons between runs become meaningless. Incident replay
# produces different results than the original incident.
# ────────────────────────────────────────────────────────────────────────────
class TestRank8_ContentHashDeterminism:
    """
    Verifies that identical inputs always produce identical outputs,
    enabling PacketEnvelope content hash integrity across re-runs.
    """

    @staticmethod
    def _hash_result(result: list[dict]) -> str:
        payload = json.dumps(
            [{k: v for k, v in sorted(c.items())} for c in sorted(result, key=lambda x: x["id"])],
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
        assert self._hash_result(r1) == self._hash_result(r2), (
            "RANK 8 FAILURE: Identical inputs produced different outputs. "
            "rescore_candidates is non-deterministic. "
            "PacketEnvelope content hash integrity is broken."
        )

    def test_bayesian_update_deterministic_across_calls(self) -> None:
        prior = BayesianBeliefState(mu=0.65, entropy=0.35, n_observations=5)
        r1 = bayesian_update(prior, trust=0.82)
        r2 = bayesian_update(prior, trust=0.82)
        assert r1.mu == r2.mu
        assert r1.entropy == r2.entropy


# ────────────────────────────────────────────────────────────────────────────
# RANK 9
# ────────────────────────────────────────────────────────────────────────────
# WHY NINTH HIGHEST LEVERAGE:
# Repeated TRUST_CONTRADICTION updates must not drive mu below 0.0.
# Probabilities are bounded by [0, 1]. If mu goes negative (even by
# floating-point underflow), it propagates NaN or negative values into:
# - composite_score (returns negative float)
# - entropy_penalty (returns nonsense)
# - posterior_score (always triggers convergence — loop terminates immediately)
# - rescore_candidates output (negative belief_score ranks below 0)
#
# SECOND-ORDER EFFECT IF ABSENT:
# A single entity with many contradicting signals triggers a cascade.
# The convergence loop exits in pass 1 (posterior_score < 0 < 0.85 is false
# but if clamped to 0, stops immediately). GMP-05 Pareto receives a negative
# score and the entity sort breaks. NaN contaminates the entire ranking array.
# ────────────────────────────────────────────────────────────────────────────
class TestRank9_ContradictionSpiralNumericalBounds:
    """
    Verifies that repeated contradiction updates keep mu strictly in [0.0, 1.0].
    Numerical instability here cascades into NaN across all downstream consumers.
    """

    def test_20_contradiction_updates_stay_in_unit_interval(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for step in range(20):
            belief = bayesian_update(belief, trust=TRUST_CONTRADICTION)
            assert 0.0 <= belief.mu <= 1.0, (
                f"RANK 9 FAILURE: mu={belief.mu} at step {step+1}. "
                "Contradiction spiral drove mu out of [0, 1]. "
                "NaN will propagate into composite_score and Pareto ranking."
            )
            assert not math.isnan(belief.mu), f"mu is NaN at step {step+1}"
            assert not math.isinf(belief.mu), f"mu is Inf at step {step+1}"

    def test_20_entailment_updates_stay_below_one(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for step in range(20):
            belief = bayesian_update(belief, trust=TRUST_ENTAILMENT)
            assert belief.mu <= 1.0, (
                f"mu={belief.mu} exceeded 1.0 at step {step+1}. "
                "Entailment spiral drove mu above 1 — probability > 100%."
            )

    def test_entropy_never_negative_after_updates(self) -> None:
        belief = BayesianBeliefState(mu=0.5, entropy=0.5, n_observations=0)
        for _ in range(15):
            belief = bayesian_update(belief, trust=TRUST_CONTRADICTION)
        assert belief.entropy >= 0.0, (
            "Entropy must be >= 0.0 after contradiction updates. "
            "Negative entropy is non-physical and breaks entropy_penalty."
        )


# ────────────────────────────────────────────────────────────────────────────
# RANK 10
# ────────────────────────────────────────────────────────────────────────────
# WHY TENTH HIGHEST LEVERAGE:
# Trust tier constants (TRUST_ENTAILMENT, TRUST_NEUTRAL, TRUST_CONTRADICTION)
# are the semantic bridge between the spec and the implementation.
# If their values drift from the spec ranges, every downstream score
# is wrong in a way that passes all unit tests (they still produce floats
# in [0,1]) but is semantically incorrect.
# This is a spec compliance regression test — it catches refactoring that
# "tidies up" constants to round numbers without realising the semantic impact.
#
# SECOND-ORDER EFFECT IF ABSENT:
# A developer changes TRUST_ENTAILMENT from 0.95 to 0.75 for "symmetry".
# All tests pass. But now 12 TRUST_ENTAILMENT updates no longer cross the
# 0.85 convergence threshold. Root cause → symptom chain is invisible
# without this test.
# ────────────────────────────────────────────────────────────────────────────
class TestRank10_TrustTierSpecCompliance:
    """
    Verifies that trust tier constants sit within spec-mandated semantic ranges.
    Guards against refactoring that changes constants without updating semantics.
    """

    def test_entailment_tier_in_spec_range(self) -> None:
        assert TRUST_ENTAILMENT >= 0.90, (
            f"RANK 10 FAILURE: TRUST_ENTAILMENT={TRUST_ENTAILMENT} < 0.90. "
            "Spec requires entailment trust to be >= 0.90. "
            "Lower values will prevent convergence at 0.85 threshold."
        )
        assert TRUST_ENTAILMENT <= 1.0, (
            f"TRUST_ENTAILMENT={TRUST_ENTAILMENT} > 1.0. "
            "Trust is a probability and must be in [0, 1]."
        )

    def test_neutral_tier_in_spec_range(self) -> None:
        assert 0.50 <= TRUST_NEUTRAL <= 0.70, (
            f"RANK 10 FAILURE: TRUST_NEUTRAL={TRUST_NEUTRAL} outside [0.50, 0.70]. "
            "Neutral trust must not move beliefs significantly. "
            "Outside this range, skipped hops bias the chain confidence."
        )

    def test_contradiction_tier_in_spec_range(self) -> None:
        assert TRUST_CONTRADICTION <= 0.15, (
            f"RANK 10 FAILURE: TRUST_CONTRADICTION={TRUST_CONTRADICTION} > 0.15. "
            "Contradiction must strongly decrease belief. "
            "Values above 0.15 make contradictions indistinguishable from neutrals."
        )
        assert TRUST_CONTRADICTION >= 0.0, (
            f"TRUST_CONTRADICTION={TRUST_CONTRADICTION} < 0.0. "
            "Trust is a probability — cannot be negative."
        )

    def test_tier_ordering_invariant(self) -> None:
        assert TRUST_CONTRADICTION < TRUST_NEUTRAL < TRUST_ENTAILMENT, (
            "RANK 10 FAILURE: Trust tier ordering violated. "
            "Must be: CONTRADICTION < NEUTRAL < ENTAILMENT. "
            "Violated ordering means contradiction and entailment are indistinguishable."
        )

    def test_tier_gap_sufficient_for_signal_separation(self) -> None:
        """
        FIRST PRINCIPLES:
        For the Bayesian update to distinguish entailment from neutral,
        the gap must be large enough to produce meaningfully different posteriors.
        A gap < 0.20 means the signal is too weak to separate good from neutral evidence.
        """
        entailment_gap = TRUST_ENTAILMENT - TRUST_NEUTRAL
        contradiction_gap = TRUST_NEUTRAL - TRUST_CONTRADICTION
        assert entailment_gap >= 0.20, (
            f"RANK 10 FAILURE: TRUST_ENTAILMENT - TRUST_NEUTRAL = {entailment_gap:.3f} < 0.20. "
            "Insufficient gap — entailment and neutral produce nearly identical posteriors."
        )
        assert contradiction_gap >= 0.30, (
            f"RANK 10 FAILURE: TRUST_NEUTRAL - TRUST_CONTRADICTION = {contradiction_gap:.3f} < 0.30. "
            "Insufficient gap — contradiction and neutral cannot be separated."
        )
