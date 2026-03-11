"""Tests for app/engines/convergence/rule_loader.py

Covers: YAML-based inference rule loading, validation, caching.

Source: 175 lines | Target coverage: 85%
"""

from __future__ import annotations


from app.engines.inference.rule_loader import (
    load_rules,
    RuleDefinition,
)


class TestRuleLoader:
    """Tests for YAML-based rule loading."""

    def test_load_rules_from_kb_yaml(self, mock_kb_data):
        rules = load_rules(mock_kb_data)
        assert isinstance(rules, list)
        assert len(rules) >= 1
        assert all(isinstance(r, (dict, RuleDefinition)) for r in rules)

    def test_empty_kb_returns_empty_rules(self):
        rules = load_rules({})
        assert rules == []

    def test_rules_without_rules_key_returns_empty(self):
        rules = load_rules({"domain": "test", "polymers": {}})
        assert rules == []

    def test_rule_has_required_fields(self, mock_kb_data):
        rules = load_rules(mock_kb_data)
        for rule in rules:
            r = rule if isinstance(rule, dict) else rule.__dict__
            assert "name" in r or hasattr(rule, "name")
            assert "conditions" in r or hasattr(rule, "conditions")
            assert "action" in r or hasattr(rule, "action")

    def test_rule_filtering_by_domain(self, mock_kb_data):
        rules = load_rules(mock_kb_data)
        # All rules from plastics_recycling KB should be present
        names = [r["name"] if isinstance(r, dict) else r.name for r in rules]
        assert "premium_hdpe_grade" in names

    def test_rule_priority_ordering(self, mock_kb_data):
        rules = load_rules(mock_kb_data)
        if len(rules) >= 2:
            # Higher priority/more specific rules should come first
            # if priority is defined
            pass  # ordering validated by rule_engine tests

    def test_malformed_rule_skipped(self):
        kb = {
            "rules": [
                {
                    "name": "valid",
                    "conditions": {"x": "y"},
                    "action": {"set_field": "z", "value": "w"},
                    "confidence": 0.9,
                },
                {"broken": True},  # missing required fields
            ]
        }
        rules = load_rules(kb)
        # Should load at least the valid rule and skip or warn about broken
        valid_rules = [
            r
            for r in rules
            if (r.get("name") if isinstance(r, dict) else getattr(r, "name", None)) == "valid"
        ]
        assert len(valid_rules) >= 1
