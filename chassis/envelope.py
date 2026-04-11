"""
chassis/envelope.py
Self-contained transport wire envelope inflate/deflate for the chassis router (dict-shaped payloads; SDK uses `TransportPacket` for Gate I/O).

Intentionally imports NOTHING from app/ — the chassis is a standalone library.
Engine-side orchestration lives under `app/engines/` and `app/services/chassis_handlers.py`; this module is the HTTP-free inflate/deflate primitive used by `chassis/router.py`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any


def inflate_ingress(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and canonicalise an inbound raw dict into an envelope.

    Validates: action present, payload is dict, content_hash (if supplied).
    Returns a dict guaranteed to have: packet_id, action, tenant.actor,
    payload, content_hash, lineage, governance, hop_trace.
    """
    action = raw.get("action")
    if not action:
        raise ValueError("Missing required field: action")

    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Missing or invalid field: payload (must be a dict)")

    tenant_raw = raw.get("tenant", "unknown")
    tenant_str = tenant_raw if isinstance(tenant_raw, str) else tenant_raw.get("actor", "unknown")

    computed_hash = _compute_hash(action, payload, tenant_str)
    provided_hash = raw.get("content_hash")
    if provided_hash and provided_hash != computed_hash:
        raise ValueError("content_hash verification failed: payload may be tampered")

    packet_id = str(uuid.uuid4())
    now = datetime.now(tz=UTC).isoformat()

    return {
        "packet_id": packet_id,
        "packet_type": "enrichment_request",
        "action": action,
        "payload": payload,
        "timestamp": now,
        "content_hash": computed_hash,
        "address": {
            "source_node": raw.get("source_node", "unknown"),
            "destination_node": "enrichment-engine",
            "reply_to": raw.get("reply_to", raw.get("source_node", "unknown")),
        },
        "tenant": {
            "actor": tenant_str,
            "on_behalf_of": raw.get("on_behalf_of", tenant_str),
            "originator": raw.get("originator", tenant_str),
            "org_id": raw.get("org_id", tenant_str),
            "user_id": raw.get("user_id"),
        },
        "lineage": raw.get(
            "lineage",
            {
                "parent_ids": [],
                "root_id": packet_id,
                "generation": 0,
                "derivation_type": "origin",
            },
        ),
        "governance": raw.get(
            "governance",
            {
                "intent": action,
                "audit_required": False,
                "compliance_tags": [],
            },
        ),
        "hop_trace": [
            {
                "node": "enrichment-engine",
                "action": "receive",
                "status": "received",
                "timestamp": now,
            }
        ],
        "delegation_chain": raw.get("delegation_chain", []),
    }


def deflate_egress(envelope: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
    """
    Wrap an engine response into a wire-format result envelope.
    Increments lineage.generation, appends hop_trace respond entry.
    """
    now = datetime.now(tz=UTC).isoformat()

    lineage = dict(envelope.get("lineage", {}))
    lineage["parent_ids"] = [envelope["packet_id"]]
    lineage["generation"] = lineage.get("generation", 0) + 1

    hop_trace = list(envelope.get("hop_trace", []))
    hop_trace.append(
        {
            "node": "enrichment-engine",
            "action": "respond",
            "status": "ok",
            "timestamp": now,
        }
    )

    return {
        "packet_id": str(uuid.uuid4()),
        "packet_type": "enrichment_result",
        "action": envelope["action"],
        "payload": response_data,
        "timestamp": now,
        "content_hash": _compute_hash(
            envelope["action"],
            response_data,
            envelope["tenant"]["actor"],
        ),
        "address": {
            "source_node": "enrichment-engine",
            "destination_node": envelope["address"].get("reply_to", "unknown"),
            "reply_to": "enrichment-engine",
        },
        "tenant": envelope["tenant"],
        "lineage": lineage,
        "governance": envelope.get("governance", {}),
        "hop_trace": hop_trace,
        "delegation_chain": envelope.get("delegation_chain", []),
    }


def _compute_hash(action: str, payload: dict, tenant: str) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload, "tenant": tenant},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
