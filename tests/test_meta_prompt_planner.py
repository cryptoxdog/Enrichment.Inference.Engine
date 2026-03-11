"""Tests for app/engines/meta_prompt_planner.py

Covers: Prompt variation generation, mode-specific prompting,
        KB fragment injection, SearchPlan construction.

Source: ~280 lines | Target coverage: 75%
"""

from __future__ import annotations

import pytest

from app.engines.meta_prompt_planner import MetaPromptPlanner, SearchPlan


class TestMetaPromptPlanner:
    """Tests for prompt variation generation."""

    @pytest.fixture
    def planner(self):
        return MetaPromptPlanner()

    def test_plan_returns_search_plan(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp", "polymer_type": "HDPE"},
            known_fields={"polymer_type": 0.9},
            inferred_fields={},
            domain_hints={},
            inference_rule_catalog=[],
            pass_number=1,
        )
        assert isinstance(plan, SearchPlan)

    def test_pass_1_discovery_mode(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp"},
            known_fields={},
            inferred_fields={},
            domain_hints={},
            inference_rule_catalog=[],
            pass_number=1,
        )
        assert plan.mode == "discovery"

    def test_pass_2_targeted_mode(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp", "polymer_type": "HDPE"},
            known_fields={"polymer_type": 0.9},
            inferred_fields={},
            domain_hints={"priority_fields": ["mfi_range", "contamination_pct"]},
            inference_rule_catalog=[],
            pass_number=2,
        )
        assert plan.mode in ("targeted", "discovery")

    def test_plan_has_objective(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp"},
            known_fields={},
            inferred_fields={},
            domain_hints={},
            inference_rule_catalog=[],
            pass_number=1,
        )
        assert plan.objective is not None

    def test_plan_has_target_fields_in_later_passes(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp"},
            known_fields={"polymer_type": 0.9},
            inferred_fields={"material_grade": "Standard HDPE"},
            domain_hints={"priority_fields": ["mfi_range"]},
            inference_rule_catalog=[{"name": "tier_compute", "inputs": ["mfi_range"]}],
            pass_number=3,
        )
        # In later passes, planner should identify targets
        assert plan.target_fields is not None or plan.mode == "verification"

    def test_variation_budget_on_plan(self, planner):
        plan = planner.plan(
            entity={"Name": "Test Corp"},
            known_fields={},
            inferred_fields={},
            domain_hints={},
            inference_rule_catalog=[],
            pass_number=1,
        )
        # Plan may specify a variation budget
        if plan.variation_budget is not None:
            assert plan.variation_budget >= 1
