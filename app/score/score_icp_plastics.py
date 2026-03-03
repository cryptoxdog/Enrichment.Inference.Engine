"""
SCORE Service — Plastics Recycling Domain ICP
revopsos-score-engine

Canonical ICP definition for the plastics recycling vertical.
Demonstrates domain-specific field criteria with gate-critical
fields, range matching, and weighted-set scoring.
"""

from __future__ import annotations

from score_models import (
    ICPDefinition,
    ICPFieldCriterion,
    ICPFieldType,
    ScoreDimension,
)


def build_plastics_recycling_icp() -> ICPDefinition:
    """
    Build the canonical ICP for plastics recycling facilities.

    This ICP reflects the deep domain knowledge injected by ENRICH:
    fields like contamination_tolerance_pct, mfi_range, and
    facility_tier are discovered (not predefined) by the schema
    discovery loop.
    """
    return ICPDefinition(
        name="Plastics Recycling - Premium HDPE Buyer",
        domain="plastics_recycling",
        description=(
            "High-capacity recyclers processing HDPE with tight contamination "
            "tolerances and documented MFI specifications. Targets Tier 1/2 "
            "facilities with verified processing capacity."
        ),
        criteria=[
            # ── FIT Dimension: Material & Facility ────────────
            ICPFieldCriterion(
                field_name="primary_resin",
                field_type=ICPFieldType.EXACT_MATCH,
                target_value="HDPE",
                weight=0.90,
                is_gate_critical=True,
                dimension=ScoreDimension.FIT,
                description="Must process HDPE as primary resin",
            ),
            ICPFieldCriterion(
                field_name="facility_tier",
                field_type=ICPFieldType.WEIGHTED_SET,
                target_set=["tier_1", "tier_2", "tier_3"],
                set_weights={"tier_1": 1.0, "tier_2": 0.75, "tier_3": 0.30},
                weight=0.80,
                is_gate_critical=True,
                dimension=ScoreDimension.FIT,
                description="Facility tier classification (tier_1 = highest)",
            ),
            ICPFieldCriterion(
                field_name="contamination_tolerance_pct",
                field_type=ICPFieldType.RANGE,
                target_range=(0.5, 3.0),
                weight=0.75,
                is_gate_critical=False,
                dimension=ScoreDimension.FIT,
                description="Contamination tolerance 0.5-3.0% (tight spec preferred)",
            ),
            ICPFieldCriterion(
                field_name="mfi_range",
                field_type=ICPFieldType.RANGE,
                target_range=(0.3, 12.0),
                weight=0.70,
                is_gate_critical=False,
                dimension=ScoreDimension.FIT,
                description="Melt Flow Index range (g/10min) indicating material grade",
            ),
            ICPFieldCriterion(
                field_name="material_grade",
                field_type=ICPFieldType.WEIGHTED_SET,
                target_set=["injection", "blow_molding", "extrusion", "film"],
                set_weights={
                    "injection": 1.0,
                    "blow_molding": 0.90,
                    "extrusion": 0.70,
                    "film": 0.50,
                },
                weight=0.65,
                dimension=ScoreDimension.FIT,
                description="End-use material grade classification",
            ),
            ICPFieldCriterion(
                field_name="processing_capacity_tons_month",
                field_type=ICPFieldType.RANGE,
                target_range=(500, 50000),
                weight=0.60,
                dimension=ScoreDimension.FIT,
                description="Monthly processing capacity in tons",
            ),
            ICPFieldCriterion(
                field_name="has_quality_certification",
                field_type=ICPFieldType.BOOLEAN,
                target_value=True,
                weight=0.50,
                dimension=ScoreDimension.FIT,
                description="ISO 9001 or equivalent quality certification",
            ),
            ICPFieldCriterion(
                field_name="color_sorting_capability",
                field_type=ICPFieldType.BOOLEAN,
                target_value=True,
                weight=0.40,
                dimension=ScoreDimension.FIT,
                description="Optical/NIR color sorting equipment",
            ),
            ICPFieldCriterion(
                field_name="geographic_region",
                field_type=ICPFieldType.WEIGHTED_SET,
                target_set=["southeast_us", "midwest_us", "northeast_us", "west_us"],
                set_weights={
                    "southeast_us": 1.0,
                    "midwest_us": 0.85,
                    "northeast_us": 0.70,
                    "west_us": 0.60,
                },
                weight=0.35,
                dimension=ScoreDimension.FIT,
                description="Geographic proximity to feedstock sources",
            ),

            # ── READINESS Dimension ───────────────────────────
            ICPFieldCriterion(
                field_name="has_procurement_contact",
                field_type=ICPFieldType.BOOLEAN,
                target_value=True,
                weight=0.70,
                dimension=ScoreDimension.READINESS,
                description="Identified procurement/purchasing decision-maker",
            ),
            ICPFieldCriterion(
                field_name="current_supplier_count",
                field_type=ICPFieldType.RANGE,
                target_range=(1, 5),
                weight=0.50,
                dimension=ScoreDimension.READINESS,
                description="Currently sourcing from 1-5 suppliers (not locked in)",
            ),
            ICPFieldCriterion(
                field_name="contract_renewal_within_90d",
                field_type=ICPFieldType.BOOLEAN,
                target_value=True,
                weight=0.80,
                dimension=ScoreDimension.READINESS,
                description="Supply contract up for renewal within 90 days",
            ),

            # ── INTENT Dimension ──────────────────────────────
            ICPFieldCriterion(
                field_name="pricing_page_visits",
                field_type=ICPFieldType.RANGE,
                target_range=(2, 100),
                weight=0.80,
                dimension=ScoreDimension.INTENT,
                description="Multiple visits to pricing/spec pages",
            ),
            ICPFieldCriterion(
                field_name="sample_request",
                field_type=ICPFieldType.BOOLEAN,
                target_value=True,
                weight=0.90,
                dimension=ScoreDimension.INTENT,
                description="Submitted a material sample request",
            ),
        ],
    )


# ── Quick Access ──────────────────────────────────────────────

PLASTICS_ICP = build_plastics_recycling_icp()


def get_plastics_gate_fields() -> list[str]:
    """Return gate-critical field names for quick reference."""
    return [c.field_name for c in PLASTICS_ICP.gate_criteria]


def get_plastics_field_summary() -> dict[str, dict]:
    """Return a summary of all ICP fields grouped by dimension."""
    summary: dict[str, dict] = {}
    for dim, criteria in PLASTICS_ICP.criteria_by_dimension.items():
        summary[dim.value] = {
            "field_count": len(criteria),
            "gate_critical": [c.field_name for c in criteria if c.is_gate_critical],
            "fields": [
                {
                    "name": c.field_name,
                    "type": c.field_type.value,
                    "weight": c.weight,
                    "gate_critical": c.is_gate_critical,
                }
                for c in criteria
            ],
        }
    return summary
'''