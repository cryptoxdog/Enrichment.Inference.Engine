"""
Tests for Simulation Bridge — validates gate/scoring/inference/community/leverage/brief.
Run: pytest tests/test_simulation_bridge.py -v
"""

from __future__ import annotations
from app.services.simulation_bridge import (
    GateVerdict,
    LeverageType,
    SimulationMode,
    analyze_leverage,
    brief_to_dict,
    generate_executive_brief,
    generate_synthetic_entities,
    run_gates,
    run_inference,
    run_scoring,
    simulate,
)

DOMAIN_SPEC = {
    "domain": {"id": "plastics-recycling", "version": "8.0.0"},
    "ontology": {
        "nodes": [
            {
                "label": "Partner",
                "properties": {
                    "name": {"type": "string"},
                    "city": {"type": "string"},
                    "phone": {"type": "string"},
                    "materials_handled": {"type": "list"},
                    "contamination_tolerance_pct": {"type": "float"},
                    "process_types": {"type": "list"},
                    "min_mfi": {"type": "float"},
                    "max_mfi": {"type": "float"},
                    "certifications": {"type": "list"},
                    "facility_size_sqft": {"type": "integer"},
                    "annual_capacity_lbs": {"type": "integer"},
                    "industries_served": {"type": "list"},
                    "equipment_types": {"type": "list"},
                    "material_forms_output": {"type": "list"},
                    "polymers_handled": {"type": "list"},
                },
            }
        ]
    },
    "gates": [
        {"candidate_property": "materials_handled"},
        {"candidate_property": "contamination_tolerance_pct", "type": "range", "max": 5.0},
        {"candidate_property": "process_types"},
        {"candidate_property": "min_mfi", "type": "range", "max": 10.0},
        {"candidate_property": "max_mfi", "type": "range", "min": 15.0},
    ],
    "scoring_dimensions": [
        {"candidate_property": "certifications", "weight": 2.0},
        {"candidate_property": "facility_size_sqft", "weight": 1.0, "max_value": 500000},
        {"candidate_property": "annual_capacity_lbs", "weight": 1.5, "max_value": 400000000},
    ],
}

CUSTOMER_CRM_FIELDS = ["name", "city", "phone"]


class TestSyntheticGeneration:
    def test_generates_correct_count(self):
        entities = generate_synthetic_entities(CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, count=10)
        assert len(entities) == 10

    def test_only_includes_crm_fields(self):
        entities = generate_synthetic_entities(CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, count=5)
        for e in entities:
            real_fields = {k for k in e if not k.startswith("_")}
            assert real_fields <= {"name", "city", "phone"}

    def test_deterministic_with_seed(self):
        e1 = generate_synthetic_entities(CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, count=5, seed=99)
        e2 = generate_synthetic_entities(CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, count=5, seed=99)
        for a, b in zip(e1, e2):
            assert a["name"] == b["name"]


class TestGates:
    def test_insufficient_data_when_missing(self):
        results = run_gates({"name": "Test"}, {"materials_handled": ["HDPE"]}, DOMAIN_SPEC["gates"])
        insufficient = [r for r in results if r.verdict == GateVerdict.INSUFFICIENT_DATA]
        assert len(insufficient) >= 4  # most gates missing

    def test_overlap_gate_pass(self):
        entity = {"materials_handled": ["HDPE", "PP", "PET"]}
        query = {"materials_handled": ["HDPE", "LDPE"]}
        results = run_gates(entity, query, [{"candidate_property": "materials_handled"}])
        assert results[0].verdict == GateVerdict.PASS

    def test_range_gate_fail(self):
        entity = {"contamination_tolerance_pct": 12.0}
        results = run_gates(
            entity,
            {},
            [{"candidate_property": "contamination_tolerance_pct", "type": "range", "max": 5.0}],
        )
        assert results[0].verdict == GateVerdict.FAIL


class TestScoring:
    def test_scoring_returns_composite(self):
        entity = {
            "certifications": ["ISO 9001", "R2"],
            "facility_size_sqft": 100000,
            "annual_capacity_lbs": 200000000,
        }
        results, composite = run_scoring(entity, DOMAIN_SPEC["scoring_dimensions"])
        assert 0.0 < composite <= 1.0
        assert len(results) == 3

    def test_missing_field_scores_zero(self):
        entity = {"certifications": ["ISO 9001"]}
        results, _ = run_scoring(entity, DOMAIN_SPEC["scoring_dimensions"])
        missing = [r for r in results if r.raw_value is None]
        assert all(r.normalized_score == 0.0 for r in missing)


class TestInference:
    def test_material_grade_inference(self):
        fields = {
            "polymers_handled": ["HDPE"],
            "contamination_tolerance_pct": 1.5,
            "certifications": ["ISO 9001"],
        }
        inferred = run_inference(fields)
        assert "material_grade" in inferred
        assert inferred["material_grade"] == "prime"

    def test_missing_inputs_skips(self):
        fields = {"polymers_handled": ["HDPE"]}
        inferred = run_inference(fields)
        assert "material_grade" not in inferred  # missing contamination_tolerance_pct


class TestFullSimulation:
    def test_dual_simulation(self):
        seed_stats, enriched_stats, seed_ents, enriched_ents = simulate(
            CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, entity_count=20
        )
        assert seed_stats.mode == SimulationMode.SEED_ONLY
        assert enriched_stats.mode == SimulationMode.FULL_GRAPH
        assert enriched_stats.gate_pass_rate >= seed_stats.gate_pass_rate
        assert enriched_stats.field_coverage >= seed_stats.field_coverage

    def test_enriched_has_communities(self):
        _, enriched_stats, _, _ = simulate(CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, entity_count=20)
        assert enriched_stats.communities_found >= 1


class TestLeverage:
    def test_leverage_points_generated(self):
        seed_stats, enriched_stats, _, _ = simulate(
            CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, entity_count=20
        )
        points = analyze_leverage(seed_stats, enriched_stats)
        assert len(points) >= 1
        types = {p.leverage_type for p in points}
        assert LeverageType.MATCHING_PRECISION in types or LeverageType.PIPELINE_VELOCITY in types


class TestExecutiveBrief:
    def test_brief_generation(self):
        seed_stats, enriched_stats, _, _ = simulate(
            CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, entity_count=20
        )
        leverage = analyze_leverage(seed_stats, enriched_stats)
        brief = generate_executive_brief(
            "Acme Recycling", "plastics-recycling", seed_stats, enriched_stats, leverage
        )
        assert brief.customer_name == "Acme Recycling"
        assert brief.estimated_roi_multiple > 0
        assert "revops_impact" in brief_to_dict(brief)
        assert len(brief.revops_impact) == 5

    def test_brief_serialization(self):
        seed_stats, enriched_stats, _, _ = simulate(
            CUSTOMER_CRM_FIELDS, DOMAIN_SPEC, entity_count=10
        )
        leverage = analyze_leverage(seed_stats, enriched_stats)
        brief = generate_executive_brief(
            "Test Co", "plastics", seed_stats, enriched_stats, leverage
        )
        d = brief_to_dict(brief)
        assert "headline" in d
        assert "leverage_points" in d
        assert "combined_narrative" in d
