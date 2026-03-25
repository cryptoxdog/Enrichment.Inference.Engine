"""
Chassis Contract — inflate/deflate PacketEnvelope at the boundary.

This is the enrichment engine's implementation of the L9 chassis contract.
Every L9 constellation node implements this same interface:
    inflate_ingress: raw HTTP dict → PacketEnvelope-compatible structure
    deflate_egress:  engine response → wire-format dict
    delegate_to_node: create derived packet for inter-node delegation

The enrichment engine never touches raw HTTP directly.
It only sees (tenant, payload) from the chassis router.

PacketEnvelope alignment:
    - packettype: "enrichment_request" | "enrichment_result"
    - action: "enrich" | "enrichbatch" | "converge" | "discover" | "writeback"
    - address.sourcenode: "enrichment-engine"
    - contenthash: SHA-256 of canonical payload
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def inflate_ingress(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Parse incoming JSON into a validated envelope structure.

    Validates:
    - Required fields: action, payload
    - content_hash integrity (if provided)
    - Tenant context extraction
    """
    action = raw.get("action")
    if not action:
        raise ValueError("Missing required field: action")

    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Missing or invalid field: payload")

    # Extract or resolve tenant
    tenant = raw.get("tenant", "unknown")

    # Verify content_hash if present
    provided_hash = raw.get("content_hash")
    if provided_hash:
        computed = _compute_hash(action, payload, tenant)
        if computed != provided_hash:
            raise ValueError("content_hash verification failed: payload tampered")

    # Build canonical envelope
    packet_id = str(uuid.uuid4())
    envelope = {
        "packet_id": packet_id,
        "packet_type": "enrichment_request",
        "action": action,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "address": {
            "source_node": raw.get("source_node", "unknown"),
            "destination_node": "enrichment-engine",
            "reply_to": raw.get("reply_to", raw.get("source_node", "unknown")),
        },
        "tenant": {
            "actor": tenant,
            "on_behalf_of": raw.get("on_behalf_of", tenant),
            "originator": raw.get("originator", tenant),
            "org_id": raw.get("org_id", tenant),
            "user_id": raw.get("user_id"),
        },
        "content_hash": _compute_hash(action, payload, tenant),
        "lineage": raw.get(
            "lineage",
            {
                "parent_ids": [],
                "derivation_type": "api_request",
                "generation": 0,
            },
        ),
        "governance": {
            "intent": raw.get("intent", action),
            "compliance_tags": raw.get("compliance_tags", []),
            "audit_required": raw.get("audit_required", False),
        },
    }

    # Propagate delegation_chain if present
    if "delegation_chain" in raw:
        envelope["delegation_chain"] = raw["delegation_chain"]

    # Propagate hop_trace
    envelope["hop_trace"] = raw.get("hop_trace", [])
    envelope["hop_trace"].append(
        {
            "node": "enrichment-engine",
            "action": "receive",
            "status": "received",
            "timestamp": envelope["timestamp"],
        }
    )

    return envelope


def deflate_egress(
    envelope: dict[str, Any],
    response_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Wrap engine response into wire-format dict for HTTP response.

    Creates a derived response envelope with:
    - packet_type: "enrichment_result"
    - lineage pointing back to the request packet
    - Updated hop_trace
    - New content_hash over response payload
    """
    response_packet_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Compute response hash
    action = envelope.get("action", "enrich")
    tenant = envelope.get("tenant", {}).get("actor", "unknown")
    response_hash = _compute_hash(action, response_data, tenant)

    result = {
        "packet_id": response_packet_id,
        "packet_type": "enrichment_result",
        "action": action,
        "payload": response_data,
        "timestamp": timestamp,
        "address": {
            "source_node": "enrichment-engine",
            "destination_node": envelope.get("address", {}).get("reply_to", "unknown"),
        },
        "tenant": envelope.get("tenant", {}),
        "content_hash": response_hash,
        "lineage": {
            "parent_ids": [envelope.get("packet_id", "")],
            "derivation_type": "enrichment",
            "generation": envelope.get("lineage", {}).get("generation", 0) + 1,
            "root_id": envelope.get("lineage", {}).get("root_id", envelope.get("packet_id", "")),
        },
    }

    # Update hop_trace
    hop_trace = list(envelope.get("hop_trace", []))
    hop_trace.append(
        {
            "node": "enrichment-engine",
            "action": "respond",
            "status": "completed",
            "timestamp": timestamp,
        }
    )
    result["hop_trace"] = hop_trace

    return result


def delegate_to_node(
    envelope: dict[str, Any],
    target_node: str,
    permissions: list[str],
) -> dict[str, Any]:
    """
    Create a derived packet addressed to another constellation node.

    Appends a DelegationLink and hop entry. Sets audit_required=True.
    Used when enrichment needs to call graph-service for sync/match.
    """
    derived_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    derived = {
        **envelope,
        "packet_id": derived_id,
        "timestamp": timestamp,
        "address": {
            "source_node": "enrichment-engine",
            "destination_node": target_node,
            "reply_to": "enrichment-engine",
        },
        "lineage": {
            "parent_ids": [envelope.get("packet_id", "")],
            "derivation_type": "delegation",
            "generation": envelope.get("lineage", {}).get("generation", 0) + 1,
            "root_id": envelope.get("lineage", {}).get("root_id", envelope.get("packet_id", "")),
        },
    }

    # Append delegation link
    chain = list(envelope.get("delegation_chain", []))
    chain.append(
        {
            "delegator": "enrichment-engine",
            "delegatee": target_node,
            "scope": permissions,
            "timestamp": timestamp,
        }
    )
    derived["delegation_chain"] = chain

    # Append hop entry
    hop_trace = list(envelope.get("hop_trace", []))
    hop_trace.append(
        {
            "node": "enrichment-engine",
            "action": "delegate",
            "status": "delegated",
            "timestamp": timestamp,
            "target": target_node,
        }
    )
    derived["hop_trace"] = hop_trace

    # Force audit
    gov = dict(derived.get("governance", {}))
    gov["audit_required"] = True
    derived["governance"] = gov

    # Recompute hash
    derived["content_hash"] = _compute_hash(
        derived.get("action", ""),
        derived.get("payload", {}),
        derived.get("tenant", {}).get("actor", "unknown"),
    )

    return derived


def _compute_hash(action: str, payload: dict, tenant: str) -> str:
    """SHA-256 of canonical JSON (sorted keys, deterministic)."""
    hash_input = json.dumps(
        {"action": action, "payload": payload, "tenant": tenant},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()
