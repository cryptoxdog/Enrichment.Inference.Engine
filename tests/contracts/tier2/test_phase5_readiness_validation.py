from __future__ import annotations

import pytest

from scripts.validate_phase5_readiness import run_phase5_readiness

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]


def test_phase5_readiness_checks_pass_without_subprocess_pytest() -> None:
    report = run_phase5_readiness(run_pytest=False)
    assert report["overall_ready_for_phase5"] is True, report


def test_phase5_readiness_reports_all_five_truths() -> None:
    report = run_phase5_readiness(run_pytest=False)
    truth_names = {item["name"] for item in report["results"]}
    assert truth_names == {
        "repo_truth",
        "runtime_truth",
        "governance_truth",
        "operational_truth",
        "agent_truth",
    }
