"""
Consensus engine for multi-response enrichment synthesis.

Synthesizes multiple enrichment responses into a single consensus result
using field-level voting with configurable agreement thresholds.

L9 Architecture Note:
    This module is chassis-agnostic. It never imports FastAPI.
    It is called by WaterfallEngine during consensus-mode enrichment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ConsensusResult:
    """Result of consensus synthesis across multiple responses."""

    fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    agreement_ratio: float = 0.0
    contributing_sources: int = 0
    field_agreements: dict[str, float] = field(default_factory=dict)


def synthesize(
    payloads: list[dict[str, Any]],
    threshold: float = 0.65,
    total_attempted: int | None = None,
) -> ConsensusResult:
    """
    Synthesize multiple enrichment responses into a single consensus result.

    Uses field-level voting: for each field, the most common non-empty value
    is selected if its agreement ratio meets the threshold.

    Args:
        payloads: List of validated response dicts from parallel enrichment calls.
                  Each dict contains field_name -> value mappings.
        threshold: Minimum agreement ratio (0.0-1.0) required to include a field.
                   Default 0.65 means 65% of responses must agree.
        total_attempted: Total variations attempted (for confidence calculation).
                        If None, uses len(payloads).

    Returns:
        ConsensusResult with:
            - fields: Merged fields that met the agreement threshold
            - confidence: Overall confidence based on response rate and agreement
            - agreement_ratio: Average agreement across all included fields
            - contributing_sources: Number of valid responses used
            - field_agreements: Per-field agreement ratios
    """
    if not payloads:
        logger.warning("consensus_empty_input")
        return ConsensusResult()

    total = total_attempted if total_attempted is not None else len(payloads)
    if total == 0:
        total = len(payloads) or 1

    all_fields = _collect_all_fields(payloads)

    consensus_fields: dict[str, Any] = {}
    field_agreements: dict[str, float] = {}

    for field_name in all_fields:
        value, agreement = _vote_for_field(payloads, field_name)

        if agreement >= threshold and value is not None:
            consensus_fields[field_name] = value
            field_agreements[field_name] = agreement

    avg_agreement = (
        sum(field_agreements.values()) / len(field_agreements) if field_agreements else 0.0
    )

    response_rate = len(payloads) / total
    confidence = _calculate_confidence(response_rate, avg_agreement, len(payloads))

    logger.info(
        "consensus_synthesized",
        input_count=len(payloads),
        total_attempted=total,
        fields_included=len(consensus_fields),
        avg_agreement=round(avg_agreement, 3),
        confidence=round(confidence, 3),
    )

    return ConsensusResult(
        fields=consensus_fields,
        confidence=round(confidence, 3),
        agreement_ratio=round(avg_agreement, 3),
        contributing_sources=len(payloads),
        field_agreements=field_agreements,
    )


def _collect_all_fields(payloads: list[dict[str, Any]]) -> set[str]:
    """Collect all unique field names across all payloads."""
    fields: set[str] = set()
    for payload in payloads:
        fields.update(payload.keys())
    return fields


def _vote_for_field(
    payloads: list[dict[str, Any]],
    field_name: str,
) -> tuple[Any, float]:
    """
    Vote for the most common value of a field across payloads.

    Returns:
        (winning_value, agreement_ratio)
        - winning_value: Most common non-empty value, or None if no valid values
        - agreement_ratio: Fraction of payloads that have this value
    """
    values: list[Any] = []

    for payload in payloads:
        value = payload.get(field_name)
        if _is_non_empty(value):
            values.append(_normalize_value(value))

    if not values:
        return None, 0.0

    counter = Counter(_hashable(v) for v in values)
    most_common_hash, count = counter.most_common(1)[0]

    for v in values:
        if _hashable(v) == most_common_hash:
            winning_value = v
            break
    else:
        winning_value = values[0]

    agreement = count / len(payloads)
    return winning_value, agreement


def _is_non_empty(value: Any) -> bool:
    """Check if a value is non-empty (not None, empty string, empty list, etc.)."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return not (isinstance(value, (list, dict)) and not value)


def _normalize_value(value: Any) -> Any:
    """Normalize a value for comparison (strip strings, etc.)."""
    if isinstance(value, str):
        return value.strip()
    return value


def _hashable(value: Any) -> Any:
    """Convert a value to a hashable form for counting."""
    if isinstance(value, dict):
        return tuple(sorted(value.items()))
    if isinstance(value, list):
        return tuple(value)
    return value


def _calculate_confidence(
    response_rate: float,
    avg_agreement: float,
    source_count: int,
) -> float:
    """
    Calculate overall confidence score.

    Factors:
        - response_rate: What fraction of attempts succeeded (weight: 0.3)
        - avg_agreement: How much sources agree (weight: 0.5)
        - source_count: More sources = higher confidence (weight: 0.2, capped at 5)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    source_factor = min(source_count / 5, 1.0)

    confidence = response_rate * 0.3 + avg_agreement * 0.5 + source_factor * 0.2

    return min(max(confidence, 0.0), 1.0)


def merge_with_priority(
    base: dict[str, Any],
    consensus: ConsensusResult,
    min_agreement: float = 0.5,
) -> dict[str, Any]:
    """
    Merge consensus fields into a base record with priority rules.

    Consensus fields override base fields only if:
    - The field's agreement ratio >= min_agreement
    - The consensus value is non-empty

    Args:
        base: Base record (e.g., from initial enrichment)
        consensus: ConsensusResult from synthesize()
        min_agreement: Minimum agreement to allow override

    Returns:
        Merged record with consensus fields applied
    """
    result = dict(base)

    for field_name, value in consensus.fields.items():
        agreement = consensus.field_agreements.get(field_name, 0.0)
        if agreement >= min_agreement and _is_non_empty(value):
            result[field_name] = value

    return result
