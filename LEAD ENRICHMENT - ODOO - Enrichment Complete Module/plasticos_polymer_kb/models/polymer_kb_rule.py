"""Recycling rules & safety constraints from polymer KB."""

from odoo import fields, models


class PlasticosPolymerKBRule(models.Model):
    _name = "plasticos.polymer.kb.rule"
    _description = "KB Recycling Rule"
    _order = "rule_id"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    rule_id = fields.Char(required=True, index=True)
    material_type = fields.Char()
    rule_text = fields.Text("Rule")
    reasoning = fields.Text()
    confidence = fields.Float()
    safety_critical = fields.Boolean(
        help="If True, this rule acts as a hard gate in Stage 1.",
    )
    action = fields.Char(help="e.g. reject_or_reroute_to_washing")
    threshold_value = fields.Float(
        help="Numeric threshold for the rule (ppm or pct).",
    )
    threshold_unit = fields.Selection(
        [("ppm", "PPM"), ("pct", "Percent")],
        default="pct",
    )
