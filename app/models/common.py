"""
Common model types used across the enrichment engine.

Defines shared types like FieldStatus, FieldTrace, EntityRef.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FieldStatus(StrEnum):
    """Status of a field during enrichment."""

    UNKNOWN = "unknown"
    POPULATED = "populated"
    MISSING = "missing"
    INPUTS_MISSING = "inputs_missing"
    BELOW_THRESHOLD = "below_threshold"
    INFERRED = "inferred"
    FAILED = "failed"


@dataclass
class FieldTrace:
    """
    Trace information for a field during enrichment.

    Tracks status, confidence, source, and extra metadata.
    """

    field_name: str
    status: FieldStatus = FieldStatus.UNKNOWN
    confidence: float = 0.0
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityRef:
    """Reference to an entity in a CRM system."""

    entity_id: str
    object_type: str
    tenant_id: str = ""
    domain: str = ""
