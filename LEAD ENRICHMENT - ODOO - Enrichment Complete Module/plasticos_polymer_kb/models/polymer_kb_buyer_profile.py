"""KB buyer archetypes -- used in Stage 2 scoring to boost archetype fit."""

from odoo import fields, models


class PlasticosPolymerKBBuyerProfile(models.Model):
    _name = "plasticos.polymer.kb.buyer.profile"
    _description = "KB Buyer Archetype Profile"
    _order = "buyer_id"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    buyer_id = fields.Char(required=True, index=True)
    buyer_type = fields.Char()
    industry_segment = fields.Char()
    polymer_types = fields.Char(help="Comma-separated polymer type codes")
    purity_min_pct = fields.Float()
    max_pcr_pct = fields.Float()
    quality_tiers_required = fields.Char(
        help="Comma-separated tier numbers, e.g. 1,2",
    )
    cross_polymer_contam_max_pct = fields.Float()
    pvc_contamination_max_ppm = fields.Float()
    color_preference = fields.Char()
    form_preference = fields.Char()

    # MFI window
    mi_min = fields.Float("MFI Min (g/10min)")
    mi_max = fields.Float("MFI Max (g/10min)")

    # Quality
    contamination_max_pct = fields.Float()
    density_min = fields.Float("Density Min (g/cm3)")

    # Volume
    volume_min_tons = fields.Float("Min Volume (tons/month)")
    volume_max_tons = fields.Float("Max Volume (tons/month)")

    # Descriptive
    applications = fields.Text()
    certifications_required = fields.Text()
