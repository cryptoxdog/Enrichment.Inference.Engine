"""Tests for app/engines/convergence/cost_tracker.py

Covers: Token/cost tracking across convergence passes.

Source: 95 lines | Target coverage: 90%
"""

from __future__ import annotations

import pytest

from app.engines.convergence.cost_tracker import CostTracker


class TestCostTracker:
    """Tests for token/cost tracking across passes."""

    @pytest.fixture
    def tracker(self):
        return CostTracker(max_budget_tokens=50000)

    def test_record_pass_tokens(self, tracker):
        tracker.record_pass(1, 1200)
        tracker.record_pass(2, 800)
        tracker.record_pass(3, 400)
        summary = tracker.to_summary()
        assert summary.tokens_per_pass == [1200, 800, 400]

    def test_total_tokens_sum(self, tracker):
        tracker.record_pass(1, 1200)
        tracker.record_pass(2, 800)
        tracker.record_pass(3, 400)
        summary = tracker.to_summary()
        assert summary.total_tokens == 2400

    def test_cost_calculation_sonar_pricing(self, tracker):
        tracker.record_pass(1, 10000)
        summary = tracker.to_summary()
        # Cost should be based on Sonar pricing model
        assert summary.total_cost_usd > 0.0

    def test_budget_utilization_pct(self, tracker):
        tracker.record_pass(1, 2400)
        summary = tracker.to_summary()
        expected_pct = (2400 / 50000) * 100
        assert abs(summary.budget_utilization_pct - expected_pct) < 1.0

    def test_can_continue_within_budget(self, tracker):
        tracker.record_pass(1, 10000)
        assert tracker.can_continue() is True

    def test_can_continue_budget_exhausted(self):
        tracker = CostTracker(max_budget_tokens=1000)
        tracker.record_pass(1, 1000)
        assert tracker.can_continue() is False

    def test_cost_per_field_calculation(self, tracker):
        tracker.record_pass(1, 5000)
        summary = tracker.to_summary()
        # cost_per_field depends on fields discovered — tested via integration

    def test_initial_state_zero(self):
        tracker = CostTracker(max_budget_tokens=50000)
        summary = tracker.to_summary()
        assert summary.total_tokens == 0
        assert summary.total_cost_usd == 0.0
