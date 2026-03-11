"""Tests for app/models/field_confidence.py

Covers: FieldSource enum, FieldConfidence model, FieldConfidenceMap aggregate,
        compute_field_confidences builder function.

Source: 290 lines | Target coverage: 85%
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.models.field_confidence import (
    FieldConfidence,
    FieldConfidenceMap,
    FieldSource,
    compute_field_confidences,
)


# ---------------------------------------------------------------------------
# FieldSource enum
# ---------------------------------------------------------------------------

class TestFieldSource:
    """Verify all expected enum members exist and serialise correctly."""

    def test_all_members_present(self):
        assert set(FieldSource) == {
            FieldSource.CRM,
            FieldSource.ENRICHMENT,
            FieldSource.INFERENCE,
            FieldSource.MANUAL,
            FieldSource.SEED,
        }

    def test_string_values(self):
        assert FieldSource.CRM.value == "crm"
        assert FieldSource.ENRICHMENT.value == "enrichment"
        assert FieldSource.INFERENCE.value == "inference"
        assert FieldSource.MANUAL.value == "manual"
        assert FieldSource.SEED.value == "seed"

    def test_string_enum_comparison(self):
        assert FieldSource.CRM == "crm"
        assert FieldSource.ENRICHMENT == "enrichment"


# ---------------------------------------------------------------------------
# FieldConfidence model
# ---------------------------------------------------------------------------

class TestFieldConfidence:
    """Tests for FieldConfidence Pydantic model."""

    def test_confidence_clamps_negative_to_zero(self):
        fc = FieldConfidence(field_name="x", confidence=-0.5)
        assert fc.confidence == 0.0

    def test_confidence_clamps_above_one_to_one(self):
        fc = FieldConfidence(field_name="x", confidence=1.5)
        assert fc.confidence == 1.0

    def test_confidence_accepts_valid_range(self):
        fc = FieldConfidence(field_name="x", confidence=0.73)
        assert fc.confidence == 0.73

    def test_confidence_boundary_zero(self):
        fc = FieldConfidence(field_name="x", confidence=0.0)
        assert fc.confidence == 0.0

    def test_confidence_boundary_one(self):
        fc = FieldConfidence(field_name="x", confidence=1.0)
        assert fc.confidence == 1.0

    def test_variation_agreement_optional_none(self):
        fc = FieldConfidence(
            field_name="x", source=FieldSource.CRM, variation_agreement=None
        )
        assert fc.variation_agreement is None

    def test_variation_agreement_valid_float(self):
        fc = FieldConfidence(field_name="x", variation_agreement=0.80)
        assert fc.variation_agreement == 0.80

    def test_kb_fragment_ids_default_empty_list(self):
        fc = FieldConfidence(field_name="x")
        assert fc.kb_fragment_ids == []

    def test_kb_fragment_ids_populated(self):
        fc = FieldConfidence(field_name="x", kb_fragment_ids=["polymers.hdpe.mfi"])
        assert fc.kb_fragment_ids == ["polymers.hdpe.mfi"]

    def test_pass_discovered_min_value_1(self):
        fc = FieldConfidence(field_name="x", pass_discovered=1)
        assert fc.pass_discovered == 1

    def test_pass_discovered_rejects_zero(self):
        with pytest.raises(ValidationError):
            FieldConfidence(field_name="x", pass_discovered=0)

    def test_source_default_is_enrichment(self):
        fc = FieldConfidence(field_name="x")
        assert fc.source == FieldSource.ENRICHMENT

    def test_source_accepts_all_enum_values(self):
        for source in FieldSource:
            fc = FieldConfidence(field_name="x", source=source)
            assert fc.source == source

    def test_value_accepts_any_type(self):
        assert FieldConfidence(field_name="x", value="HDPE").value == "HDPE"
        assert FieldConfidence(field_name="x", value=3.5).value == 3.5
        assert FieldConfidence(field_name="x", value=["A", "B"]).value == ["A", "B"]
        assert FieldConfidence(field_name="x", value=None).value is None

    def test_model_dump_json_serializable(self):
        fc = FieldConfidence(
            field_name="polymer_type",
            value="HDPE",
            confidence=0.9,
            source=FieldSource.ENRICHMENT,
        )
        data = fc.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["field_name"] == "polymer_type"
        assert data["confidence"] == 0.9
        json.dumps(data)  # must not raise


# ---------------------------------------------------------------------------
# FieldConfidenceMap aggregate
# ---------------------------------------------------------------------------

class TestFieldConfidenceMap:
    """Tests for FieldConfidenceMap aggregate container."""

    def test_set_adds_field(self):
        fcm = FieldConfidenceMap()
        fc = FieldConfidence(field_name="polymer_type", value="HDPE", confidence=0.9)
        fcm.set(fc)
        assert "polymer_type" in fcm
        assert fcm.get("polymer_type") is fc

    def test_set_replaces_existing_field(self):
        fcm = FieldConfidenceMap()
        fc1 = FieldConfidence(field_name="x", value="A", confidence=0.5)
        fc2 = FieldConfidence(field_name="x", value="B", confidence=0.9)
        fcm.set(fc1)
        fcm.set(fc2)
        assert fcm.get("x").value == "B"
        assert len(fcm) == 1

    def test_merge_keeps_higher_confidence(self):
        fcm1 = FieldConfidenceMap()
        fcm1.set(FieldConfidence(field_name="x", confidence=0.7))
        fcm2 = FieldConfidenceMap()
        fcm2.set(FieldConfidence(field_name="x", confidence=0.9))
        fcm1.merge(fcm2)
        assert fcm1.get("x").confidence == 0.9

    def test_merge_keeps_existing_when_higher(self):
        fcm1 = FieldConfidenceMap()
        fcm1.set(FieldConfidence(field_name="x", confidence=0.95))
        fcm2 = FieldConfidenceMap()
        fcm2.set(FieldConfidence(field_name="x", confidence=0.6))
        fcm1.merge(fcm2)
        assert fcm1.get("x").confidence == 0.95

    def test_merge_adds_new_fields(self):
        fcm1 = FieldConfidenceMap()
        fcm1.set(FieldConfidence(field_name="a", confidence=0.8))
        fcm2 = FieldConfidenceMap()
        fcm2.set(FieldConfidence(field_name="b", confidence=0.7))
        fcm1.merge(fcm2)
        assert len(fcm1) == 2

    def test_weakest_fields_sorted_ascending(self, sample_field_confidence_map):
        weakest = sample_field_confidence_map.weakest_fields(3)
        assert len(weakest) == 3
        confs = [f.confidence for f in weakest]
        assert confs == sorted(confs)
        assert weakest[0].field_name == "facility_tier"  # 0.45

    def test_weakest_fields_n_larger_than_map(self):
        fcm = FieldConfidenceMap()
        fcm.set(FieldConfidence(field_name="x", confidence=0.5))
        result = fcm.weakest_fields(10)
        assert len(result) == 1

    def test_fields_below_threshold(self, sample_field_confidence_map):
        below = sample_field_confidence_map.fields_below_threshold(0.65)
        names = {f.field_name for f in below}
        assert "facility_tier" in names  # 0.45
        assert "polymer_type" not in names  # 0.92

    def test_fields_above_threshold(self, sample_field_confidence_map):
        above = sample_field_confidence_map.fields_above_threshold(0.65)
        names = {f.field_name for f in above}
        assert "polymer_type" in names  # 0.92
        assert "facility_tier" not in names  # 0.45

    def test_avg_confidence_calculation(self, sample_field_confidence_map):
        avg = sample_field_confidence_map.avg_confidence()
        expected = (0.92 + 0.68 + 0.45 + 0.88 + 1.0) / 5
        assert abs(avg - expected) < 0.001

    def test_empty_map_returns_zero_avg(self):
        fcm = FieldConfidenceMap()
        assert fcm.avg_confidence() == 0.0

    def test_coverage_ratio(self, sample_field_confidence_map):
        ratio = sample_field_confidence_map.coverage_ratio(10)
        assert ratio == 0.5  # 5 filled / 10 expected

    def test_coverage_ratio_zero_expected(self):
        fcm = FieldConfidenceMap()
        assert fcm.coverage_ratio(0) == 0.0

    def test_confident_fields_filters_by_threshold(self, sample_field_confidence_map):
        result = sample_field_confidence_map.confident_fields(0.85)
        assert "polymer_type" in result  # 0.92
        assert "material_grade" in result  # 0.88
        assert "Name" in result  # 1.0
        assert "facility_tier" not in result  # 0.45
        assert "contamination_pct" not in result  # 0.68

    def test_source_breakdown_counts_by_enum(self, sample_field_confidence_map):
        breakdown = sample_field_confidence_map.source_breakdown()
        assert breakdown[FieldSource.ENRICHMENT] == 2
        assert breakdown[FieldSource.INFERENCE] == 2
        assert breakdown[FieldSource.CRM] == 1

    def test_to_flat_dict_serialization(self, sample_field_confidence_map):
        flat = sample_field_confidence_map.to_flat_dict()
        assert isinstance(flat, dict)
        assert "polymer_type" in flat
        assert flat["polymer_type"]["confidence"] == 0.92
        json.dumps(flat)  # must be JSON-serializable

    def test_from_flat_dict_deserialization(self, sample_field_confidence_map):
        flat = sample_field_confidence_map.to_flat_dict()
        restored = FieldConfidenceMap.from_flat_dict(flat)
        assert len(restored) == len(sample_field_confidence_map)
        assert restored.get("polymer_type").confidence == 0.92

    def test_roundtrip_serialization(self, sample_field_confidence_map):
        flat = sample_field_confidence_map.to_flat_dict()
        restored = FieldConfidenceMap.from_flat_dict(flat)
        assert restored.to_flat_dict() == flat

    def test_len_and_contains(self):
        fcm = FieldConfidenceMap()
        assert len(fcm) == 0
        assert "x" not in fcm
        fcm.set(FieldConfidence(field_name="x"))
        assert len(fcm) == 1
        assert "x" in fcm

    def test_iter_yields_field_confidences(self, sample_field_confidence_map):
        items = list(sample_field_confidence_map)
        assert all(isinstance(item, FieldConfidence) for item in items)
        assert len(items) == 5

    def test_field_names_returns_list(self, sample_field_confidence_map):
        names = sample_field_confidence_map.field_names()
        assert isinstance(names, list)
        assert "polymer_type" in names


# ---------------------------------------------------------------------------
# compute_field_confidences builder
# ---------------------------------------------------------------------------

class TestComputeFieldConfidences:
    """Tests for compute_field_confidences builder function."""

    def test_perfect_agreement_high_confidence(self, mock_consensus_payloads):
        fcm = compute_field_confidences(
            mock_consensus_payloads, total_attempted=5, pass_number=1
        )
        # polymer_type: 5/5 agree on "HDPE"
        pt = fcm.get("polymer_type")
        assert pt is not None
        assert pt.value == "HDPE"
        assert pt.confidence > 0.7
        assert pt.variation_agreement == 1.0

    def test_partial_agreement_lower_confidence(self, mock_consensus_payloads):
        fcm = compute_field_confidences(
            mock_consensus_payloads, total_attempted=5, pass_number=1
        )
        # mfi_range: 4/5 agree on "0.5-3.0", 1 disagrees
        mr = fcm.get("mfi_range")
        assert mr is not None
        assert mr.value == "0.5-3.0"
        assert mr.variation_agreement == 0.8

    def test_total_attempted_penalty(self):
        payloads = [
            {"confidence": 0.9, "field_a": "val"},
            {"confidence": 0.85, "field_a": "val"},
            {"confidence": 0.88, "field_a": "val"},
        ]
        fcm = compute_field_confidences(payloads, total_attempted=5, pass_number=1)
        fc = fcm.get("field_a")
        # penalty = 3/5 = 0.6, agreement = 1.0, avg_conf ~0.877
        # combined = 1.0 * 0.877 * 0.6 * 1.0 ≈ 0.526
        assert fc is not None
        assert fc.confidence < 0.9  # penalised

    def test_value_consensus_picks_most_common(self):
        payloads = [
            {"confidence": 0.8, "x": "A"},
            {"confidence": 0.8, "x": "A"},
            {"confidence": 0.8, "x": "B"},
        ]
        fcm = compute_field_confidences(payloads, total_attempted=3)
        assert fcm.get("x").value == "A"
        assert fcm.get("x").variation_agreement == pytest.approx(0.6667, abs=0.01)

    def test_kb_fragment_ids_attached(self):
        payloads = [{"confidence": 0.9, "x": "val"}]
        fcm = compute_field_confidences(
            payloads,
            total_attempted=1,
            kb_fragment_ids=["polymers.hdpe.mfi"],
        )
        assert fcm.get("x").kb_fragment_ids == ["polymers.hdpe.mfi"]

    def test_pass_number_propagates(self):
        payloads = [{"confidence": 0.9, "x": "val"}]
        fcm = compute_field_confidences(payloads, total_attempted=1, pass_number=3)
        assert fcm.get("x").pass_discovered == 3

    def test_empty_payloads_returns_empty_map(self):
        fcm = compute_field_confidences([], total_attempted=5)
        assert len(fcm) == 0
        assert fcm.avg_confidence() == 0.0

    def test_reserved_fields_excluded(self):
        payloads = [
            {
                "confidence": 0.9,
                "tokens_used": 1200,
                "processing_time_ms": 500,
                "polymer_type": "HDPE",
            }
        ]
        fcm = compute_field_confidences(payloads, total_attempted=1)
        assert "confidence" not in fcm
        assert "tokens_used" not in fcm
        assert "processing_time_ms" not in fcm
        assert "polymer_type" in fcm

    def test_hashable_value_lists_and_dicts(self):
        payloads = [
            {"confidence": 0.9, "certs": ["ISO 9001", "R2"]},
            {"confidence": 0.85, "certs": ["ISO 9001", "R2"]},
        ]
        fcm = compute_field_confidences(payloads, total_attempted=2)
        assert fcm.get("certs") is not None
        assert fcm.get("certs").value == ["ISO 9001", "R2"]

    def test_source_always_enrichment(self, mock_consensus_payloads):
        fcm = compute_field_confidences(
            mock_consensus_payloads, total_attempted=5
        )
        for fc in fcm:
            assert fc.source == FieldSource.ENRICHMENT

    def test_single_payload_no_penalty_when_one_attempted(self):
        payloads = [{"confidence": 0.9, "x": "val"}]
        fcm = compute_field_confidences(payloads, total_attempted=1)
        fc = fcm.get("x")
        # agreement=1.0, avg_conf=0.9, penalty=1.0, value_agreement=1.0
        assert fc.confidence == pytest.approx(0.9, abs=0.01)
