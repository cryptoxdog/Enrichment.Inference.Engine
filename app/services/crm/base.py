"""
CRM client base classes and contracts.

Defines the abstract interface that all CRM clients (Odoo, Salesforce,
HubSpot) must implement. The enrichment engine never imports a concrete
client directly — it goes through WriteBackOrchestrator which selects
the correct implementation at runtime.

L9 Architecture Note:
    This module lives in app/services/crm/ and is chassis-agnostic.
    It never imports FastAPI, never creates routes, never touches auth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CRMType(StrEnum):
    """Supported CRM platforms."""

    ODOO = "odoo"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"


@dataclass
class CRMCredentials:
    """Credential container for CRM connections."""

    crm_type: CRMType
    credentials: dict[str, str]


@dataclass
class WriteResult:
    """Outcome of a single CRM write operation."""

    success: bool
    record_id: str = ""
    fields_written: list[str] = field(default_factory=list)
    error: str = ""


class CRMClientBase(ABC):
    """
    Abstract CRM client interface.

    Concrete implementations must handle:
    - Connection lifecycle (connect / test_connection)
    - CRUD operations (get, query, create, update, upsert)
    - Bulk operations (bulk_create, bulk_update)
    - Schema introspection (get_field_metadata)
    """

    def __init__(self, credentials: CRMCredentials) -> None:
        self.credentials = credentials

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the CRM. Returns True on success."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify the connection is still alive."""
        ...

    @abstractmethod
    def get_record(self, object_type: str, record_id: str) -> dict[str, Any] | None:
        """Fetch a single record by ID."""
        ...

    @abstractmethod
    def query_records(
        self,
        object_type: str,
        filters: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query records matching filters."""
        ...

    @abstractmethod
    def create_record(self, object_type: str, data: dict[str, Any]) -> WriteResult:
        """Create a new record."""
        ...

    @abstractmethod
    def update_record(self, object_type: str, record_id: str, data: dict[str, Any]) -> WriteResult:
        """Update an existing record."""
        ...

    @abstractmethod
    def upsert_record(
        self,
        object_type: str,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any],
    ) -> WriteResult:
        """Create or update based on external ID."""
        ...

    @abstractmethod
    def get_field_metadata(self, object_type: str) -> dict[str, Any]:
        """Return field schema metadata for a CRM object."""
        ...
