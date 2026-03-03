#!/usr/bin/env python3
"""
Demo: Run the simulation bridge with a typical plastics recycler CRM.
Shows seed vs enriched stats, leverage points, and executive brief.

Usage: python run_demo.py
"""
import json
import sys
sys.path.insert(0, ".")

from app.services.simulation_bridge import (
    simulate, analyze_leverage, generate_executive_brief,
    stats_to_dict, leverage_to_dict, brief_to_dict,
)

DOMAIN_SPEC = {
    "domain": {"id": "plastics-recycling", "version": "8.0.0"},
    "ontology": {"nodes": [{"label": "Partner", "properties": {
        "name": {"type": "string"}, "city": {"type": "string"},
        "phone": {"type": "string"},
        "materials_handled": {"type": "list"},
        "contamination_tolerance_pct": {"type": "float"},
        "process_types": {"type": "list"},
        "min_mfi": {"type": "float"}, "max_mfi": {"type": "float"},
        "certifications": {"type": "list"},
        "facility_size_sqft": {"type": "integer"},
        "annual_capacity_lbs": {"type": "integer"},
        "industries_served": {"type": "list"},
        "equipment_types": {"type": "list"},
        "material_forms_output": {"type": "list"},
        "polymers_handled": {"type": "list"},
        "material_grade": {"type": "string", "managed_by": "inference"},
        "facility_tier": {"type": "string", "managed_by": "inference"},
        "buyer_class": {"type": "string", "managed_by": "inference"},
    }}]},
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

# Typical recycler CRM: just name + city + phone
CUSTOMER_CRM = ["name", "city", "phone"]

if __name__ == "__main__":
    print("=" * 70)
    print("SIMULATION BRIDGE — ENRICH ↔ GRAPH Live Test")
    print("=" * 70)

    seed_stats, enriched_stats, seed_ents, enriched_ents = simulate(
        CUSTOMER_CRM, DOMAIN_SPEC, entity_count=20, seed=42
    )

    print(f"\nSEED (customer\'s current CRM):")
    print(f"  Gate pass rate:     {seed_stats.gate_pass_rate}%")
    print(f"  Entities blocked:   {seed_stats.entities_blocked}/{seed_stats.total_entities}")
    print(f"  Avg score:          {seed_stats.avg_composite_score:.4f}")
    print(f"  Field coverage:     {seed_stats.field_coverage}%")
    print(f"  Communities:        {seed_stats.communities_found}")
    print(f"  Fields inferred:    {seed_stats.fields_inferred}")

    print(f"\nENRICHED (after convergence loop):")
    print(f"  Gate pass rate:     {enriched_stats.gate_pass_rate}%")
    print(f"  Entities blocked:   {enriched_stats.entities_blocked}/{enriched_stats.total_entities}")
    print(f"  Avg score:          {enriched_stats.avg_composite_score:.4f}")
    print(f"  Field coverage:     {enriched_stats.field_coverage}%")
    print(f"  Communities:        {enriched_stats.communities_found}")
    print(f"  Fields inferred:    {enriched_stats.fields_inferred}")
    print(f"  Cost:               ${enriched_stats.total_enrichment_cost_usd:.2f} total")

    leverage = analyze_leverage(seed_stats, enriched_stats)
    print(f"\nLEVERAGE POINTS ({len(leverage)}):")
    for lp in leverage:
        print(f"  [{lp.leverage_type.value}] {lp.title}")
        print(f"    Current:  {lp.current_state}")
        print(f"    Enriched: {lp.enriched_state}")
        print(f"    Delta:    {lp.delta}")
        print(f"    Revenue:  {lp.revenue_implication}")
        print()

    brief = generate_executive_brief("Acme Recycling", "plastics-recycling",
                                      seed_stats, enriched_stats, leverage)
    print("EXECUTIVE BRIEF:")
    print(f"  {brief.headline}")
    print(f"  Recommended tier: {brief.recommended_tier}")
    print(f"  Estimated ROI:    {brief.estimated_roi_multiple}x")
    print(f"\nREVOPS IMPACT:")
    for area, impact in brief.revops_impact.items():
        print(f"  {area}: {impact}")

    # Save full output
    with open("simulation_results.json", "w") as f:
        json.dump(brief_to_dict(brief), f, indent=2, default=str)
    print(f"\nFull results saved to simulation_results.json")
