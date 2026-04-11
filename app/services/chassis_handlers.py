"""
Chassis handler registration for L9 inter-node communication.

This module registers handlers for PacketEnvelope types received via
the chassis router (/v1/execute). All inter-node communication flows
through these handlers rather than direct HTTP calls.

Usage at app startup:
    from app.services.chassis_handlers import register_all_handlers
    register_all_handlers()
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Handler registry - maps action names to handler functions
_HANDLERS: dict[str, Any] = {}


def register_handler(action: str, handler) -> None:
    """Register a handler function for an action type."""
    _HANDLERS[action] = handler
    logger.debug("Registered chassis handler: %s", action)


def get_handler(action: str):
    """Get the handler for an action type."""
    return _HANDLERS.get(action)


def list_handlers() -> list[str]:
    """List all registered handler action names."""
    return sorted(_HANDLERS.keys())


async def handle_graph_inference_result(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Handle graph_inference_result packets from GRAPH node.
    
    These contain inference outputs (e.g., community labels, derived fields)
    that should be injected into the ENRICH convergence loop.
    """
    from .graph_return_channel import (
        GraphReturnChannel,
        GraphInferenceResultEnvelope,
    )
    
    envelope = GraphInferenceResultEnvelope(
        packet_id=payload.get("packet_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        inference_outputs=payload.get("inference_outputs", []),
        content_hash=payload.get("content_hash", ""),
        envelope_hash=payload.get("envelope_hash", ""),
    )
    
    channel = GraphReturnChannel.get_instance()
    count = await channel.submit(envelope)
    
    return {
        "status": "accepted",
        "targets_queued": count,
        "packet_id": envelope.packet_id,
    }


async def handle_community_export(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Handle community_export packets from GRAPH node.
    
    These contain Louvain community labels to be injected as
    enrichment targets for re-enrichment passes.
    """
    from .graph_return_channel import (
        GraphReturnChannel,
        build_graph_inference_result_envelope,
    )
    
    tenant_id = payload.get("tenant_id", "")
    communities = payload.get("communities", [])
    
    if not communities:
        return {"status": "ok", "targets_queued": 0}
    
    # Convert community labels to inference outputs
    inference_outputs = [
        {
            "entity_id": c.get("entity_id"),
            "field": "community_id",
            "value": c.get("community_id"),
            "confidence": 0.95,  # Louvain is deterministic
            "rule": "louvain_community_detection",
        }
        for c in communities
        if c.get("entity_id") and c.get("community_id") is not None
    ]
    
    if not inference_outputs:
        return {"status": "ok", "targets_queued": 0}
    
    envelope = build_graph_inference_result_envelope(
        tenant_id=tenant_id,
        inference_outputs=inference_outputs,
    )
    
    channel = GraphReturnChannel.get_instance()
    count = await channel.submit(envelope)
    
    return {
        "status": "accepted",
        "targets_queued": count,
        "packet_id": envelope.packet_id,
    }


async def handle_schema_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Handle schema_proposal packets.
    
    These contain proposed field additions from schema discovery
    that should be reviewed and potentially added to the domain schema.
    """
    from .contract_enforcement import enforce_packet_envelope
    
    # Validate the packet
    enforce_packet_envelope(payload, expected_type="schema_proposal")
    
    tenant_id = payload.get("tenant_id", "")
    proposed_fields = payload.get("proposed_fields", [])
    
    logger.info(
        "Received schema_proposal for tenant=%s with %d fields",
        tenant_id,
        len(proposed_fields),
    )
    
    # In production, this would queue for review or auto-apply
    # For now, just acknowledge receipt
    return {
        "status": "received",
        "tenant_id": tenant_id,
        "field_count": len(proposed_fields),
        "packet_id": payload.get("packet_id"),
    }


def register_all_handlers() -> None:
    """
    Register all chassis handlers.
    Call this at application startup.
    """
    register_handler("graph_inference_result", handle_graph_inference_result)
    register_handler("community_export", handle_community_export)
    register_handler("schema_proposal", handle_schema_proposal)
    
    logger.info("Registered %d chassis handlers: %s", len(_HANDLERS), list_handlers())
