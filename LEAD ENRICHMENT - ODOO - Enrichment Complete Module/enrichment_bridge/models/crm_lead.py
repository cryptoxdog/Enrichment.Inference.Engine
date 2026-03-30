import json
import logging
import uuid

import requests
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = ["crm.lead", "enrichment.mixin"]
    _name = "crm.lead"

    def _prepare_enrichment_entity(self):
        self.ensure_one()
        entity = {}
        field_map = {
            "name": self.name,
            "contact_name": self.contact_name,
            "partner_name": self.partner_name,
            "email_from": self.email_from,
            "phone": self.phone,
            "website": self.website,
            "street": self.street,
            "city": self.city,
            "country_id": self.country_id.name if self.country_id else None,
            "state_id": self.state_id.name if self.state_id else None,
            "function": self.function,
            "description": self.description,
        }
        for k, v in field_map.items():
            if v:
                entity[k] = v
        return entity

    def _get_enrichment_schema(self):
        return {
            "description": "text",
            "function": "string",
            "website": "string",
            "phone": "string",
            "street": "string",
            "city": "string",
            "expected_revenue": "float",
        }

    def _get_enrichment_objective(self):
        return (
            "Research this CRM lead. Find the company website, phone, "
            "key contact role, address, and expected revenue. "
            "Identify the industry and any relevant business context."
        )

    def _get_enrichment_object_type(self):
        return "Lead" if self.type == "lead" else "Opportunity"

    @api.model
    def cron_batch_enrich(self):
        ICP = self.env["ir.config_parameter"].sudo()
        url = ICP.get_param("enrichment.api_url", "http://enrichment-api:8000/api/v1")
        key = ICP.get_param("enrichment.api_key", "")
        batch_size = int(ICP.get_param("enrichment.batch_size", "25"))
        auto_enrich = ICP.get_param("enrichment.auto_enrich", "False")

        if auto_enrich != "True":
            _logger.info("Enrichment auto_enrich is disabled, skipping cron")
            return

        if not key or key == "CHANGEME":
            _logger.warning("Enrichment API key not configured, skipping cron")
            return

        leads = self.search(
            [
                ("enrichment_state", "=", "not_enriched"),
                ("type", "=", "lead"),
                ("active", "=", True),
            ],
            limit=batch_size,
            order="create_date desc",
        )

        if not leads:
            _logger.info("No leads to enrich")
            return

        _logger.info("Batch enriching %d leads", len(leads))

        entities = []
        for lead in leads:
            entities.append(
                {
                    "entity": lead._prepare_enrichment_entity(),
                    "object_type": lead._get_enrichment_object_type(),
                    "objective": lead._get_enrichment_objective(),
                    "schema": lead._get_enrichment_schema(),
                    "idempotency_key": str(uuid.uuid4()),
                    "max_variations": 3,
                }
            )

        try:
            resp = requests.post(
                f"{url}/enrich/batch",
                json={"entities": entities},
                headers={
                    "X-API-Key": key,
                    "Content-Type": "application/json",
                },
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            for lead, result in zip(leads, results):
                run = self.env["enrichment.run"].create(
                    {
                        "res_model": "crm.lead",
                        "res_id": lead.id,
                        "state": result.get("state", "failed"),
                        "confidence": result.get("confidence", 0),
                        "fields_enriched": len(result.get("fields", {})),
                        "enriched_data": json.dumps(result.get("fields", {}), indent=2),
                        "failure_reason": result.get("failure_reason"),
                        "variation_count": result.get("variation_count", 0),
                        "tokens_used": result.get("tokens_used", 0),
                        "processing_time_ms": result.get("processing_time_ms", 0),
                        "raw_response": json.dumps(result, indent=2),
                    }
                )

                if result.get("state") == "completed" and result.get("fields"):
                    lead._apply_enrichment(result["fields"])
                    lead.write(
                        {
                            "enrichment_state": "enriched",
                            "last_enrichment_date": fields.Datetime.now(),
                            "last_enrichment_confidence": result.get("confidence", 0),
                        }
                    )
                elif result.get("state") == "failed":
                    lead.write({"enrichment_state": "failed"})

            self.env.cr.commit()
            _logger.info(
                "Batch enrichment complete: %d succeeded, %d failed",
                data.get("succeeded", 0),
                data.get("failed", 0),
            )

        except Exception as e:
            _logger.exception("Batch enrichment failed: %s", e)
