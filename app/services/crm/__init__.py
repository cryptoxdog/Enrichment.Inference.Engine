"""
CRM integration package.

Provides CRM client abstraction, Odoo XML-RPC client, field mapping,
and write-back orchestration for the enrichment engine.
"""

from .base import CRMClientBase, CRMCredentials, CRMType, WriteResult
from .field_mapper import FieldMapper
from .odoo_client import OdooClient
from .writeback import WriteBackOrchestrator

__all__ = [
    "CRMClientBase",
    "CRMCredentials",
    "CRMType",
    "FieldMapper",
    "OdooClient",
    "WriteBackOrchestrator",
    "WriteResult",
]
