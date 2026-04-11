"""
TransportPacket contract enforcement for Gate-routed inter-node communication.

The function names are preserved to avoid a broad call-site rewrite, but the
underlying contract is the SDK `TransportPacket`.
"""

from __future__ import annotations

import logging
from typing import Any

from constellation_node_sdk.transport import TransportPacket, create_transport_packet

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


_ACTION_ALIASES = {
    "admin_command": "admin-command",
    "community_export": "community-export",
    "enrich_request": "enrich-request",
    "enrich_result": "enrich-result",
    "graph_inference_result": "graph-inference-result",
    "graph_sync": "graph-sync",
    "health_check": "health-check",
    "inference_result": "inference-result",
    "schema_proposal": "schema-proposal",
}

_ALLOWED_ACTIONS: frozenset[str] = frozenset(_ACTION_ALIASES.values())


# Required fields per packet type
_REQUIRED_PAYLOAD_FIELDS: dict[str, list[str]] = {
    "admin-command": ["subaction"],
    "community-export": ["communities"],
    "enrich-request": ["entity_id"],
    "enrich-result": ["entity_id", "enriched_fields"],
    "graph-inference-result": ["inference_outputs"],
    "graph-sync": ["entity_type", "batch"],
    "health-check": [],
    "inference-result": ["inference_outputs"],
    "schema-proposal": ["proposed_fields"],
}


def enforce_packet_envelope(
    packet: Any,
    *,
    expected_type: str,
) -> TransportPacket:
    """
    Validate that `packet` is a well-formed TransportPacket of `expected_type`.
    """
    if not isinstance(packet, TransportPacket):
        raise ContractViolationError(f"Expected a TransportPacket, got {type(packet).__name__}")

    normalized_type = _normalize_action(expected_type)
    packet_id = str(packet.header.packet_id)
    actual_action = packet.header.action

    if normalized_type not in _ALLOWED_ACTIONS:
        raise ContractViolationError(
            f"action={normalized_type!r} is not in the allowed set",
            packet_id=packet_id,
        )

    if actual_action != normalized_type:
        raise ContractViolationError(
            f"action mismatch: expected={normalized_type!r} got={actual_action!r}",
            packet_id=packet_id,
        )

    required = _REQUIRED_PAYLOAD_FIELDS.get(normalized_type, [])
    for field_name in required:
        if field_name not in packet.payload or packet.payload[field_name] is None:
            raise ContractViolationError(
                f"Missing or null required field '{field_name}' for action={normalized_type!r}",
                packet_id=packet_id,
            )

    return packet


def build_graph_sync_packet(
    *,
    tenant_id: str,
    entity_type: str,
    batch: list[dict[str, Any]],
) -> TransportPacket:
    """Build a contract-compliant graph-sync TransportPacket for sending to Gate."""
    packet = create_transport_packet(
        action="graph-sync",
        payload={"entity_type": entity_type, "batch": batch},
        tenant=tenant_id,
        source_node="enrichment-engine",
        destination_node="gate",
        reply_to="enrichment-engine",
        classification="internal",
        compliance_tags=("GRAPH_SYNC",),
    )
    enforce_packet_envelope(packet, expected_type="graph_sync")
    return packet


def build_schema_proposal_packet(
    *,
    tenant_id: str,
    proposed_fields: list[dict[str, Any]],
    provenance: str = "schema_discovery",
) -> TransportPacket:
    """Build a contract-compliant schema-proposal TransportPacket."""
    packet = create_transport_packet(
        action="schema-proposal",
        payload={"proposed_fields": proposed_fields, "provenance": provenance},
        tenant=tenant_id,
        source_node="enrichment-engine",
        destination_node="gate",
        reply_to="enrichment-engine",
        classification="internal",
        compliance_tags=("SCHEMA_EVOLUTION",),
    )
    enforce_packet_envelope(packet, expected_type="schema_proposal")
    return packet


def build_enrich_result_packet(
    *,
    tenant_id: str,
    entity_id: str,
    enriched_fields: dict[str, Any],
    confidence: float,
    pass_count: int,
) -> TransportPacket:
    """Build a contract-compliant enrich-result TransportPacket."""
    packet = create_transport_packet(
        action="enrich-result",
        payload={
            "entity_id": entity_id,
            "enriched_fields": enriched_fields,
            "confidence": confidence,
            "pass_count": pass_count,
        },
        tenant=tenant_id,
        source_node="enrichment-engine",
        destination_node="gate",
        reply_to="enrichment-engine",
        classification="internal",
        compliance_tags=("ENRICH_RESULT",),
    )
    enforce_packet_envelope(packet, expected_type="enrich_result")
    return packet


def _normalize_action(name: str) -> str:
    normalized = name.strip().lower()
    return _ACTION_ALIASES.get(normalized, normalized.replace("_", "-"))
