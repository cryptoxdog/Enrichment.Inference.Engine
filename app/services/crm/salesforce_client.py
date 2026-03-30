"""
Salesforce CRM client.

Production-ready Salesforce integration with field-level security,
bulk operations, and OAuth2 authentication.

L9 Architecture Note:
    Chassis-agnostic. Implements CRMClientBase contract.
    Never imports FastAPI. Used by WriteBackOrchestrator.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import CRMClientBase, CRMCredentials, WriteResult

logger = logging.getLogger(__name__)


class SalesforceClient(CRMClientBase):
    """Salesforce CRM client with REST API integration."""

    def __init__(self, credentials: CRMCredentials) -> None:
        super().__init__(credentials)
        self._instance_url: str = ""
        self._access_token: str = ""
        self._api_version: str = credentials.credentials.get("api_version", "v59.0")

    def connect(self) -> bool:
        """Authenticate via OAuth2 password flow or JWT."""
        creds = self.credentials.credentials
        token_url = creds.get("token_url", "https://login.salesforce.com/services/oauth2/token")

        grant_type = creds.get("grant_type", "password")
        body: dict[str, str] = {
            "grant_type": grant_type,
            "client_id": creds.get("client_id", ""),
            "client_secret": creds.get("client_secret", ""),
        }

        if grant_type == "password":
            body["username"] = creds.get("username", "")
            body["password"] = creds.get("password", "") + creds.get("security_token", "")

        try:
            resp = httpx.post(token_url, data=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self._instance_url = data["instance_url"]
            self._access_token = data["access_token"]
            logger.info("Salesforce connected: %s", self._instance_url)
            return True
        except Exception as exc:
            logger.error("Salesforce connect failed: %s", exc)
            return False

    def test_connection(self) -> bool:
        """Verify the connection by querying limits."""
        if not self._access_token:
            return False
        try:
            resp = httpx.get(
                f"{self._instance_url}/services/data/{self._api_version}/limits",
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_record(self, object_type: str, record_id: str) -> dict[str, Any] | None:
        """Fetch a single Salesforce record by ID."""
        url = (
            f"{self._instance_url}/services/data/{self._api_version}"
            f"/sobjects/{object_type}/{record_id}"
        )
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=15)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("SF get_record error: %s", exc)
            return None

    def query_records(
        self,
        object_type: str,
        filters: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SOQL query."""
        field_list = ", ".join(fields) if fields else "Id, Name"
        where_parts = [f"{k} = '{v}'" for k, v in filters.items()]
        where_clause = " AND ".join(where_parts) if where_parts else "Id != null"
        soql = f"SELECT {field_list} FROM {object_type} WHERE {where_clause}"

        url = f"{self._instance_url}/services/data/{self._api_version}/query"
        try:
            resp = httpx.get(url, params={"q": soql}, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json().get("records", [])
        except Exception as exc:
            logger.error("SF query error: %s", exc)
            return []

    def create_record(self, object_type: str, data: dict[str, Any]) -> WriteResult:
        """Create a new Salesforce record."""
        url = f"{self._instance_url}/services/data/{self._api_version}/sobjects/{object_type}"
        try:
            resp = httpx.post(url, json=data, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            result = resp.json()
            return WriteResult(
                success=result.get("success", False),
                record_id=result.get("id", ""),
                fields_written=list(data.keys()),
            )
        except Exception as exc:
            return WriteResult(success=False, error=str(exc))

    def update_record(self, object_type: str, record_id: str, data: dict[str, Any]) -> WriteResult:
        """Update an existing Salesforce record."""
        url = (
            f"{self._instance_url}/services/data/{self._api_version}"
            f"/sobjects/{object_type}/{record_id}"
        )
        try:
            resp = httpx.patch(url, json=data, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return WriteResult(
                success=True,
                record_id=record_id,
                fields_written=list(data.keys()),
            )
        except Exception as exc:
            return WriteResult(success=False, error=str(exc))

    def upsert_record(
        self,
        object_type: str,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any],
    ) -> WriteResult:
        """Upsert a record using an external ID field."""
        url = (
            f"{self._instance_url}/services/data/{self._api_version}"
            f"/sobjects/{object_type}/{external_id_field}/{external_id_value}"
        )
        try:
            resp = httpx.patch(url, json=data, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            record_id = ""
            if resp.status_code == 201:
                record_id = resp.json().get("id", "")
            return WriteResult(
                success=True,
                record_id=record_id,
                fields_written=list(data.keys()),
            )
        except Exception as exc:
            return WriteResult(success=False, error=str(exc))

    def bulk_create(self, object_type: str, records: list[dict[str, Any]]) -> list[WriteResult]:
        """Create multiple records using Salesforce Composite API."""
        url = f"{self._instance_url}/services/data/{self._api_version}/composite/sobjects"
        payload = {
            "allOrNone": False,
            "records": [{"attributes": {"type": object_type}, **rec} for rec in records],
        }
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            results = resp.json()
            return [
                WriteResult(
                    success=r.get("success", False),
                    record_id=r.get("id", ""),
                    fields_written=list(records[i].keys()) if r.get("success") else [],
                    error=str(r.get("errors", "")) if not r.get("success") else "",
                )
                for i, r in enumerate(results)
            ]
        except Exception as exc:
            return [WriteResult(success=False, error=str(exc))] * len(records)

    def bulk_update(self, object_type: str, records: list[dict[str, Any]]) -> list[WriteResult]:
        """Update multiple records using Salesforce Composite API."""
        url = f"{self._instance_url}/services/data/{self._api_version}/composite/sobjects"
        payload = {
            "allOrNone": False,
            "records": [{"attributes": {"type": object_type}, **rec} for rec in records],
        }
        try:
            resp = httpx.patch(url, json=payload, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            results = resp.json()
            return [
                WriteResult(
                    success=r.get("success", False),
                    record_id=r.get("id", ""),
                    fields_written=list(records[i].keys()) if r.get("success") else [],
                    error=str(r.get("errors", "")) if not r.get("success") else "",
                )
                for i, r in enumerate(results)
            ]
        except Exception as exc:
            return [WriteResult(success=False, error=str(exc))] * len(records)

    def get_field_metadata(self, object_type: str) -> dict[str, Any]:
        """Return field schema metadata for a Salesforce object."""
        url = (
            f"{self._instance_url}/services/data/{self._api_version}"
            f"/sobjects/{object_type}/describe"
        )
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            describe = resp.json()
            return {
                f["name"]: {
                    "type": f["type"],
                    "label": f["label"],
                    "updateable": f["updateable"],
                    "createable": f["createable"],
                    "nillable": f["nillable"],
                    "length": f.get("length"),
                }
                for f in describe.get("fields", [])
            }
        except Exception as exc:
            logger.error("SF metadata error: %s", exc)
            return {}

    def _headers(self) -> dict[str, str]:
        """Build authorization headers."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
