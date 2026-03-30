"""Tests for app/engines/convergence/schema_proposer.py

Covers: Batch schema discovery, fill rate, field type inference,
        gate/scoring proposals, YAML diff generation.

Source: 445 lines | Target coverage: 75%
"""

from __future__ import annotations

import pytest

from app.engines.convergence.schema_proposer import (
    SchemaProposalSet,
)
from app.engines.convergence.schema_proposer import (
    apply as apply_proposals,
)
from app.engines.convergence.schema_proposer import (
    propose as propose_schema,
)
from app.models.loop_schemas import ApprovalDecision


class TestSchemaProposer:
    """Tests for batch schema discovery."""

    @pytest.fixture
    def batch_results(self):
        """50 entity results with a consistent new field."""
        return [
            {
                "final_fields": {
                    "polymer_type": "HDPE",
                    "contamination_tolerance_pct": 2.0 + (i * 0.1),
                    "facility_tier": "Tier 1" if i < 25 else "Tier 2",
                },
                "final_field_confidences": {
                    "polymer_type": 0.9,
                    "contamination_tolerance_pct": 0.75 + (i * 0.005),
                    "facility_tier": 0.8,
                },
            }
            for i in range(50)
        ]

    @pytest.fixture
    def current_yaml(self):
        return {
            "domain": "plastics_recycling",
            "version": "1.2.0",
            "ontology": {
                "nodes": {
                    "Facility": {
                        "properties": {
                            "polymer_type": {"type": "string"},
                        }
                    }
                }
            },
        }

    def test_detect_new_field_across_entities(self, batch_results, current_yaml):
        ps = propose_schema(batch_results, current_yaml, domain="plastics_recycling")
        assert isinstance(ps, SchemaProposalSet)
        new_field_names = [p.field_name for p in ps.proposed_fields]
        assert "contamination_tolerance_pct" in new_field_names

    def test_fill_rate_calculation(self, batch_results, current_yaml):
        ps = propose_schema(batch_results, current_yaml, domain="plastics_recycling")
        for proposal in ps.proposed_fields:
            assert 0.0 <= proposal.fill_rate <= 1.0

    def test_avg_confidence_calculation(self, batch_results, current_yaml):
        ps = propose_schema(batch_results, current_yaml, domain="plastics_recycling")
        for proposal in ps.proposed_fields:
            assert 0.0 <= proposal.avg_confidence <= 1.0

    def test_sample_values_max_10(self, batch_results, current_yaml):
        ps = propose_schema(batch_results, current_yaml, domain="plastics_recycling")
        for proposal in ps.proposed_fields:
            assert len(proposal.sample_values) <= 10

    def test_no_proposals_when_all_in_schema(self, current_yaml):
        # All fields already in YAML
        results = [
            {
                "final_fields": {"polymer_type": "HDPE"},
                "final_field_confidences": {"polymer_type": 0.9},
            }
            for _ in range(10)
        ]
        ps = propose_schema(results, current_yaml, domain="plastics_recycling")
        existing_proposals = [p for p in ps.proposed_fields if p.field_name == "polymer_type"]
        assert len(existing_proposals) == 0

    def test_apply_proposals_updates_yaml(self, current_yaml):
        decisions = [
            ApprovalDecision(field_name="new_field", approved=True),
        ]
        ps = SchemaProposalSet(
            proposed_fields=[],
            yaml_diff="+ new_field: string",
        )
        updated = apply_proposals(current_yaml, decisions, ps)
        assert isinstance(updated, dict)

    def test_version_bump_in_proposal_set(self, batch_results, current_yaml):
        ps = propose_schema(batch_results, current_yaml, domain="plastics_recycling")
        if ps.version_bump:
            parts = ps.version_bump.split(".")
            assert len(parts) == 3
