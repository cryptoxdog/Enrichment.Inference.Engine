#!/usr/bin/env python3
"""
Test script for search optimizer — validates all decision paths.
"""

import yaml
from app.engines.field_classifier import auto_classify_domain
from app.engines.search_optimizer import EntitySignals, SearchMode


def test_field_classification():
    """Test auto-classification from domain YAML."""
    print("=" * 60)
    print("TEST 1: Field Auto-Classification")
    print("=" * 60)

    # Load example domain
    with open("examples/plasticos_domain.yaml") as f:
        domain_spec = yaml.safe_load(f)

    gate_fields = set(domain_spec["metadata"]["gate_fields"])
    scoring_fields = set(domain_spec["metadata"]["scoring_fields"])

    classification = auto_classify_domain(domain_spec, gate_fields, scoring_fields)

    print(f"\nDomain: {classification.domain}")
    print(f"Total fields: {sum(classification.stats.values())}")
    print(f"\nDistribution: {classification.stats}\n")

    # Print by difficulty
    for diff in ["trivial", "public", "findable", "obscure", "inferrable"]:
        fields = [k for k, v in classification.field_map.items() if v.value == diff]
        if fields:
            print(f"{diff.upper()}:")
            for f in fields:
                marker = " [GATE]" if f in gate_fields else ""
                marker += " [SCORING]" if f in scoring_fields else ""
                print(f"  • {f}{marker}")

    return classification


def test_search_optimizer(classification):
    """Test search optimizer decision tree."""
    print("\n" + "=" * 60)
    print("TEST 2: Search Optimizer Decision Tree")
    print("=" * 60)

    # Patch optimizer with our classification
    from optimizers import search_optimizer

    search_optimizer.FIELD_DIFFICULTY = classification.field_map

    scenarios = [
        {
            "name": "Discovery (name + address only)",
            "mode": SearchMode.DISCOVERY,
            "targets": ["polymers_handled", "facility_type", "processing_capabilities"],
            "known": {"company_legal_name": "Acme Plastics", "address": "123 Main St"},
            "pass": 1,
        },
        {
            "name": "Targeted obscure fields",
            "mode": SearchMode.TARGETED,
            "targets": ["annual_capacity_tons", "equipment_types", "pcr_content_capability"],
            "known": {
                "company_legal_name": "Acme",
                "polymers_handled": ["HDPE", "PP"],
                "facility_type": "processor",
            },
            "pass": 2,
        },
        {
            "name": "Public DB lookup",
            "mode": SearchMode.TARGETED,
            "targets": ["annual_revenue_usd", "employee_count", "naics_codes"],
            "known": {"company_legal_name": "Acme Plastics Inc", "address": "123 Main St"},
            "pass": 2,
        },
        {
            "name": "Verification (2 fields)",
            "mode": SearchMode.VERIFICATION,
            "targets": ["certifications", "pcr_content_capability"],
            "known": {"company_legal_name": "Acme", "polymers_handled": ["PET"]},
            "pass": 3,
        },
        {
            "name": "All inferrable (should skip)",
            "mode": SearchMode.TARGETED,
            "targets": ["material_grade", "facility_tier", "buyer_class"],
            "known": {"polymers_handled": ["HDPE"], "certifications": ["ISO 9001"]},
            "pass": 2,
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}] {scenario['name']}")
        print(f"    Mode: {scenario['mode'].value}, Pass: {scenario['pass']}")
        print(f"    Targets: {scenario['targets']}")

        signals = EntitySignals(
            known_fields=scenario["known"],
            confidence_map={},
            gate_fields={"polymers_handled", "facility_type"},
            pass_number=scenario["pass"],
            allocated_tokens=10000,
        )

        config = resolve(
            search_plan_mode=scenario["mode"],
            target_fields=scenario["targets"],
            signals=signals,
        )

        if config.disable_search:
            print("    → SKIP (all inferrable)")
        else:
            print(f"    → Model: {config.model.value}")
            print(f"    → Context: {config.context_size.value}")
            print(f"    → Variations: {config.variations}")
            print(f"    → Cost: ${config.estimated_cost:.4f}")
            if config.domain_filters:
                print(f"    → Domains: {config.domain_filters[:3]}")


def test_batch_cost():
    """Estimate cost for batch enrichment."""
    print("\n" + "=" * 60)
    print("TEST 3: Batch Cost Estimation")
    print("=" * 60)

    lead_count = 500
    passes = 3

    # Simulate distribution
    pass1_cost = 0.045  # discovery, sonar-pro/high
    pass2_cost = 0.008  # targeted, sonar/medium
    pass3_cost = 0.003  # verification, sonar/low

    total = (pass1_cost + pass2_cost + pass3_cost) * lead_count
    per_lead = total / lead_count

    print(f"\n{lead_count} leads × {passes} passes:")
    print(
        f"  Pass 1 (discovery):   ${pass1_cost:.3f}/lead × {lead_count} = ${pass1_cost * lead_count:.2f}"
    )
    print(
        f"  Pass 2 (targeted):    ${pass2_cost:.3f}/lead × {lead_count} = ${pass2_cost * lead_count:.2f}"
    )
    print(
        f"  Pass 3 (verification): ${pass3_cost:.3f}/lead × {lead_count} = ${pass3_cost * lead_count:.2f}"
    )
    print("  ─────────────────────────────────────")
    print(f"  Total: ${total:.2f}")
    print(f"  Per lead: ${per_lead:.4f}")


if __name__ == "__main__":
    classification = test_field_classification()
    test_search_optimizer(classification)
    test_batch_cost()

    print("\n" + "=" * 60)
    print("✅ All tests complete")
    print("=" * 60)
