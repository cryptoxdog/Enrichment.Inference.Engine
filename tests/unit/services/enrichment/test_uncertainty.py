"""Unit tests for uncertainty engine."""

from __future__ import annotations

import pytest

from app.services.enrichment.uncertainty import (
    UncertaintyConfig,
    UncertaintyResult,
    aggregate_uncertainties,
    apply_uncertainty,
    should_proceed,
)


class TestApplyUncertainty:
    """Tests for apply_uncertainty() function."""

    def test_high_confidence_no_flags(self) -> None:
        """High confidence should produce no warning flags."""
        fields = {"name": "Acme Corp", "industry": "Manufacturing"}

        result = apply_uncertainty(fields, confidence=0.9)

        assert result.fields == fields
        assert result.confidence == 0.9
        assert result.risk_level == "low"
        assert "low_confidence" not in result.flags
        assert "needs_review" not in result.flags

    def test_moderate_confidence_flags(self) -> None:
        """Moderate confidence should produce moderate_confidence flag."""
        fields = {"name": "Acme Corp"}

        result = apply_uncertainty(fields, confidence=0.7)

        assert result.risk_level == "medium"
        assert "moderate_confidence" in result.flags

    def test_low_confidence_flags(self) -> None:
        """Low confidence should produce low_confidence and needs_review flags."""
        fields = {"name": "Acme Corp"}

        result = apply_uncertainty(fields, confidence=0.4)

        assert result.risk_level == "high"
        assert "low_confidence" in result.flags
        assert "needs_review" in result.flags

    def test_critical_confidence_flags(self) -> None:
        """Critical confidence should produce critical flags."""
        fields = {"name": "Acme Corp"}

        result = apply_uncertainty(fields, confidence=0.2)

        assert result.risk_level == "critical"
        assert "critical_low_confidence" in result.flags
        assert "manual_review_required" in result.flags

    def test_custom_thresholds(self) -> None:
        """Custom thresholds should be respected."""
        fields = {"name": "Acme Corp"}
        config = UncertaintyConfig(
            low_threshold=0.7,
            high_threshold=0.95,
            critical_threshold=0.4,
        )

        result = apply_uncertainty(fields, confidence=0.6, config=config)

        assert result.risk_level == "high"
        assert "low_confidence" in result.flags

    def test_field_level_confidence_flags(self) -> None:
        """Per-field confidence should generate field-specific flags."""
        fields = {"name": "Acme Corp", "industry": "Manufacturing", "size": "large"}
        field_confidences = {
            "name": 0.9,
            "industry": 0.4,
            "size": 0.2,
        }

        result = apply_uncertainty(
            fields,
            confidence=0.7,
            field_confidences=field_confidences,
        )

        assert "field_uncertain:industry" in result.flags
        assert "field_critical:size" in result.flags
        assert "field_uncertain:name" not in result.flags

    def test_filter_below_critical(self) -> None:
        """Fields below critical threshold should be filtered when enabled."""
        fields = {"name": "Acme Corp", "industry": "Manufacturing", "size": "large"}
        field_confidences = {
            "name": 0.9,
            "industry": 0.4,
            "size": 0.2,
        }
        config = UncertaintyConfig(filter_below_critical=True)

        result = apply_uncertainty(
            fields,
            confidence=0.7,
            field_confidences=field_confidences,
            config=config,
        )

        assert "name" in result.fields
        assert "industry" in result.fields
        assert "size" not in result.fields
        assert "size" in result.filtered_fields

    def test_no_field_level_flags_when_disabled(self) -> None:
        """Field-level flags should not be generated when disabled."""
        fields = {"name": "Acme Corp"}
        field_confidences = {"name": 0.2}
        config = UncertaintyConfig(flag_field_level=False)

        result = apply_uncertainty(
            fields,
            confidence=0.7,
            field_confidences=field_confidences,
            config=config,
        )

        assert not any(f.startswith("field_") for f in result.flags)


class TestShouldProceed:
    """Tests for should_proceed() function."""

    def test_high_confidence_proceeds(self) -> None:
        """High confidence should proceed."""
        result = UncertaintyResult(
            fields={"name": "Acme"},
            confidence=0.9,
            flags=[],
            risk_level="low",
        )

        assert should_proceed(result) is True

    def test_low_confidence_blocks(self) -> None:
        """Low confidence below threshold should block."""
        result = UncertaintyResult(
            fields={"name": "Acme"},
            confidence=0.3,
            flags=["low_confidence"],
            risk_level="high",
        )

        assert should_proceed(result, require_confidence=0.5) is False

    def test_critical_risk_blocks(self) -> None:
        """Critical risk level should block when block_on_critical is True."""
        result = UncertaintyResult(
            fields={"name": "Acme"},
            confidence=0.6,
            flags=["critical_low_confidence"],
            risk_level="critical",
        )

        assert should_proceed(result, block_on_critical=True) is False

    def test_critical_risk_allowed_when_disabled(self) -> None:
        """Critical risk should proceed when block_on_critical is False."""
        result = UncertaintyResult(
            fields={"name": "Acme"},
            confidence=0.6,
            flags=["critical_low_confidence"],
            risk_level="critical",
        )

        assert should_proceed(result, block_on_critical=False) is True


class TestAggregateUncertainties:
    """Tests for aggregate_uncertainties() function."""

    def test_empty_input(self) -> None:
        """Empty input should return empty result."""
        result = aggregate_uncertainties([])

        assert result.fields == {}
        assert result.confidence == 0.0
        assert result.flags == []

    def test_single_result(self) -> None:
        """Single result should be returned as-is."""
        single = UncertaintyResult(
            fields={"name": "Acme"},
            confidence=0.8,
            flags=["moderate_confidence"],
            risk_level="medium",
        )

        result = aggregate_uncertainties([single])

        assert result.fields == {"name": "Acme"}
        assert result.confidence == 0.8
        assert "moderate_confidence" in result.flags
        assert result.risk_level == "medium"

    def test_multiple_results_merged(self) -> None:
        """Multiple results should be merged correctly."""
        results = [
            UncertaintyResult(
                fields={"name": "Acme"},
                confidence=0.8,
                flags=["flag1"],
                risk_level="low",
            ),
            UncertaintyResult(
                fields={"industry": "Manufacturing"},
                confidence=0.6,
                flags=["flag2"],
                risk_level="medium",
            ),
        ]

        result = aggregate_uncertainties(results)

        assert result.fields == {"name": "Acme", "industry": "Manufacturing"}
        assert result.confidence == pytest.approx(0.7, rel=0.01)
        assert "flag1" in result.flags
        assert "flag2" in result.flags

    def test_worst_risk_level_selected(self) -> None:
        """Worst risk level should be selected."""
        results = [
            UncertaintyResult(
                fields={},
                confidence=0.9,
                flags=[],
                risk_level="low",
            ),
            UncertaintyResult(
                fields={},
                confidence=0.3,
                flags=[],
                risk_level="critical",
            ),
            UncertaintyResult(
                fields={},
                confidence=0.6,
                flags=[],
                risk_level="medium",
            ),
        ]

        result = aggregate_uncertainties(results)

        assert result.risk_level == "critical"

    def test_later_fields_override(self) -> None:
        """Later results should override earlier field values."""
        results = [
            UncertaintyResult(
                fields={"name": "Old Name"},
                confidence=0.8,
                flags=[],
                risk_level="low",
            ),
            UncertaintyResult(
                fields={"name": "New Name"},
                confidence=0.9,
                flags=[],
                risk_level="low",
            ),
        ]

        result = aggregate_uncertainties(results)

        assert result.fields["name"] == "New Name"
