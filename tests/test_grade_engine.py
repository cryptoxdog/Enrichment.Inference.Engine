"""Tests for app/engines/convergence/grade_engine.py

Covers: Material grading inference for plastics recycling vertical.

Source: 195 lines | Target coverage: 85%
"""

from __future__ import annotations

from app.engines.inference.grade_engine import (
    classify as compute_grade,
)


class TestGradeEngine:
    """Tests for material grading inference."""

    def test_grade_hdpe_premium(self):
        result = compute_grade(
            polymer_type="HDPE",
            contamination_pct=1.0,
            mfi_range="0.5-3.0",
        )
        assert result.grade == "Premium HDPE"
        assert result.confidence >= 0.85

    def test_grade_hdpe_standard(self):
        result = compute_grade(
            polymer_type="HDPE",
            contamination_pct=3.5,
            mfi_range="0.5-3.0",
        )
        assert result.grade == "Standard HDPE"
        assert result.confidence >= 0.75

    def test_grade_hdpe_recycled(self):
        result = compute_grade(
            polymer_type="HDPE",
            contamination_pct=7.0,
        )
        assert result.grade == "Recycled HDPE"

    def test_grade_pet_bottle(self):
        result = compute_grade(
            polymer_type="PET",
            application="bottle",
        )
        assert "bottle" in result.grade.lower() or "PET" in result.grade

    def test_grade_pet_fiber(self):
        result = compute_grade(
            polymer_type="PET",
            application="fiber",
        )
        assert "fiber" in result.grade.lower() or "PET" in result.grade

    def test_grade_unknown_polymer(self):
        result = compute_grade(polymer_type="UNKNOWN_POLYMER")
        assert result.grade is not None
        assert result.confidence < 0.7

    def test_grade_confidence_from_input_confidence(self):
        result = compute_grade(
            polymer_type="HDPE",
            contamination_pct=1.5,
            input_confidence=0.8,
        )
        assert result.confidence <= 0.8

    def test_missing_critical_field_lowers_confidence(self):
        result_full = compute_grade(
            polymer_type="HDPE",
            contamination_pct=1.5,
            mfi_range="0.5-3.0",
        )
        result_partial = compute_grade(
            polymer_type="HDPE",
        )
        assert result_partial.confidence < result_full.confidence
