"""
CRM write-back orchestration layer.

Coordinates field mapping, conflict detection, and idempotent upserts
back to the originating CRM. Odoo is the first consumer; Salesforce
and HubSpot can be added by implementing CRMClientBase.

L9 Architecture Note:
    This module is chassis-agnostic. It never imports FastAPI.
    It is called by handlers.py via the 'writeback' action.
"""

from __future__ import annotations

from typing import Any

import structlog

from .base import CRMClientBase, CRMCredentials, CRMType, WriteResult
from .field_mapper import FieldMapper
from .odoo_client import OdooClient

logger = structlog.get_logger("crm_writeback")


class WriteBackOrchestrator:
    """
    High-level facade for CRM write-back.

    Responsibilities:
    - Select correct CRM client based on CRMType
    - Map canonical enrichment fields to CRM schema
    - Decide create/update/upsert strategy
    - Log results and errors deterministically
    """

    def __init__(
        self,
        crm_type: CRMType,
        credentials: dict[str, str],
        mapping_path: str,
    ) -> None:
        self.crm_type = crm_type
        self.mapper = FieldMapper(mapping_path)
        creds = CRMCredentials(crm_type=crm_type, credentials=credentials)
        self.client: CRMClientBase = self._init_client(creds)

    def _init_client(self, creds: CRMCredentials) -> CRMClientBase:
        """Instantiate the correct CRM client and connect."""
        if creds.crm_type == CRMType.ODOO:
            client = OdooClient(creds)
        else:
            msg = f"Unsupported CRM type: {creds.crm_type}"
            raise ValueError(msg)

        if not client.connect():
            msg = f"Failed to connect to CRM: {creds.crm_type.value}"
            raise RuntimeError(msg)
        return client

    def _detect_existing_record(
        self,
        domain: str,
        crm_object: str,
        crm_payload: dict[str, Any],
    ) -> str | None:
        """
        Attempt to find an existing record by matching on key fields.

        For Odoo:
        - company/account: match on website (domain)
        - contact: match on email
        - opportunity: match on id if present
        """
        filters: dict[str, Any] = {}

        if domain in ("company", "account"):
            if "website" in crm_payload:
                filters["website"] = crm_payload["website"]
            elif "name" in crm_payload:
                filters["name"] = crm_payload["name"]
        elif domain == "contact":
            if "email" in crm_payload:
                filters["email"] = crm_payload["email"]
        elif domain == "opportunity":
            if "id" in crm_payload:
                return str(crm_payload["id"])

        if not filters:
            return None

        # Add extra_domain filters for Odoo (e.g., is_company=True)
        extra = self.mapper.get_extra_domain(domain)
        if extra:
            for clause in extra:
                if len(clause) == 3:
                    filters[clause[0]] = clause[2]

        recs = self.client.query_records(
            crm_object, filters, fields=["id"]
        )
        if not recs:
            return None
        return str(recs[0].get("id", ""))

    def write_back(
        self,
        domain: str,
        canonical: dict[str, Any],
    ) -> WriteResult:
        """
        Write enriched canonical data back to the CRM.

        Args:
            domain: The entity domain (company, contact, opportunity, account)
            canonical: Canonical enrichment fields to write

        Returns:
            WriteResult with success/failure details
        """
        crm_object, crm_payload = self.mapper.to_crm(domain, canonical)

        if not crm_payload:
            logger.warning(
                "writeback_empty_payload",
                domain=domain,
                crm_type=self.crm_type.value,
            )
            return WriteResult(
                success=False, error="empty_payload_after_mapping"
            )

        existing_id = self._detect_existing_record(
            domain, crm_object, crm_payload
        )

        if existing_id:
            logger.info(
                "writeback_update",
                domain=domain,
                crm_type=self.crm_type.value,
                record_id=existing_id,
                field_count=len(crm_payload),
            )
            return self.client.update_record(
                crm_object, existing_id, crm_payload
            )

        logger.info(
            "writeback_create",
            domain=domain,
            crm_type=self.crm_type.value,
            field_count=len(crm_payload),
        )
        return self.client.create_record(crm_object, crm_payload)

    async def async_write_back(
        self,
        domain: str,
        canonical: dict[str, Any],
    ) -> WriteResult:
        """
        Async wrapper for write_back.

        Uses asyncio.to_thread internally via the OdooClient async methods.
        """
        import asyncio

        return await asyncio.to_thread(self.write_back, domain, canonical)
