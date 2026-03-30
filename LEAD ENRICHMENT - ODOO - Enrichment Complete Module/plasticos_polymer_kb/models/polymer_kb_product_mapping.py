"""Product-to-scrap bidirectional mappings."""

from odoo import fields, models


class PlasticosPolymerKBProductMapping(models.Model):
    _name = "plasticos.polymer.kb.product.mapping"
    _description = "KB Product-Scrap Mapping"
    _order = "category, product"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    category = fields.Char(index=True, help="e.g. packaging_products")
    product = fields.Char()
    scrap_grade = fields.Char()
    quality_tier_min = fields.Integer()
    quality_tier_max = fields.Integer()
    contamination_min_pct = fields.Float()
    contamination_max_pct = fields.Float()
    typical_contaminants = fields.Text()
    suitable_buyers = fields.Char(help="Comma-separated buyer archetype IDs")
    reverse_reasoning = fields.Text()
    note = fields.Text()
