import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EnrichmentRun(models.Model):
    _name = "enrichment.run"
    _description = "Enrichment Run Log"
    _order = "create_date desc"
    _rec_name = "display_name"

    # ── Identity ─────────────────────────────────────
    res_model = fields.Char("Source Model", required=True, index=True)
    res_id = fields.Many2oneReference("Source Record", model_field="res_model", index=True)
    idempotency_key = fields.Char("Idempotency Key", index=True)

    # ── State ────────────────────────────────────────
    state = fields.Selection([
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ], default="pending", required=True, index=True)

    # ── Results ──────────────────────────────────────
    confidence = fields.Float("Confidence", digits=(3, 4))
    fields_enriched = fields.Integer("Fields Enriched")
    enriched_data = fields.Text("Enriched Data (JSON)")
    failure_reason = fields.Text("Failure Reason")

    # ── Provenance ───────────────────────────────────
    variation_count = fields.Integer("Variations Used")
    consensus_threshold = fields.Float("Consensus Threshold")
    kb_content_hash = fields.Char("KB Content Hash")
    inference_version = fields.Char("Inference Version")
    tokens_used = fields.Integer("Tokens Used")
    processing_time_ms = fields.Integer("Processing Time (ms)")

    # ── Full response for replay ─────────────────────
    raw_response = fields.Text("Raw API Response (JSON)")

    # ── Computed ─────────────────────────────────────
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("res_model", "res_id", "state")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.res_model}/{rec.res_id} [{rec.state}]"

    def action_view_source_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
