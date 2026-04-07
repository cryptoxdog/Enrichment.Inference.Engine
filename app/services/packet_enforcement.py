from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUTION_PATH = REPO_ROOT / "docs/contracts/node.constitution.yaml"


class PacketValidationError(ValueError):
    """Raised when an ingress packet violates the PacketEnvelope contract."""


class PacketPolicyError(PermissionError):
    """Raised when a packet violates action policy or governance requirements."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _constitution() -> dict[str, Any]:
    return _load_yaml(CONSTITUTION_PATH)


def _tenant_to_hashable_string(tenant: Any) -> str:
    if isinstance(tenant, str):
        return tenant
    if isinstance(tenant, dict):
        if "actor" in tenant:
            return str(tenant["actor"])
        return json.dumps(tenant, sort_keys=True, separators=(",", ":"))
    return str(tenant)


def canonical_packet_hash(action: str, payload: Mapping[str, Any], tenant: Any) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "payload": payload,
            "tenant": _tenant_to_hashable_string(tenant),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def registered_actions() -> set[str]:
    return set(_constitution()["actions"].keys())


def action_policy(action: str) -> dict[str, Any]:
    try:
        return _constitution()["actions"][action]
    except KeyError as exc:
        raise PacketValidationError(f"unregistered action: {action}") from exc


def _normalize_lineage(lineage: Any) -> dict[str, Any]:
    if lineage is None:
        return {
            "parent_ids": [],
            "root_id": None,
            "generation": 0,
            "derivation_type": None,
        }
    if not isinstance(lineage, dict):
        raise PacketValidationError("lineage must be an object")
    return {
        "parent_ids": list(lineage.get("parent_ids", [])),
        "root_id": lineage.get("root_id"),
        "generation": int(lineage.get("generation", 0)),
        "derivation_type": lineage.get("derivation_type"),
    }


def _normalize_hop_trace(hop_trace: Any) -> list[dict[str, Any]]:
    if hop_trace is None:
        return []
    if not isinstance(hop_trace, list):
        raise PacketValidationError("hop_trace must be a list")
    normalized: list[dict[str, Any]] = []
    for item in hop_trace:
        if not isinstance(item, dict):
            raise PacketValidationError("each hop_trace entry must be an object")
        normalized.append(dict(item))
    return normalized


def validate_ingress_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        raise PacketValidationError("packet must be an object")

    action = packet.get("action")
    if not isinstance(action, str) or not action:
        raise PacketValidationError("missing required field: action")

    if action not in registered_actions():
        raise PacketValidationError(f"unregistered action: {action}")

    payload = packet.get("payload")
    if not isinstance(payload, Mapping):
        raise PacketValidationError("payload must be an object")

    tenant = packet.get("tenant", "unknown")
    declared_hash = packet.get("content_hash")
    if declared_hash is not None:
        expected_hash = canonical_packet_hash(action, payload, tenant)
        if declared_hash != expected_hash:
            raise PacketValidationError("content_hash verification failed")

    lineage = _normalize_lineage(packet.get("lineage"))
    hop_trace = _normalize_hop_trace(packet.get("hop_trace"))

    return {
        **dict(packet),
        "action": action,
        "payload": dict(payload),
        "tenant": tenant,
        "lineage": lineage,
        "hop_trace": hop_trace,
        "delegation_chain": list(packet.get("delegation_chain", [])),
    }


def enforce_action_policy(
    packet: Mapping[str, Any],
    *,
    policy_cleared: bool = False,
) -> None:
    action = str(packet["action"])
    policy = action_policy(action)

    if action == "writeback" and not policy_cleared:
        raise PacketPolicyError(
            "writeback requires threshold_or_human approval before execution"
        )

    approval_mode = policy.get("approval_mode")
    if approval_mode == "threshold_or_human" and not policy_cleared:
        raise PacketPolicyError(
            f"{action} requires {approval_mode} approval before execution"
        )


def build_egress_packet(
    ingress_packet: Mapping[str, Any],
    result_payload: Mapping[str, Any],
    *,
    source_node: str,
    destination_node: str | None = None,
) -> dict[str, Any]:
    ingress = validate_ingress_packet(ingress_packet)
    lineage = ingress["lineage"]
    hop_trace = list(ingress["hop_trace"])
    hop_trace.append(
        {
            "node": source_node,
            "action": ingress["action"],
            "status": "completed",
            "timestamp": _utc_now_iso(),
        }
    )

    resolved_destination = destination_node or ingress.get("reply_to")
    packet_id = str(uuid.uuid4())
    timestamp = _utc_now_iso()

    return {
        "packet_id": packet_id,
        "packet_type": "enrichment_result",
        "action": ingress["action"],
        "payload": dict(result_payload),
        "timestamp": timestamp,
        "content_hash": canonical_packet_hash(ingress["action"], result_payload, ingress["tenant"]),
        "address": {
            "source_node": source_node,
            "destination_node": resolved_destination,
            "reply_to": source_node,
        },
        "tenant": ingress["tenant"],
        "lineage": {
            "parent_ids": [ingress.get("packet_id")] if ingress.get("packet_id") else [],
            "root_id": lineage.get("root_id"),
            "generation": int(lineage.get("generation", 0)) + 1,
            "derivation_type": lineage.get("derivation_type"),
        },
        "governance": dict(ingress.get("governance", {})),
        "hop_trace": hop_trace,
        "delegation_chain": list(ingress.get("delegation_chain", [])),
    }
