"""Unit tests for grade classification engine."""

import pytest
from app.engines.inference.grade_engine import GradeCondition, GradeDefinition, classify


@pytest.fixture
def grade_defs():
    return [
        GradeDefinition(
            grade_id="hdpe-a",
            grade_label="A",
            tier="premium",
            application_class="pipe",
            conditions=[
                GradeCondition(field="density", operator="gte", value=0.94),
                GradeCondition(field="contamination", operator="lte", value=0.02),
                GradeCondition(field="mfi", operator="gte", value=5.0),
                GradeCondition(field="mfi", operator="lte", value=10.0),
            ],
            min_match_threshold=0.75,
        ),
        GradeDefinition(
            grade_id="hdpe-b",
            grade_label="B",
            tier="standard",
            application_class="film",
            conditions=[
                GradeCondition(field="density", operator="gte", value=0.93),
                GradeCondition(field="contamination", operator="lte", value=0.05),
            ],
            min_match_threshold=0.6,
        ),
    ]


def test_perfect_match_returns_grade_a(grade_defs):
    entity = {"density": 0.95, "contamination": 0.01, "mfi": 7.5}
    result = classify(entity, grade_defs)
    assert result is not None
    assert result.grade == "A"
    assert result.match_score == 1.0


def test_partial_match_returns_grade_b(grade_defs):
    entity = {"density": 0.93, "contamination": 0.04}
    result = classify(entity, grade_defs)
    assert result is not None
    assert result.grade == "B"


def test_below_threshold_returns_none(grade_defs):
    entity = {"density": 0.80}  # only 1/4 conditions met
    result = classify(entity, grade_defs)
    assert result is None or result.fallback_used


def test_empty_grade_defs_returns_none():
    entity = {"density": 0.95}
    result = classify(entity, [])
    assert result is None
