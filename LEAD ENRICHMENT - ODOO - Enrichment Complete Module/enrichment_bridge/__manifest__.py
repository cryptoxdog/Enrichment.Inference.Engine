{
    "name": "Enrichment Bridge",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Bridge to external Enrichment API — enrich CRM leads, contacts, accounts",
    "description": """
        Connects Odoo to the Domain Enrichment API v2.2.
        Supports single-record enrichment (button), batch enrichment (cron),
        and enrichment run logging with full provenance.

        Compatible with:
        - CRM Leads (crm.lead)
        - Contacts (res.partner)
        - Any model via configuration
    """,
    "author": "Igor Beylin",
    "website": "https://github.com/cryptoxdog/enrichment-api",
    "license": "LGPL-3",
    "depends": ["base", "crm", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "views/enrichment_run_views.xml",
        "views/crm_lead_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/enrichment_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
