"""
Enrichment quality scoring engine.

Evaluates the quality of enrichment results across five dimensions:
completeness, freshness, accuracy, consistency, and confidence.

This module is independent of any specific CRM or enrichment source.
It operates on canonical field dictionaries.

L9 Architecture Note:
    This module is chassis-agnostic. It never imports FastAPI.
    It is called by WaterfallEngine during enrichment convergence.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger("quality_scorer")

# Default dimension weights if not configured
_DEFAULT_WEIGHTS: dict[str, float] = {
    "completeness": 0.30,
    "freshness": 0.15,
    "accuracy": 0.25,
    "consistency": 0.15,
    "confidence": 0.15,
}


@dataclass
class QualityDimensions:
    """Individual quality dimension scores."""

    completeness: float = 0.0
    freshness: float = 0.0
    accuracy: float = 0.0
    consistency: float = 0.0
    confidence: float = 0.0


class QualityScorer:
    """
    Scores enrichment quality across multiple dimensions.

    Can be initialized with a YAML thresholds file or with defaults.
    """

    def __init__(self, thresholds_path: str | None = None) -> None:
        self.weights: dict[str, float] = dict(_DEFAULT_WEIGHTS)
        self.required_fields: dict[str, list[str]] = {}
        self.validation_rules: dict[str, dict[str, str]] = {}

        if thresholds_path:
            self._load_thresholds(thresholds_path)

    def _load_thresholds(self, path: str) -> None:
        """Load quality thresholds from YAML config."""
        import yaml

        try:
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("quality_thresholds_not_found", path=path)
            return

        self.weights = cfg.get("dimension_weights", self.weights)
        self.required_fields = cfg.get("required_fields", {})
        self.validation_rules = cfg.get("validation_rules", {})

    def score(
        self,
        domain: str,
        record: dict[str, Any],
        source_quality_scores: list[float] | None = None,
    ) -> float:
        """
        Compute a weighted quality score for an enrichment record.

        Args:
            domain: Entity domain (company, contact, account, opportunity)
            record: Canonical enrichment fields
            source_quality_scores: Per-source quality scores from waterfall

        Returns:
            Weighted quality score between 0.0 and 1.0
        """
        dims = QualityDimensions(
            completeness=self._score_completeness(domain, record),
            freshness=self._score_freshness(record),
            accuracy=self._score_accuracy(domain, record),
            consistency=self._score_consistency(record),
            confidence=self._score_confidence(source_quality_scores),
        )

        total = (
            dims.completeness * self.weights.get("completeness", 0.30)
            + dims.freshness * self.weights.get("freshness", 0.15)
            + dims.accuracy * self.weights.get("accuracy", 0.25)
            + dims.consistency * self.weights.get("consistency", 0.15)
            + dims.confidence * self.weights.get("confidence", 0.15)
        )

        return round(min(max(total, 0.0), 1.0), 3)

    def _score_completeness(self, domain: str, record: dict[str, Any]) -> float:
        """Score based on how many required fields are populated."""
        required = self.required_fields.get(domain, [])
        if not required:
            # Fallback: count non-empty fields vs total
            total = max(len(record), 1)
            filled = sum(1 for v in record.values() if v not in (None, "", [], {}))
            return filled / total

        filled = sum(1 for f in required if f in record and record[f] not in (None, "", [], {}))
        return filled / max(len(required), 1)

    def _score_freshness(self, record: dict[str, Any]) -> float:
        """Score based on enrichment timestamp recency."""
        ts = record.get("enrichment_timestamp")
        if not ts:
            return 0.5  # neutral if no timestamp

        try:
            if isinstance(ts, (int, float)):
                age_hours = (time.time() - ts) / 3600
            else:
                return 0.5
        except (TypeError, ValueError):
            return 0.5

        if age_hours < 24:
            return 1.0
        if age_hours < 168:  # 1 week
            return 0.8
        if age_hours < 720:  # 30 days
            return 0.5
        return 0.2

    def _score_accuracy(self, domain: str, record: dict[str, Any]) -> float:
        """Score based on validation rule pass rate."""
        rules = self.validation_rules.get(domain, {})
        if not rules:
            return 0.7  # neutral default

        passed = 0
        total = 0
        for field_name, rule_type in rules.items():
            if field_name not in record:
                continue
            total += 1
            value = record[field_name]
            if self._validate_field(value, rule_type):
                passed += 1

        return passed / max(total, 1)

    def _score_consistency(self, record: dict[str, Any]) -> float:
        """Score based on cross-field consistency checks."""
        checks = 0
        passed = 0

        # employee_count should be positive
        emp = record.get("employee_count")
        if emp is not None:
            checks += 1
            if isinstance(emp, (int, float)) and emp > 0:
                passed += 1

        # annual_revenue should be positive
        rev = record.get("annual_revenue")
        if rev is not None:
            checks += 1
            if isinstance(rev, (int, float)) and rev > 0:
                passed += 1

        # domain should look like a domain
        dom = record.get("company_domain") or record.get("account_domain")
        if dom is not None:
            checks += 1
            if isinstance(dom, str) and "." in dom:
                passed += 1

        if checks == 0:
            return 0.7  # neutral
        return passed / checks

    def _score_confidence(self, source_scores: list[float] | None) -> float:
        """Score based on max source quality score."""
        if not source_scores:
            return 0.5
        return max(source_scores)

    @staticmethod
    def _validate_field(value: Any, rule_type: str) -> bool:
        """Validate a field value against a rule type."""
        if rule_type == "domain_format":
            return isinstance(value, str) and bool(
                re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", value.lower())
            )
        if rule_type == "phone_format":
            return isinstance(value, str) and bool(re.match(r"^[+\d\s()-]{7,}$", value))
        if rule_type == "positive_integer":
            return isinstance(value, (int, float)) and value > 0
        if rule_type == "range_0_1":
            return isinstance(value, (int, float)) and 0 <= value <= 1
        return True
