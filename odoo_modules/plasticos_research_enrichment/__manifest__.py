{  # noqa: B018 — Odoo manifest convention
    "name": "Plasticos Research Enrichment v2",
    "version": "19.0.2.0.0",
    "category": "Automation",
    "depends": [
        "base",
        "contacts",
        "plasticos_enrichment",
        "plasticos_inference_engine",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/enrichment_profile_views.xml",
        "views/enrichment_run_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
