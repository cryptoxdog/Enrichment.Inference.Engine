import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class EnrichmentWizard(models.TransientModel):
    _name = "enrichment.wizard"
    _description = "Batch Enrichment Wizard"

    lead_ids = fields.Many2many("crm.lead", string="Leads to Enrich")
    lead_count = fields.Integer(compute="_compute_lead_count")

    def _compute_lead_count(self):
        for rec in self:
            rec.lead_count = len(rec.lead_ids)

    def action_enrich_selected(self):
        for lead in self.lead_ids:
            try:
                lead.action_enrich()
            except Exception as e:
                _logger.error("Failed to enrich lead %s: %s", lead.id, e)
                continue
        return {"type": "ir.actions.act_window_close"}
