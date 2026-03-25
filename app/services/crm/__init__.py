"""
CRM integration package.

Provides CRM client abstraction, field mapping, and write-back
orchestration for the enrichment engine.

Available clients:
- OdooClient: Odoo XML-RPC integration (first consumer)
- SalesforceClient: Salesforce REST API integration
- HubSpotClient: HubSpot CRM v3 API integration
"""

from .base import CRMClientBase, CRMCredentials, CRMType, WriteResult
from .field_mapper import FieldMapper
from .hubspot_client import HubSpotClient
from .odoo_client import OdooClient
from .salesforce_client import SalesforceClient
from .writeback import WriteBackOrchestrator

# Client registry — maps CRMType to implementation
CLIENT_REGISTRY: dict[CRMType, type[CRMClientBase]] = {
    CRMType.ODOO: OdooClient,
    CRMType.SALESFORCE: SalesforceClient,
    CRMType.HUBSPOT: HubSpotClient,
}

__all__ = [
    "CLIENT_REGISTRY",
    "CRMClientBase",
    "CRMCredentials",
    "CRMType",
    "FieldMapper",
    "HubSpotClient",
    "OdooClient",
    "SalesforceClient",
    "WriteBackOrchestrator",
    "WriteResult",
]
