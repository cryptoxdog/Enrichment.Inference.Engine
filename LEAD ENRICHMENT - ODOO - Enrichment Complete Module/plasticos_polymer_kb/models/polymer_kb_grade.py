"""Material grade definitions from polymer KB (e.g. PP Homopolymer Injection)."""

from odoo import fields, models


class PlasticosPolymerKBGrade(models.Model):
    _name = "plasticos.polymer.kb.grade"
    _description = "KB Material Grade"
    _order = "grade_id"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    grade_id = fields.Char(required=True, index=True)
    grade_name = fields.Char()
    description = fields.Text()
    grade_type = fields.Char(help="virgin, recycled, etc.")
    polymer_structure = fields.Char()

    # Processing windows
    mi_min = fields.Float("MFI Min (g/10min)")
    mi_max = fields.Float("MFI Max (g/10min)")
    density_min = fields.Float("Density Min (g/cm3)")
    density_max = fields.Float("Density Max (g/cm3)")

    # Mechanical
    tensile_strength_min = fields.Float("Tensile Strength Min (MPa)")
    impact_strength_min = fields.Float("Impact Strength Min (J/m)")

    # Thermal
    processing_temp_min = fields.Float("Processing Temp Min (C)")
    processing_temp_max = fields.Float("Processing Temp Max (C)")

    # PCR
    max_pcr_pct = fields.Float("Max PCR %")
