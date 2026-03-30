"""Unit tests for consensus engine."""

from __future__ import annotations

import pytest

from app.services.enrichment.consensus import (
    ConsensusResult,
    merge_with_priority,
    synthesize,
)


class TestSynthesize:
    """Tests for synthesize() function."""

    def test_empty_input_returns_empty_result(self) -> None:
        """Empty input should return empty ConsensusResult."""
        result = synthesize([])

        assert result.fields == {}
        assert result.confidence == 0.0
        assert result.agreement_ratio == 0.0
        assert result.contributing_sources == 0

    def test_single_response_full_agreement(self) -> None:
        """Single response should have 100% agreement for all fields."""
        payloads = [{"name": "Acme Corp", "industry": "Manufacturing"}]

        result = synthesize(payloads, threshold=0.5)

        assert result.fields["name"] == "Acme Corp"
        assert result.fields["industry"] == "Manufacturing"
        assert result.agreement_ratio == 1.0
        assert result.contributing_sources == 1

    def test_unanimous_agreement(self) -> None:
        """All responses agreeing should have 100% agreement."""
        payloads = [
            {"name": "Acme Corp", "industry": "Manufacturing"},
            {"name": "Acme Corp", "industry": "Manufacturing"},
            {"name": "Acme Corp", "industry": "Manufacturing"},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["name"] == "Acme Corp"
        assert result.fields["industry"] == "Manufacturing"
        assert result.agreement_ratio == 1.0
        assert result.contributing_sources == 3

    def test_majority_agreement_above_threshold(self) -> None:
        """Majority agreement above threshold should include field."""
        payloads = [
            {"name": "Acme Corp"},
            {"name": "Acme Corp"},
            {"name": "Acme Inc"},  # Different
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["name"] == "Acme Corp"
        assert result.field_agreements["name"] == pytest.approx(0.667, rel=0.01)

    def test_majority_agreement_below_threshold(self) -> None:
        """Majority agreement below threshold should exclude field."""
        payloads = [
            {"name": "Acme Corp"},
            {"name": "Acme Inc"},
            {"name": "Acme LLC"},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert "name" not in result.fields

    def test_mixed_fields_partial_agreement(self) -> None:
        """Some fields agree, some don't."""
        payloads = [
            {"name": "Acme Corp", "industry": "Manufacturing", "size": "large"},
            {"name": "Acme Corp", "industry": "Manufacturing", "size": "medium"},
            {"name": "Acme Corp", "industry": "Tech", "size": "small"},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["name"] == "Acme Corp"
        assert "industry" in result.fields
        assert "size" not in result.fields

    def test_empty_values_ignored(self) -> None:
        """Empty values should not count toward agreement."""
        payloads = [
            {"name": "Acme Corp", "industry": ""},
            {"name": "Acme Corp", "industry": None},
            {"name": "Acme Corp", "industry": "Manufacturing"},
        ]

        result = synthesize(payloads, threshold=0.3)

        assert result.fields["name"] == "Acme Corp"
        assert result.fields.get("industry") == "Manufacturing"
        assert result.field_agreements.get("industry") == pytest.approx(0.333, rel=0.01)

    def test_total_attempted_affects_confidence(self) -> None:
        """total_attempted parameter should affect confidence calculation."""
        payloads = [{"name": "Acme Corp"}]

        result_all_succeeded = synthesize(payloads, total_attempted=1)
        result_some_failed = synthesize(payloads, total_attempted=5)

        assert result_all_succeeded.confidence > result_some_failed.confidence

    def test_string_normalization(self) -> None:
        """Strings with different whitespace should be normalized."""
        payloads = [
            {"name": "  Acme Corp  "},
            {"name": "Acme Corp"},
            {"name": "Acme Corp "},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["name"] == "Acme Corp"
        assert result.agreement_ratio == 1.0

    def test_list_values_handled(self) -> None:
        """List values should be handled correctly."""
        payloads = [
            {"tags": ["manufacturing", "plastics"]},
            {"tags": ["manufacturing", "plastics"]},
            {"tags": ["tech"]},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["tags"] == ["manufacturing", "plastics"]

    def test_dict_values_handled(self) -> None:
        """Dict values should be handled correctly."""
        payloads = [
            {"address": {"city": "NYC", "state": "NY"}},
            {"address": {"city": "NYC", "state": "NY"}},
            {"address": {"city": "LA", "state": "CA"}},
        ]

        result = synthesize(payloads, threshold=0.65)

        assert result.fields["address"] == {"city": "NYC", "state": "NY"}


class TestMergeWithPriority:
    """Tests for merge_with_priority() function."""

    def test_consensus_overrides_base(self) -> None:
        """Consensus fields should override base fields."""
        base = {"name": "Old Name", "industry": "Unknown"}
        consensus = ConsensusResult(
            fields={"name": "New Name"},
            confidence=0.8,
            agreement_ratio=0.9,
            contributing_sources=3,
            field_agreements={"name": 0.9},
        )

        result = merge_with_priority(base, consensus, min_agreement=0.5)

        assert result["name"] == "New Name"
        assert result["industry"] == "Unknown"

    def test_low_agreement_does_not_override(self) -> None:
        """Fields with low agreement should not override base."""
        base = {"name": "Old Name"}
        consensus = ConsensusResult(
            fields={"name": "New Name"},
            confidence=0.8,
            agreement_ratio=0.4,
            contributing_sources=3,
            field_agreements={"name": 0.4},
        )

        result = merge_with_priority(base, consensus, min_agreement=0.5)

        assert result["name"] == "Old Name"

    def test_new_fields_added(self) -> None:
        """New fields from consensus should be added to base."""
        base = {"name": "Acme Corp"}
        consensus = ConsensusResult(
            fields={"industry": "Manufacturing"},
            confidence=0.8,
            agreement_ratio=0.9,
            contributing_sources=3,
            field_agreements={"industry": 0.9},
        )

        result = merge_with_priority(base, consensus, min_agreement=0.5)

        assert result["name"] == "Acme Corp"
        assert result["industry"] == "Manufacturing"

    def test_empty_consensus_preserves_base(self) -> None:
        """Empty consensus should preserve base unchanged."""
        base = {"name": "Acme Corp", "industry": "Manufacturing"}
        consensus = ConsensusResult()

        result = merge_with_priority(base, consensus)

        assert result == base
