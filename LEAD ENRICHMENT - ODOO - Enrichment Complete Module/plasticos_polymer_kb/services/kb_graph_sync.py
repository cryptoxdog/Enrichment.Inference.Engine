# -*- coding: utf-8 -*-
"""Push KB buyer-profile archetypes + grade nodes to Neo4j.

Called by ``plasticos.polymer.kb.action_sync_to_graph()``.
"""
import logging

_logger = logging.getLogger(__name__)


def sync_kb_to_graph(graph_service, kb_record):
    """Sync a single KB record to Neo4j.

    Creates/updates:
    - ``(:PolymerKB {polymer_type})`` node
    - ``(:KBGrade {grade_id})`` nodes  +  ``[:HAS_GRADE]`` edges
    - ``(:KBBuyerProfile {buyer_id})`` nodes  +  ``[:HAS_KB_PROFILE]`` edges
    """
    polymer_type = kb_record.polymer_type

    # 1. Upsert PolymerKB node
    graph_service.execute_cypher_query(
        """
        MERGE (kb:PolymerKB {polymer_type: $polymer_type})
        SET kb.version       = $version,
            kb.data_quality  = $data_quality,
            kb.full_name     = $full_name,
            kb.updated_at_utc = datetime()
        """,
        {
            "polymer_type": polymer_type,
            "version": kb_record.version or "",
            "data_quality": kb_record.data_quality or "",
            "full_name": kb_record.full_name or "",
        },
        metadata={"name": f"kb_sync_{polymer_type}_node"},
    )

    # 2. Upsert Grade nodes
    grade_payloads = []
    for g in kb_record.grade_ids:
        grade_payloads.append({
            "grade_id": g.grade_id,
            "grade_name": g.grade_name or "",
            "mi_min": g.mi_min or 0.0,
            "mi_max": g.mi_max or 0.0,
            "density_min": g.density_min or 0.0,
            "density_max": g.density_max or 0.0,
            "max_pcr_pct": g.max_pcr_pct or 0.0,
            "processing_temp_min": g.processing_temp_min or 0.0,
            "processing_temp_max": g.processing_temp_max or 0.0,
        })
    if grade_payloads:
        graph_service.execute_cypher_query(
            """
            UNWIND $grades AS g
            MERGE (gr:KBGrade {grade_id: g.grade_id})
            SET gr.grade_name         = g.grade_name,
                gr.mi_min             = g.mi_min,
                gr.mi_max             = g.mi_max,
                gr.density_min        = g.density_min,
                gr.density_max        = g.density_max,
                gr.max_pcr_pct        = g.max_pcr_pct,
                gr.processing_temp_min = g.processing_temp_min,
                gr.processing_temp_max = g.processing_temp_max,
                gr.updated_at_utc     = datetime()
            WITH gr, g
            MATCH (kb:PolymerKB {polymer_type: $polymer_type})
            MERGE (kb)-[:HAS_GRADE]->(gr)
            """,
            {"grades": grade_payloads, "polymer_type": polymer_type},
            metadata={"name": f"kb_sync_{polymer_type}_grades"},
        )

    # 3. Upsert KBBuyerProfile nodes
    bp_payloads = []
    for bp in kb_record.buyer_profile_ids:
        bp_payloads.append({
            "buyer_id": bp.buyer_id,
            "buyer_type": bp.buyer_type or "",
            "industry_segment": bp.industry_segment or "",
            "polymer_types": bp.polymer_types or "",
            "mi_min": bp.mi_min or 0.0,
            "mi_max": bp.mi_max or 0.0,
            "contamination_max_pct": bp.contamination_max_pct or 0.0,
            "density_min": bp.density_min or 0.0,
            "quality_tiers_required": bp.quality_tiers_required or "",
            "purity_min_pct": bp.purity_min_pct or 0.0,
            "max_pcr_pct": bp.max_pcr_pct or 0.0,
            "cross_polymer_contam_max_pct": bp.cross_polymer_contam_max_pct or 0.0,
            "pvc_contamination_max_ppm": bp.pvc_contamination_max_ppm or 0.0,
            "form_preference": bp.form_preference or "",
            "color_preference": bp.color_preference or "",
            "volume_min_tons": bp.volume_min_tons or 0.0,
            "volume_max_tons": bp.volume_max_tons or 0.0,
        })
    if bp_payloads:
        graph_service.execute_cypher_query(
            """
            UNWIND $profiles AS p
            MERGE (bp:KBBuyerProfile {buyer_id: p.buyer_id})
            SET bp.buyer_type                   = p.buyer_type,
                bp.industry_segment             = p.industry_segment,
                bp.polymer_types                = p.polymer_types,
                bp.mi_min                       = p.mi_min,
                bp.mi_max                       = p.mi_max,
                bp.contamination_max_pct        = p.contamination_max_pct,
                bp.density_min                  = p.density_min,
                bp.quality_tiers_required       = p.quality_tiers_required,
                bp.purity_min_pct               = p.purity_min_pct,
                bp.max_pcr_pct                  = p.max_pcr_pct,
                bp.cross_polymer_contam_max_pct = p.cross_polymer_contam_max_pct,
                bp.pvc_contamination_max_ppm    = p.pvc_contamination_max_ppm,
                bp.form_preference              = p.form_preference,
                bp.color_preference             = p.color_preference,
                bp.volume_min_tons              = p.volume_min_tons,
                bp.volume_max_tons              = p.volume_max_tons,
                bp.updated_at_utc               = datetime()
            WITH bp, p
            MATCH (kb:PolymerKB {polymer_type: $polymer_type})
            MERGE (kb)-[:HAS_KB_PROFILE]->(bp)
            """,
            {"profiles": bp_payloads, "polymer_type": polymer_type},
            metadata={"name": f"kb_sync_{polymer_type}_buyer_profiles"},
        )

    _logger.info(
        "KB sync complete: %s -- %d grades, %d buyer profiles",
        polymer_type, len(grade_payloads), len(bp_payloads),
    )
