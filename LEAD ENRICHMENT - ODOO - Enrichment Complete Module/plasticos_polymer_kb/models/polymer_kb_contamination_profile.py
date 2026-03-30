"""Contamination profiles for common scrap sources."""

from odoo import fields, models


class PlasticosPolymerKBContaminationProfile(models.Model):
    _name = "plasticos.polymer.kb.contamination.profile"
    _description = "KB Contamination Profile"
    _order = "profile_id"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    profile_id = fields.Char(required=True, index=True)
    source = fields.Char()
    contamination_level = fields.Char()
    quality_tier = fields.Integer()
    sorting_purity_pct = fields.Float()
    typical_contaminants = fields.Text()
    suitable_applications = fields.Text()
