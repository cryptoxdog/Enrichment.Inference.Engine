"""Forward / backward inference rules for buyer matching."""

from odoo import fields, models


class PlasticosPolymerKBInferenceRule(models.Model):
    _name = "plasticos.polymer.kb.inference.rule"
    _description = "KB Inference Rule"
    _order = "rule_id"

    kb_id = fields.Many2one(
        "plasticos.polymer.kb",
        required=True,
        ondelete="cascade",
        index=True,
    )
    rule_id = fields.Char(required=True, index=True)
    inference_type = fields.Selection(
        [
            ("buyer_matching", "Buyer Matching"),
            ("source_matching", "Source Matching"),
            ("application_matching", "Application Matching"),
            ("quality_control", "Quality Control"),
            ("processing_requirement", "Processing Requirement"),
        ]
    )
    logic = fields.Text()
    reasoning = fields.Text()
    confidence = fields.Float()
