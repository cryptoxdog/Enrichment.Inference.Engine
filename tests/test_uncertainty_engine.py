"""Tests for app/services/uncertainty_engine.py

Covers: Convergence uncertainty scoring, schema coverage penalty,
        confidence-weighted scoring, variation budget recommendation.

Source: ~160 lines | Target coverage: 85%
"""

from __future__ import annotations

import pytest

from app.services.uncertainty_engine import compute_uncertainty
from app.models.field_confidence import FieldConfidenceMap, FieldConfidence, FieldSource


class TestUncertaintyEngine:
    """Tests for convergence uncertainty scoring."""

    def test_empty_entity_high_uncertainty(self):
        score = compute_uncertainty(
            entity={},
            field_confidence_map=FieldConfidenceMap(),
            schema={},
        )
        assert score >= 5.0

    def test_rich_entity_low_uncertainty(self, rich_entity, sample_field_confidence_map, sample_schema):
        score = compute_uncertainty(
            entity=rich_entity,
            field_confidence_map=sample_field_confidence_map,
            schema=sample_schema,
        )
        assert score < 5.0

    def test_low_confidence_increases_uncertainty(self, sample_schema):
        fcm = FieldConfidenceMap()
        for field_name in sample_schema:
            fcm.set(FieldConfidence(
                field_name=field_name,
                value="test",
                confidence=0.3,
                source=FieldSource.ENRICHMENT,
            ))
        entity = {k: "test" for k in sample_schema}
        score = compute_uncertainty(entity=entity, field_confidence_map=fcm, schema=sample_schema)
        # Low confidence should produce higher uncertainty
        assert score > 3.0

    def test_high_confidence_lowers_uncertainty(self, sample_schema):
        fcm = FieldConfidenceMap()
        for field_name in sample_schema:
            fcm.set(FieldConfidence(
                field_name=field_name,
                value="test",
                confidence=0.95,
                source=FieldSource.ENRICHMENT,
            ))
        entity = {k: "test" for k in sample_schema}
        score = compute_uncertainty(entity=entity, field_confidence_map=fcm, schema=sample_schema)
        assert score < 4.0

    def test_schema_coverage_penalty(self, sample_schema):
        fcm = FieldConfidenceMap()
        fcm.set(FieldConfidence(
            field_name="polymer_type", value="HDPE", confidence=0.9,
            source=FieldSource.ENRICHMENT,
        ))
        entity = {"polymer_type": "HDPE"}
        score_partial = compute_uncertainty(entity=entity, field_confidence_map=fcm, schema=sample_schema)

        fcm_full = FieldConfidenceMap()
        entity_full = {}
        for field_name in sample_schema:
            fcm_full.set(FieldConfidence(
                field_name=field_name, value="test", confidence=0.9,
                source=FieldSource.ENRICHMENT,
            ))
            entity_full[field_name] = "test"
        score_full = compute_uncertainty(entity=entity_full, field_confidence_map=fcm_full, schema=sample_schema)
        # Partial coverage → higher uncertainty
        assert score_partial > score_full

    def test_uncertainty_returns_float(self):
        score = compute_uncertainty(
            entity={"Name": "X"},
            field_confidence_map=FieldConfidenceMap(),
            schema={},
        )
        assert isinstance(score, float)
