from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUTION_PATH = REPO_ROOT / "docs/contracts/node.constitution.yaml"


class PacketValidationError(ValueError):
    """Raised when a packet violates the packet envelope contract."""


class PacketPolicyError(PermissionError):
    """Raised when packet egress violates action policy constraints."""


@lru_cache(maxsize=1)
def _constitution() -> dict[str, Any]:
    result = yaml.safe_load(CONSTITUTION_PATH.read_text(encoding="utf-8"))
    return dict(result) if result else {}


def registered_actions() -> set[str]:
    return set(_constitution()["actions"].keys())


def action_policy(action_name: str) -> dict[str, Any]:
    try:
        return dict(_constitution()["actions"][action_name])
    except KeyError as exc:
        raise PacketValidationError(f"packet.action is not registered: {action_name}") from exc


def _tenant_to_string(tenant: Any) -> str:
    if isinstance(tenant, str):
        return tenant
    if isinstance(tenant, dict):
        return json.dumps(tenant, sort_keys=True, separators=(",", ":"))
    return str(tenant)


def canonical_packet_hash(action: str, payload: Mapping[str, Any], tenant: Any) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "payload": dict(payload),
            "tenant": _tenant_to_string(tenant),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_lineage(lineage: Any) -> dict[str, Any]:
    if lineage is None:
        lineage = {}
    if not isinstance(lineage, dict):
        raise PacketValidationError("lineage must be an object")

    parent_ids = lineage.get("parent_ids", [])
    if not isinstance(parent_ids, list) or not all(isinstance(item, str) for item in parent_ids):
        raise PacketValidationError("lineage.parent_ids must be a list[str]")

    generation = lineage.get("generation", 0)
    if not isinstance(generation, int) or generation < 0:
        raise PacketValidationError("lineage.generation must be a non-negative integer")

    root_id = lineage.get("root_id")
    if root_id is not None and not isinstance(root_id, str):
        raise PacketValidationError("lineage.root_id must be a string or null")

    derivation_type = lineage.get("derivation_type")
    if derivation_type is not None and not isinstance(derivation_type, str):
        raise PacketValidationError("lineage.derivation_type must be a string or null")

    return {
        "parent_ids": parent_ids,
        "root_id": root_id,
        "generation": generation,
        "derivation_type": derivation_type,
    }


def _normalize_governance(governance: Any) -> dict[str, Any]:
    if governance is None:
        return {}
    if not isinstance(governance, dict):
        raise PacketValidationError("governance must be an object")
    return dict(governance)


def _normalize_hop_trace(hop_trace: Any) -> list[dict[str, Any]]:
    if hop_trace is None:
        return []
    if not isinstance(hop_trace, list):
        raise PacketValidationError("hop_trace must be a list")

    normalized: list[dict[str, Any]] = []
    for item in hop_trace:
        if not isinstance(item, dict):
            raise PacketValidationError("hop_trace entries must be objects")
        for key in ("node", "action", "status", "timestamp"):
            if key not in item:
                raise PacketValidationError(f"hop_trace entry missing field: {key}")
            if not isinstance(item[key], str):
                raise PacketValidationError(f"hop_trace.{key} must be a string")
        normalized.append(dict(item))
    return normalized


def _normalize_delegation_chain(chain: Any) -> list[dict[str, Any]]:
    if chain is None:
        return []
    if not isinstance(chain, list):
        raise PacketValidationError("delegation_chain must be a list")

    normalized: list[dict[str, Any]] = []
    for item in chain:
        if not isinstance(item, dict):
            raise PacketValidationError("delegation_chain entries must be objects")
        normalized.append(dict(item))
    return normalized


def validate_ingress_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        raise PacketValidationError("packet must be an object")

    action = packet.get("action")
    if not isinstance(action, str) or not action:
        raise PacketValidationError("packet.action must be a non-empty string")
    if action not in registered_actions():
        raise PacketValidationError(f"packet.action is not registered: {action}")

    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise PacketValidationError("packet.payload must be an object")

    tenant = packet.get("tenant")
    if tenant is None or not isinstance(tenant, (str, dict)):
        raise PacketValidationError("packet.tenant must be a string or object")

    declared_hash = packet.get("content_hash")
    if declared_hash is not None:
        if not isinstance(declared_hash, str) or not declared_hash:
            raise PacketValidationError("packet.content_hash must be a non-empty string")
        computed_hash = canonical_packet_hash(action, payload, tenant)
        if declared_hash != computed_hash:
            raise PacketValidationError("content_hash verification failed")

    packet_id = packet.get("packet_id")
    if packet_id is not None and not isinstance(packet_id, str):
        raise PacketValidationError("packet.packet_id must be a string when present")

    reply_to = packet.get("reply_to")
    if reply_to is not None and not isinstance(reply_to, str):
        raise PacketValidationError("packet.reply_to must be a string when present")

    source_node = packet.get("source_node")
    if source_node is not None and not isinstance(source_node, str):
        raise PacketValidationError("packet.source_node must be a string when present")

    return {
        "packet_id": packet.get("packet_id"),
        "action": action,
        "payload": dict(payload),
        "tenant": tenant,
        "source_node": source_node,
        "reply_to": reply_to,
        "lineage": _normalize_lineage(packet.get("lineage")),
        "governance": _normalize_governance(packet.get("governance")),
        "hop_trace": _normalize_hop_trace(packet.get("hop_trace")),
        "delegation_chain": _normalize_delegation_chain(packet.get("delegation_chain")),
        "content_hash": declared_hash,
    }


def build_egress_packet(
    ingress_packet: Mapping[str, Any],
    result_payload: Mapping[str, Any],
    *,
    current_node: str,
    packet_type: str = "enrichment_result",
    policy_cleared: bool = False,
) -> dict[str, Any]:
    normalized_ingress = validate_ingress_packet(ingress_packet)

    if not isinstance(result_payload, Mapping):
        raise PacketValidationError("egress result_payload must be an object")

    policy = action_policy(normalized_ingress["action"])
    if policy["mutation_class"] == "external_mutation" and not policy_cleared:
        raise PacketPolicyError(
            f"action '{normalized_ingress['action']}' requires explicit policy clearance"
        )

    ingress_lineage = normalized_ingress["lineage"]
    ingress_packet_id = normalized_ingress.get("packet_id") or "unknown-ingress-packet"

    hop_trace = list(normalized_ingress["hop_trace"])
    hop_trace.append(
        {
            "node": current_node,
            "action": normalized_ingress["action"],
            "status": "completed",
            "timestamp": _utc_now_iso(),
        }
    )

    root_id = ingress_lineage["root_id"] or ingress_packet_id

    egress_packet = {
        "packet_id": str(uuid.uuid4()),
        "packet_type": packet_type,
        "action": normalized_ingress["action"],
        "payload": dict(result_payload),
        "timestamp": _utc_now_iso(),
        "address": {
            "source_node": current_node,
            "destination_node": normalized_ingress["reply_to"],
            "reply_to": current_node,
        },
        "tenant": normalized_ingress["tenant"],
        "lineage": {
            "parent_ids": [ingress_packet_id],
            "root_id": root_id,
            "generation": ingress_lineage["generation"] + 1,
            "derivation_type": ingress_lineage["derivation_type"],
        },
        "governance": normalized_ingress["governance"],
        "hop_trace": hop_trace,
        "delegation_chain": normalized_ingress["delegation_chain"],
    }

    egress_packet["content_hash"] = canonical_packet_hash(
        egress_packet["action"],
        egress_packet["payload"],
        egress_packet["tenant"],
    )
    return egress_packet
