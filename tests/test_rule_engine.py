"""Tests for app/engines/convergence/rule_engine.py

Covers: Deterministic inference rule evaluation against entity fields.

Source: 195 lines | Target coverage: 85%
"""

from __future__ import annotations

import pytest

from app.engines.inference.rule_engine import (
    infer as evaluate_rules,
    InferenceResult as RuleResult,
    RuleFired,
)
from app.engines.inference.rule_loader import RuleRegistry
from app.models.field_confidence import FieldSource


class TestRuleEngine:
    """Tests for deterministic inference rule execution."""

    @pytest.fixture
    def hdpe_rules(self):
        return [
            {
                "name": "premium_hdpe_grade",
                "conditions": {"polymer_type": "HDPE", "contamination_pct": {"lt": 2.0}},
                "action": {"set_field": "material_grade", "value": "Premium HDPE"},
                "confidence": 0.95,
                "priority": 1,
            },
            {
                "name": "standard_hdpe_grade",
                "conditions": {"polymer_type": "HDPE", "contamination_pct": {"gte": 2.0, "lt": 5.0}},
                "action": {"set_field": "material_grade", "value": "Standard HDPE"},
                "confidence": 0.90,
                "priority": 2,
            },
            {
                "name": "recycled_hdpe_grade",
                "conditions": {"polymer_type": "HDPE", "contamination_pct": {"gte": 5.0, "lt": 10.0}},
                "action": {"set_field": "material_grade", "value": "Recycled HDPE"},
                "confidence": 0.85,
                "priority": 3,
            },
        ]

    def test_rule_matching_simple_condition(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 1.0}
        result = evaluate_rules(entity, hdpe_rules)
        assert "material_grade" in result.derived_fields
        assert result.derived_fields["material_grade"] == "Premium HDPE"

    def test_rule_matching_range_condition(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 3.5}
        result = evaluate_rules(entity, hdpe_rules)
        assert result.derived_fields.get("material_grade") == "Standard HDPE"

    def test_rule_matching_multiple_conditions(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 7.0}
        result = evaluate_rules(entity, hdpe_rules)
        assert result.derived_fields.get("material_grade") == "Recycled HDPE"

    def test_rule_execution_sets_field_value(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 1.0}
        result = evaluate_rules(entity, hdpe_rules)
        assert result.derived_fields["material_grade"] == "Premium HDPE"

    def test_rule_confidence_propagation(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 1.0}
        result = evaluate_rules(entity, hdpe_rules)
        conf = result.confidence_map.get("material_grade", 0.0)
        assert conf > 0.0
        assert conf <= 0.95

    def test_no_matching_rules_returns_empty(self, hdpe_rules):
        entity = {"polymer_type": "PP", "contamination_pct": 1.0}
        result = evaluate_rules(entity, hdpe_rules)
        assert len(result.derived_fields) == 0

    def test_rules_fired_tracking(self, hdpe_rules):
        entity = {"polymer_type": "HDPE", "contamination_pct": 1.0}
        result = evaluate_rules(entity, hdpe_rules)
        assert "premium_hdpe_grade" in result.rules_fired

    def test_missing_field_no_match(self, hdpe_rules):
        entity = {"polymer_type": "HDPE"}  # no contamination_pct
        result = evaluate_rules(entity, hdpe_rules)
        assert "material_grade" not in result.derived_fields
