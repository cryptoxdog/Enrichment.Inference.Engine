"""Unit tests for the rule engine (rule loading + evaluation)."""

import pytest
import yaml
from app.engines.inference.rule_engine import infer
from app.engines.inference.rule_loader import load_rules

SAMPLE_YAML = {
    "name": "test-domain",
    "inference_rules": [
        {
            "rule_id": "grade-a-hdpe",
            "conditions": [
                {"field": "materials_handled", "operator": "CONTAINS", "value": "HDPE"},
                {"field": "contamination_tolerance_pct", "operator": "LT", "value": 0.03},
            ],
            "outputs": [
                {"field": "material_grade", "value_expr": "A", "derivation_type": "classification"}
            ],
            "confidence": 0.95,
            "priority": 10,
        },
        {
            "rule_id": "grade-b-hdpe",
            "conditions": [
                {"field": "materials_handled", "operator": "CONTAINS", "value": "HDPE"},
                {"field": "contamination_tolerance_pct", "operator": "GTE", "value": 0.03},
                {"field": "contamination_tolerance_pct", "operator": "LTE", "value": 0.07},
            ],
            "outputs": [
                {"field": "material_grade", "value_expr": "B", "derivation_type": "classification"}
            ],
            "confidence": 0.85,
            "priority": 5,
        },
    ],
}


@pytest.fixture
def registry(tmp_path):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml.dump(SAMPLE_YAML))
    return load_rules(str(spec_file))


def test_rule_fires_on_matching_entity(registry):
    entity = {
        "materials_handled": ["HDPE", "LDPE"],
        "contamination_tolerance_pct": 0.02,
    }
    result = infer(entity, registry)
    assert "material_grade" in result.derived_fields
    assert result.derived_fields["material_grade"] == "A"


def test_higher_priority_wins(registry):
    """Grade A rule (priority 10) should win over Grade B (priority 5)."""
    entity = {
        "materials_handled": ["HDPE"],
        "contamination_tolerance_pct": 0.02,  # qualifies for grade A
    }
    result = infer(entity, registry)
    assert result.derived_fields.get("material_grade") == "A"


def test_rule_skipped_when_field_missing(registry):
    entity = {"materials_handled": ["HDPE"]}  # missing contamination_tolerance_pct
    result = infer(entity, registry)
    assert "material_grade" not in result.derived_fields
    assert result.rules_skipped > 0


def test_bad_operator_raises_at_load_time(tmp_path):
    bad_spec = {
        "name": "bad",
        "inference_rules": [
            {
                "rule_id": "bad-op",
                "conditions": [{"field": "x", "operator": "INVALID_OP", "value": 1}],
                "outputs": [{"field": "y", "value_expr": "z", "derivation_type": "classification"}],
            }
        ],
    }
    f = tmp_path / "bad.yaml"
    f.write_text(yaml.dump(bad_spec))
    with pytest.raises(ValueError, match="unsupported operator"):
        load_rules(str(f))


def test_null_entity_produces_no_derivations(registry):
    result = infer({}, registry)
    assert result.derived_fields == {}
    assert result.rules_fired == []
