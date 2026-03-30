"""Quality tier definitions (Tier 1 Premium -> Tier 4 Marginal)."""

from odoo import fields, models


class PlasticosPolymerKBTier(models.Model):
    _name = "plasticos.polymer.kb.tier"
    _description = "KB Quality Tier"
    _order = "tier_key"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    tier_key = fields.Char(
        required=True,
        index=True,
        help="e.g. tier_1_premium, tier_2_standard",
    )
    definition = fields.Text()
    contamination_max_pct = fields.Float()
    cross_polymer_contam_max_pct = fields.Float(
        help="PP contam for HDPE KB; PE contam for PP KB",
    )
    moisture_max_pct = fields.Float()
    moisture_max_ppm = fields.Float()
    ash_max_pct = fields.Float()
    property_retention_min_pct = fields.Float()
    sorting_purity_min_pct = fields.Float()
    processing_history = fields.Char()
    mi_change_max_pct = fields.Float("MFI Change Max %")
