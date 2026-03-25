{
    "name": "PlastOS Polymer Knowledge Base",
    "version": "19.0.1.0.0",
    "category": "Plasticos/Matching",
    "summary": "Polymer knowledge bases for AI-driven buyer matching",
    "description": """
        Stores polymer-specific compounding & recycling knowledge bases
        (PP, HDPE, etc.) as structured Odoo records.  Provides:

        * Material grade definitions with MFI / density / mechanical ranges
        * Quality tier definitions (Tier 1-4) with contamination thresholds
        * Recycling rules & safety-critical constraints
        * KB buyer-profile archetypes for Stage 2 scoring
        * Inference rules for forward/backward buyer matching
        * YAML import wizard for domain-expert self-service updates
        * Neo4j sync helpers for graph-based scoring enrichment
    """,
    "author": "PlastOS",
    "license": "LGPL-3",
    "depends": [
        "base",
        "plasticos_buyer_match_engine",
        "plasticos_material_profile",
        "plasticos_facility_profile",
    ],
    "external_dependencies": {
        "python": ["pyyaml"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/polymer_kb_views.xml",
        "views/polymer_kb_menu.xml",
        "wizard/kb_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
