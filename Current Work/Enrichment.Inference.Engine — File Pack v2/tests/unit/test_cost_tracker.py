"""Unit tests for CostTracker budget enforcement."""

from app.engines.convergence.cost_tracker import CostTracker


def test_budget_remaining_decrements():
    ct = CostTracker(max_budget_tokens=10_000)
    ct.record_pass(0, 3_000)
    assert ct.budget_remaining() == 7_000


def test_can_continue_false_when_exhausted():
    ct = CostTracker(max_budget_tokens=5_000)
    ct.record_pass(0, 5_001)
    assert not ct.can_continue()


def test_cost_usd_calculation():
    ct = CostTracker(max_budget_tokens=100_000)
    ct.record_pass(0, 10_000)
    # 10K tokens × $0.005/1K = $0.05
    assert abs(ct.cost_usd() - 0.05) < 0.001


def test_cost_per_field():
    ct = CostTracker(max_budget_tokens=100_000)
    ct.record_pass(0, 10_000)
    # $0.05 / 10 fields = $0.005 per field
    assert abs(ct.cost_per_field(10) - 0.005) < 0.0001


def test_summary_budget_utilization():
    ct = CostTracker(max_budget_tokens=10_000)
    ct.record_pass(0, 5_000)
    summary = ct.to_summary()
    assert summary.budget_utilization_pct == 50.0
