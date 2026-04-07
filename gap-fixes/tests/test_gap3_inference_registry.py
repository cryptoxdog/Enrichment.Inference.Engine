"""Gap-3 tests: inference function execution."""
import pytest
from engine.inference_rule_registry import (
    execute_rule, list_registered_rules, InferenceContext,
)

CTX = InferenceContext(tenant_id="t1", domain_id="plastics", pass_number=1)


def test_all_core_rules_registered():
    rules = list_registered_rules()
    for r in [
        "infer_company_size_tier",
        "infer_facility_tier_from_capacity",
        "infer_material_grade_from_mfi",
        "infer_contamination_tolerance",
        "infer_icp_fit_score",
        "infer_buyer_persona",
        "infer_recycler_vertical",
    ]:
        assert r in rules, f"Missing rule: {r}"


def test_facility_tier_large():
    r = execute_rule("infer_facility_tier_from_capacity",
                     {"processing_capacity_tons_per_year": 50_000}, CTX)
    assert r is not None and r.value == "large" and r.confidence >= 0.55


def test_facility_tier_mid():
    r = execute_rule("infer_facility_tier_from_capacity",
                     {"processing_capacity_tons_per_year": 8_000}, CTX)
    assert r is not None and r.value == "mid"


def test_facility_tier_micro():
    r = execute_rule("infer_facility_tier_from_capacity",
                     {"processing_capacity_tons_per_year": 500}, CTX)
    assert r is not None and r.value == "micro"


def test_mfi_hdpe_injection():
    r = execute_rule("infer_material_grade_from_mfi",
                     {"melt_flow_index": 5.0, "material_type": "HDPE"}, CTX)
    assert r is not None and r.value == "HD_injection"


def test_mfi_hdpe_pipe():
    r = execute_rule("infer_material_grade_from_mfi",
                     {"melt_flow_index": 0.3, "material_type": "HDPE"}, CTX)
    assert r is not None and r.value == "HD_pipe"


def test_contamination_from_micro_tier():
    r = execute_rule("infer_contamination_tolerance",
                     {"facility_tier": "micro", "material_grade": "HD_pipe"}, CTX)
    assert r is not None and r.value == "high"


def test_contamination_from_large_tier():
    r = execute_rule("infer_contamination_tolerance",
                     {"facility_tier": "large"}, CTX)
    assert r is not None and r.value == "low"


def test_unknown_rule_raises():
    with pytest.raises(KeyError, match="not found in registry"):
        execute_rule("nonexistent_rule_xyz", {}, CTX)


def test_icp_score_no_data_suppressed():
    r = execute_rule("infer_icp_fit_score", {}, CTX)
    assert r is None
