"""Unit tests for FieldConfidenceMap."""

from app.models.field_confidence import FieldConfidenceMap, FieldSource, compute_field_confidence


def test_full_agreement_yields_confidence_one():
    payloads = [
        {"materials_handled": ["HDPE", "LDPE"]},
        {"materials_handled": ["HDPE", "LDPE"]},
        {"materials_handled": ["HDPE", "LDPE"]},
    ]
    result = compute_field_confidence(payloads, {"materials_handled": "list"})
    fc = result.fields.get("materials_handled")
    assert fc is not None
    assert fc.confidence == 1.0


def test_partial_agreement_scores_correctly():
    payloads = [
        {"contamination_tolerance": 0.03},
        {"contamination_tolerance": 0.03},
        {"contamination_tolerance": 0.05},  # disagrees
        {"contamination_tolerance": 0.03},
        {"contamination_tolerance": 0.03},
    ]
    result = compute_field_confidence(payloads, {"contamination_tolerance": "float"})
    fc = result.fields.get("contamination_tolerance")
    assert fc is not None
    assert abs(fc.confidence - 0.8) < 0.01


def test_empty_payload_list_returns_empty_map():
    result = compute_field_confidence([], {})
    assert len(result.fields) == 0


def test_weakest_fields_sorted():
    fcm = FieldConfidenceMap()
    from app.models.field_confidence import FieldConfidence

    fcm.fields["a"] = FieldConfidence(
        field_name="a", value="x", confidence=0.9, source=FieldSource.ENRICHMENT
    )
    fcm.fields["b"] = FieldConfidence(
        field_name="b", value="y", confidence=0.3, source=FieldSource.ENRICHMENT
    )
    fcm.fields["c"] = FieldConfidence(
        field_name="c", value="z", confidence=0.6, source=FieldSource.ENRICHMENT
    )
    weakest = fcm.weakest_fields(2)
    assert weakest[0].field_name == "b"
    assert weakest[1].field_name == "c"


def test_coverage_ratio():
    fcm = FieldConfidenceMap()
    from app.models.field_confidence import FieldConfidence

    fcm.fields["a"] = FieldConfidence(
        field_name="a", value=1, confidence=0.9, source=FieldSource.CRM
    )
    ratio = fcm.coverage_ratio(["a", "b", "c"])
    assert abs(ratio - 1 / 3) < 0.01
