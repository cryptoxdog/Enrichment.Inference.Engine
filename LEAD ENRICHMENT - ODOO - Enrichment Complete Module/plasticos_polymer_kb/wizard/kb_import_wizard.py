"""Wizard to import polymer KB from uploaded YAML file."""

import base64
import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KBImportWizard(models.TransientModel):
    _name = "plasticos.polymer.kb.import.wizard"
    _description = "Import Polymer KB from YAML"

    yaml_file = fields.Binary("YAML File", required=True)
    filename = fields.Char()

    def action_import(self):
        """Parse uploaded YAML and create/update KB records."""
        self.ensure_one()
        if not self.yaml_file:
            raise UserError("Please upload a YAML file.")
        if self.filename and not self.filename.endswith((".yaml", ".yml")):
            raise UserError("File must be .yaml or .yml")

        raw = base64.b64decode(self.yaml_file).decode("utf-8")
        KB = self.env["plasticos.polymer.kb"]
        kb = KB.load_from_yaml(raw)
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.polymer.kb",
            "res_id": kb.id,
            "view_mode": "form",
            "target": "current",
        }
