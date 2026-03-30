import json
import logging
import uuid

import requests
from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 120


class EnrichmentMixin(models.AbstractModel):
    _name = "enrichment.mixin"
    _description = "Enrichment Mixin"

    enrichment_run_ids = fields.One2many(
        "enrichment.run",
        "res_id",
        string="Enrichment Runs",
        domain=lambda self: [("res_model", "=", self._name)],
    )
    enrichment_state = fields.Selection(
        [
            ("not_enriched", "Not Enriched"),
            ("enriched", "Enriched"),
            ("failed", "Failed"),
        ],
        default="not_enriched",
        tracking=True,
    )
    last_enrichment_date = fields.Datetime("Last Enrichment")
    last_enrichment_confidence = fields.Float("Last Confidence", digits=(3, 4))

    def _get_api_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        url = ICP.get_param("enrichment.api_url", "http://enrichment-api:8000/api/v1")
        key = ICP.get_param("enrichment.api_key", "")
        if not key or key == "CHANGEME":
            raise UserError("Enrichment API key not configured. Go to Settings > Enrichment.")
        return url, key

    def _prepare_enrichment_entity(self):
        self.ensure_one()
        result = {}
        for field_name, field_obj in self._fields.items():
            if field_obj.type in ("char", "text", "selection", "float", "integer", "boolean"):
                val = self[field_name]
                if val and val is not False:
                    result[field_name] = val
            elif field_obj.type == "many2one":
                val = self[field_name]
                if val:
                    result[field_name] = val.display_name
        return result

    def _get_enrichment_objective(self):
        return (
            f"Research and enrich this {self._description or self._name} record with missing data."
        )

    def _get_enrichment_schema(self):
        return None

    def _get_enrichment_object_type(self):
        return self._name

    def action_enrich(self):
        self.ensure_one()
        url, key = self._get_api_config()
        idem_key = str(uuid.uuid4())

        entity = self._prepare_enrichment_entity()
        payload = {
            "entity": entity,
            "object_type": self._get_enrichment_object_type(),
            "objective": self._get_enrichment_objective(),
            "idempotency_key": idem_key,
        }

        schema = self._get_enrichment_schema()
        if schema:
            payload["schema"] = schema

        run = self.env["enrichment.run"].create(
            {
                "res_model": self._name,
                "res_id": self.id,
                "idempotency_key": idem_key,
                "state": "pending",
            }
        )

        try:
            resp = requests.post(
                f"{url}/enrich",
                json=payload,
                headers={
                    "X-API-Key": key,
                    "Content-Type": "application/json",
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            run.write(
                {
                    "state": data.get("state", "completed"),
                    "confidence": data.get("confidence", 0),
                    "fields_enriched": len(data.get("fields", {})),
                    "enriched_data": json.dumps(data.get("fields", {}), indent=2),
                    "failure_reason": data.get("failure_reason"),
                    "variation_count": data.get("variation_count", 0),
                    "consensus_threshold": data.get("consensus_threshold", 0),
                    "kb_content_hash": data.get("kb_content_hash", ""),
                    "inference_version": data.get("inference_version", ""),
                    "tokens_used": data.get("tokens_used", 0),
                    "processing_time_ms": data.get("processing_time_ms", 0),
                    "raw_response": json.dumps(data, indent=2),
                }
            )

            if data.get("state") == "completed" and data.get("fields"):
                self._apply_enrichment(data["fields"])
                self.write(
                    {
                        "enrichment_state": "enriched",
                        "last_enrichment_date": fields.Datetime.now(),
                        "last_enrichment_confidence": data.get("confidence", 0),
                    }
                )
            elif data.get("state") == "failed":
                self.write({"enrichment_state": "failed"})

        except requests.Timeout:
            run.write({"state": "failed", "failure_reason": "API timeout"})
            self.write({"enrichment_state": "failed"})
            _logger.error("Enrichment API timeout for %s/%s", self._name, self.id)

        except requests.RequestException as e:
            run.write({"state": "failed", "failure_reason": str(e)})
            self.write({"enrichment_state": "failed"})
            _logger.error("Enrichment API error for %s/%s: %s", self._name, self.id, e)

        except Exception as e:
            run.write({"state": "failed", "failure_reason": str(e)})
            self.write({"enrichment_state": "failed"})
            _logger.exception("Unexpected enrichment error for %s/%s", self._name, self.id)

        return True

    def _apply_enrichment(self, enriched_fields):
        self.ensure_one()
        vals = {}
        for field_name, value in enriched_fields.items():
            if field_name not in self._fields:
                continue
            field_obj = self._fields[field_name]
            current = self[field_name]
            if current and current is not False:
                continue
            if field_obj.type in ("char", "text") and isinstance(value, str):
                vals[field_name] = value
            elif field_obj.type == "float" and isinstance(value, (int, float)):
                vals[field_name] = float(value)
            elif field_obj.type == "integer" and isinstance(value, (int, float)):
                vals[field_name] = int(value)
            elif field_obj.type == "boolean" and isinstance(value, bool):
                vals[field_name] = value
            elif field_obj.type == "selection":
                valid_keys = [k for k, _ in field_obj.selection]
                if value in valid_keys:
                    vals[field_name] = value

        if vals:
            self.write(vals)
            _logger.info("Enrichment applied %d fields to %s/%s", len(vals), self._name, self.id)
