"""
PacketEnvelope contract enforcement for L9 chassis communication.

All inter-node data flows must pass through enforce_packet_envelope() before
processing. This ensures content_hash, envelope_hash, and required fields are
validated - no silent bypass paths.

Usage:
    from app.services.contract_enforcement import enforce_packet_envelope, ContractViolationError

    # Validate incoming packet
    envelope = enforce_packet_envelope(raw_payload, expected_type="enrich_request")

    # Build outbound packets
    packet = build_graph_sync_packet(tenant_id="acme", entity_type="Account", batch=[...])
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class ContractViolationError(RuntimeError):
    """Raised when an inter-service packet fails contract validation.

    This is an EXPLICIT HARD FAILURE — never caught and silently swallowed.
    Callers must fix the packet, not catch this error.
    """

    def __init__(self, reason: str, *, packet_id: str | None = None) -> None:
        self.reason = reason
        self.packet_id = packet_id
        msg = f"ContractViolation[{packet_id or 'unknown'}]: {reason}"
        super().__init__(msg)
        logger.error(msg)


# Allowed packet types for L9 ENRICH node
_ALLOWED_PACKET_TYPES: frozenset[str] = frozenset([
    "enrich_request",
    "enrich_result",
    "inference_result",
    "graph_sync",
    "graph_inference_result",
    "schema_proposal",
    "community_export",
    "health_check",
    "admin_command",
])


# Required fields per packet type
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "enrich_request": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_id"],
    "enrich_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_id", "enriched_fields"],
    "inference_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "inference_outputs"],
    "graph_sync": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_type", "batch"],
    "graph_inference_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "inference_outputs"],
    "schema_proposal": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "proposed_fields"],
    "community_export": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "communities"],
    "health_check": ["packet_id", "tenant_id"],
    "admin_command": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "subaction"],
}


def enforce_packet_envelope(
    packet: Any,
    *,
    expected_type: str,
) -> dict[str, Any]:
    """
    Validate that `packet` is a well-formed PacketEnvelope of `expected_type`.

    Checks:
      1. packet is a dict (or Pydantic model with .model_dump())
      2. packet_type matches expected_type
      3. packet_type is in _ALLOWED_PACKET_TYPES
      4. All required fields for the type are present
      5. content_hash matches SHA-256 of the canonical content payload
      6. envelope_hash is present and non-empty

    Returns the validated dict.
    Raises ContractViolationError on ANY failure — no silent returns.
    """
    if hasattr(packet, "model_dump"):
        packet = packet.model_dump(mode="python")
    if not isinstance(packet, dict):
        raise ContractViolationError(
            f"Expected a dict or Pydantic model, got {type(packet).__name__}",
        )

    packet_id = packet.get("packet_id", "<no_id>")

    actual_type = packet.get("packet_type") or packet.get("type")
    if actual_type != expected_type:
        raise ContractViolationError(
            f"packet_type mismatch: expected={expected_type!r} got={actual_type!r}",
            packet_id=packet_id,
        )

    if expected_type not in _ALLOWED_PACKET_TYPES:
        raise ContractViolationError(
            f"packet_type={expected_type!r} is not in the allowed set",
            packet_id=packet_id,
        )

    required = _REQUIRED_FIELDS.get(expected_type, [])
    for field_name in required:
        if field_name not in packet or packet[field_name] is None:
            raise ContractViolationError(
                f"Missing or null required field '{field_name}' for type={expected_type!r}",
                packet_id=packet_id,
            )

    if "content_hash" in required:
        _verify_content_hash(packet, expected_type, packet_id)

    if "envelope_hash" in required:
        if not packet.get("envelope_hash"):
            raise ContractViolationError(
                "envelope_hash is empty",
                packet_id=packet_id,
            )

    return packet


def _verify_content_hash(
    packet: dict[str, Any],
    packet_type: str,
    packet_id: str,
) -> None:
    """Recompute SHA-256 over the canonical content payload and compare."""
    _HASH_EXCLUDED = {
        "content_hash", "envelope_hash", "packet_id", "packet_type",
        "type", "created_at", "lineage", "tenant_context"
    }
    content_payload = {k: v for k, v in packet.items() if k not in _HASH_EXCLUDED}
    try:
        payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    except (TypeError, ValueError) as exc:
        raise ContractViolationError(
            f"Cannot serialize content payload for hash verification: {exc}",
            packet_id=packet_id,
        ) from exc

    expected_hash = hashlib.sha256(payload_bytes).hexdigest()
    actual_hash = packet.get("content_hash", "")
    if expected_hash != actual_hash:
        raise ContractViolationError(
            f"content_hash mismatch: expected={expected_hash!r} got={actual_hash!r}",
            packet_id=packet_id,
        )


def build_graph_sync_packet(
    *,
    tenant_id: str,
    entity_type: str,
    batch: list[dict[str, Any]],
    tenant_context: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a contract-compliant graph_sync PacketEnvelope for sending to GRAPH node."""
    content_payload: dict[str, Any] = {
        "entity_type": entity_type,
        "batch": batch,
    }
    if tenant_context:
        content_payload["tenant_context"] = tenant_context

    payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()

    packet_id = f"gs_{uuid.uuid4().hex}"
    envelope_meta = {"packet_id": packet_id, "tenant_id": tenant_id, "content_hash": content_hash}
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_meta, sort_keys=True).encode()
    ).hexdigest()

    packet = {
        "packet_id": packet_id,
        "packet_type": "graph_sync",
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "batch": batch,
        "content_hash": content_hash,
        "envelope_hash": envelope_hash,
        "created_at": time.time(),
    }
    if tenant_context:
        packet["tenant_context"] = tenant_context
    if lineage:
        packet["lineage"] = lineage

    enforce_packet_envelope(packet, expected_type="graph_sync")
    return packet


