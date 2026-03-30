from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enrichment_api_url = fields.Char(
        "Enrichment API URL",
        config_parameter="enrichment.api_url",
        default="http://enrichment-api:8000/api/v1",
    )
    enrichment_api_key = fields.Char(
        "Enrichment API Key",
        config_parameter="enrichment.api_key",
    )
    enrichment_batch_size = fields.Integer(
        "Batch Size",
        config_parameter="enrichment.batch_size",
        default=25,
    )
    enrichment_auto_enrich = fields.Boolean(
        "Auto-Enrich New Leads (Cron)",
        config_parameter="enrichment.auto_enrich",
        default=False,
    )
