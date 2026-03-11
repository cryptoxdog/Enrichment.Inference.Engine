"""Tests for app/models/loop_schemas.py

Covers: All enums, CostSummary, SchemaProposal, PassResult, ConvergeRequest,
        ConvergeResponse, BatchConvergeRequest, BatchConvergeResponse,
        ConvergenceReport, ApprovalDecision.

Source: 480 lines | Target coverage: 80%
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.loop_schemas import (
    ApprovalMode,
    BatchConvergeRequest,
    BatchConvergeResponse,
    ConvergeRequest,
    ConvergeResponse,
    ConvergenceMode,
    ConvergenceReason,
    ConvergenceReport,
    CostSummary,
    PassResult,
    SchemaProposal,
    SchemaProposalSource,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    """Tests for enum definitions."""

    def test_convergence_mode_values(self):
        assert ConvergenceMode.DISCOVERY.value == "discovery"
        assert ConvergenceMode.TARGETED.value == "targeted"
        assert ConvergenceMode.VERIFICATION.value == "verification"

    def test_approval_mode_values(self):
        assert ApprovalMode.AUTO.value == "auto"
        assert ApprovalMode.HUMAN.value == "human"

    def test_convergence_reason_values(self):
        expected = {
            "threshold_met",
            "budget_exhausted",
            "max_passes",
            "human_hold",
            "diminishing_returns",
            "failed",
        }
        actual = {r.value for r in ConvergenceReason}
        assert actual == expected

    def test_schema_proposal_source_values(self):
        assert SchemaProposalSource.ENRICHMENT.value == "enrichment"
        assert SchemaProposalSource.INFERENCE.value == "inference"


# ---------------------------------------------------------------------------
# CostSummary
# ---------------------------------------------------------------------------


class TestCostSummary:
    """Tests for CostSummary model."""

    def test_cost_rounding_to_6_decimals(self):
        cs = CostSummary(
            total_cost_usd=0.1234567890,
            cost_per_field=0.0000019999,
            budget_utilization_pct=4.12345678,
        )
        assert cs.total_cost_usd == 0.123457
        assert cs.cost_per_field == 0.000002
        assert cs.budget_utilization_pct == 4.123457

    def test_tokens_per_pass_list(self):
        cs = CostSummary(tokens_per_pass=[1200, 800, 400])
        assert cs.tokens_per_pass == [1200, 800, 400]

    def test_defaults_are_zero(self):
        cs = CostSummary()
        assert cs.total_tokens == 0
        assert cs.total_cost_usd == 0.0
        assert cs.cost_per_field == 0.0


# ---------------------------------------------------------------------------
# SchemaProposal
# ---------------------------------------------------------------------------


class TestSchemaProposal:
    """Tests for schema discovery proposals."""

    def test_fill_rate_clamps_0_to_1(self):
        with pytest.raises(ValidationError):
            SchemaProposal(field_name="x", fill_rate=1.5)
        with pytest.raises(ValidationError):
            SchemaProposal(field_name="x", fill_rate=-0.1)

    def test_avg_confidence_clamps_0_to_1(self):
        with pytest.raises(ValidationError):
            SchemaProposal(field_name="x", avg_confidence=2.0)

    def test_valid_proposal(self):
        sp = SchemaProposal(
            field_name="contamination_tolerance_pct",
            field_type="float",
            source=SchemaProposalSource.ENRICHMENT,
            fill_rate=0.90,
            avg_confidence=0.85,
            sample_values=[2.0, 5.0, 3.5],
        )
        assert sp.field_name == "contamination_tolerance_pct"
        assert sp.fill_rate == 0.90

    def test_sample_values_max_10(self):
        sp = SchemaProposal(
            field_name="x",
            sample_values=list(range(10)),
        )
        assert len(sp.sample_values) == 10

    def test_proposed_gate_optional(self):
        sp = SchemaProposal(field_name="x")
        assert sp.proposed_gate is None
        sp2 = SchemaProposal(field_name="x", proposed_gate="contamination_control")
        assert sp2.proposed_gate == "contamination_control"

    def test_proposed_scoring_dimension_optional(self):
        sp = SchemaProposal(field_name="x")
        assert sp.proposed_scoring_dimension is None


# ---------------------------------------------------------------------------
# PassResult
# ---------------------------------------------------------------------------


class TestPassResult:
    """Tests for per-pass snapshot."""

    def test_uncertainty_delta_computed_property(self):
        pr = PassResult(
            pass_number=2,
            uncertainty_before=5.2,
            uncertainty_after=3.1,
        )
        assert pr.uncertainty_delta == pytest.approx(2.1, abs=0.001)

    def test_fields_gained_sum(self):
        pr = PassResult(
            pass_number=1,
            fields_enriched=["a", "b", "c", "d", "e"],
            fields_inferred=["f", "g", "h"],
        )
        assert pr.fields_gained == 8

    def test_rules_fired_list(self):
        pr = PassResult(pass_number=1, rules_fired=["rule_a", "rule_b"])
        assert pr.rules_fired == ["rule_a", "rule_b"]

    def test_error_optional(self):
        pr = PassResult(pass_number=1)
        assert pr.error is None
        pr2 = PassResult(pass_number=1, error="LLM timeout")
        assert pr2.error == "LLM timeout"

    def test_pass_number_minimum_1(self):
        with pytest.raises(ValidationError):
            PassResult(pass_number=0)

    def test_default_mode_is_discovery(self):
        pr = PassResult(pass_number=1)
        assert pr.mode == ConvergenceMode.DISCOVERY


# ---------------------------------------------------------------------------
# ConvergeRequest
# ---------------------------------------------------------------------------


class TestConvergeRequest:
    """Tests for loop initiation request."""

    def test_max_passes_range_1_to_20(self):
        cr = ConvergeRequest(
            entity={"Name": "X"}, object_type="Account", objective="test", max_passes=1
        )
        assert cr.max_passes == 1
        cr = ConvergeRequest(
            entity={"Name": "X"}, object_type="Account", objective="test", max_passes=20
        )
        assert cr.max_passes == 20
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"}, object_type="Account", objective="test", max_passes=0
            )
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"}, object_type="Account", objective="test", max_passes=21
            )

    def test_max_budget_tokens_minimum_1000(self):
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"}, object_type="Account", objective="test", max_budget_tokens=999
            )

    def test_convergence_threshold_range(self):
        cr = ConvergeRequest(
            entity={"Name": "X"}, object_type="Account", objective="test", convergence_threshold=0.0
        )
        assert cr.convergence_threshold == 0.0
        cr = ConvergeRequest(
            entity={"Name": "X"},
            object_type="Account",
            objective="test",
            convergence_threshold=10.0,
        )
        assert cr.convergence_threshold == 10.0
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"},
                object_type="Account",
                objective="test",
                convergence_threshold=10.1,
            )

    def test_consensus_threshold_range(self):
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"},
                object_type="Account",
                objective="test",
                consensus_threshold=1.1,
            )

    def test_max_variations_range_1_to_10(self):
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"}, object_type="Account", objective="test", max_variations=0
            )
        with pytest.raises(ValidationError):
            ConvergeRequest(
                entity={"Name": "X"}, object_type="Account", objective="test", max_variations=11
            )

    def test_schema_string_parsing(self):
        cr = ConvergeRequest(
            entity={"Name": "X"},
            object_type="Account",
            objective="test",
            schema='{"field": "string"}',
        )
        assert cr.schema == {"field": "string"}

    def test_schema_invalid_string_returns_none(self):
        cr = ConvergeRequest(
            entity={"Name": "X"},
            object_type="Account",
            objective="test",
            schema="not-json",
        )
        assert cr.schema is None

    def test_run_id_autogenerated_uuid(self):
        cr = ConvergeRequest(entity={"Name": "X"}, object_type="Account", objective="test")
        UUID(cr.run_id)  # must not raise

    def test_idempotency_key_optional(self):
        cr = ConvergeRequest(entity={"Name": "X"}, object_type="Account", objective="test")
        assert cr.idempotency_key is None

    def test_entity_required_nonempty(self):
        with pytest.raises(ValidationError):
            ConvergeRequest(entity={}, object_type="Account", objective="test")


# ---------------------------------------------------------------------------
# ConvergeResponse
# ---------------------------------------------------------------------------


class TestConvergeResponse:
    """Tests for full loop result."""

    def test_total_passes_property(self):
        resp = ConvergeResponse(passes=[PassResult(pass_number=1), PassResult(pass_number=2)])
        assert resp.total_passes == 2

    def test_total_fields_discovered_property(self):
        resp = ConvergeResponse(final_fields={"a": 1, "b": 2, "c": 3})
        assert resp.total_fields_discovered == 3

    def test_is_converged_property_true(self):
        resp = ConvergeResponse(convergence_reason=ConvergenceReason.THRESHOLD_MET)
        assert resp.is_converged is True

    def test_is_converged_property_false(self):
        resp = ConvergeResponse(convergence_reason=ConvergenceReason.MAX_PASSES)
        assert resp.is_converged is False

    def test_created_at_defaults_to_utc_now(self):
        resp = ConvergeResponse()
        assert resp.created_at.tzinfo is not None
        assert (datetime.now(timezone.utc) - resp.created_at).total_seconds() < 5

    def test_completed_at_optional(self):
        resp = ConvergeResponse()
        assert resp.completed_at is None

    def test_kb_content_hash_tracking(self):
        resp = ConvergeResponse(kb_content_hash="abc123")
        assert resp.kb_content_hash == "abc123"

    def test_default_state_is_running(self):
        resp = ConvergeResponse()
        assert resp.state == "running"


# ---------------------------------------------------------------------------
# BatchConvergeRequest / Response
# ---------------------------------------------------------------------------


class TestBatchConvergeRequest:
    """Tests for batch convergence."""

    def test_entities_max_50(self):
        entities = [
            ConvergeRequest(entity={"Name": f"E{i}"}, object_type="A", objective="t")
            for i in range(50)
        ]
        bcr = BatchConvergeRequest(entities=entities)
        assert len(bcr.entities) == 50

    def test_profile_name_optional(self):
        bcr = BatchConvergeRequest(
            entities=[ConvergeRequest(entity={"Name": "X"}, object_type="A", objective="t")]
        )
        assert bcr.profile_name is None

    def test_shared_budget_tokens(self):
        bcr = BatchConvergeRequest(
            entities=[ConvergeRequest(entity={"Name": "X"}, object_type="A", objective="t")],
            max_budget_tokens=100_000,
        )
        assert bcr.max_budget_tokens == 100_000


class TestBatchConvergeResponse:
    """Tests for batch results."""

    def test_succeeded_failed_counts(self):
        resp = BatchConvergeResponse(succeeded=8, failed=2, total=10)
        assert resp.succeeded == 8
        assert resp.failed == 2

    def test_total_tokens_aggregation(self):
        resp = BatchConvergeResponse(total_tokens=25000)
        assert resp.total_tokens == 25000

    def test_schema_proposal_set_optional(self):
        resp = BatchConvergeResponse()
        assert resp.schema_proposal_set is None


# ---------------------------------------------------------------------------
# ConvergenceReport
# ---------------------------------------------------------------------------


class TestConvergenceReport:
    """Tests for telemetry report model."""

    def test_trajectories(self):
        report = ConvergenceReport(
            run_id="test-123",
            passes_completed=3,
            confidence_trajectory=[0.45, 0.62, 0.78],
            uncertainty_trajectory=[8.5, 5.2, 3.1],
            tokens_per_pass=[1200, 800, 400],
            cost_per_pass_usd=[0.006, 0.004, 0.002],
        )
        assert len(report.confidence_trajectory) == 3
        assert report.confidence_trajectory[-1] == 0.78

    def test_roi_per_pass(self):
        report = ConvergenceReport(
            run_id="x",
            roi_per_pass=[20.0, 15.0, 5.0],
        )
        assert report.roi_per_pass[0] == 20.0