def build_schema_proposal_packet(
    *,
    tenant_id: str,
    proposed_fields: list[dict[str, Any]],
    provenance: str = "schema_discovery",
) -> dict[str, Any]:
    """Build a contract-compliant schema_proposal PacketEnvelope."""
    content_payload: dict[str, Any] = {
        "proposed_fields": proposed_fields,
        "provenance": provenance,
    }
    payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()
    packet_id = f"sp_{uuid.uuid4().hex}"
    envelope_meta = {"packet_id": packet_id, "tenant_id": tenant_id, "content_hash": content_hash}
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_meta, sort_keys=True).encode()
    ).hexdigest()

    packet = {
        "packet_id": packet_id,
        "packet_type": "schema_proposal",
        "tenant_id": tenant_id,
        "proposed_fields": proposed_fields,
        "provenance": provenance,
        "content_hash": content_hash,
        "envelope_hash": envelope_hash,
        "created_at": time.time(),
    }
    enforce_packet_envelope(packet, expected_type="schema_proposal")
    return packet


def build_enrich_result_packet(
    *,
    tenant_id: str,
    entity_id: str,
    enriched_fields: dict[str, Any],
    confidence: float,
    pass_count: int,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a contract-compliant enrich_result PacketEnvelope."""
    content_payload: dict[str, Any] = {
        "entity_id": entity_id,
        "enriched_fields": enriched_fields,
        "confidence": confidence,
        "pass_count": pass_count,
    }
    payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()
    packet_id = f"er_{uuid.uuid4().hex}"
    envelope_meta = {"packet_id": packet_id, "tenant_id": tenant_id, "content_hash": content_hash}
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_meta, sort_keys=True).encode()
    ).hexdigest()

    packet = {
        "packet_id": packet_id,
        "packet_type": "enrich_result",
        "tenant_id": tenant_id,
        "entity_id": entity_id,
        "enriched_fields": enriched_fields,
        "confidence": confidence,
        "pass_count": pass_count,
        "content_hash": content_hash,
        "envelope_hash": envelope_hash,
        "created_at": time.time(),
    }
    if lineage:
        packet["lineage"] = lineage

    enforce_packet_envelope(packet, expected_type="enrich_result")
    return packet
