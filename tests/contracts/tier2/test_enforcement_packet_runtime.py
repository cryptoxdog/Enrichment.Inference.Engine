"""
Tier 2 — Enforcement: Packet Runtime Behavior
=============================================
Proves PacketEnvelope ingress/egress semantics match the current protocol contract.

Primary source:
- docs/contracts/agents/protocols/packet-envelope.yaml
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]

ROOT = Path(".")
PACKET_PROTOCOL_PATH = ROOT / "docs/contracts/agents/protocols/packet-envelope.yaml"
CURRENT_NODE = "enrichment-engine"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def packet_protocol() -> dict[str, Any]:
    return _load_yaml(PACKET_PROTOCOL_PATH)


def _tenant_to_string(tenant: Any) -> str:
    if isinstance(tenant, str):
        return tenant
    if isinstance(tenant, dict):
        return str(tenant.get("actor", "unknown"))
    return "unknown"


def _canonical_hash(action: str, payload: dict[str, Any], tenant: Any) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload, "tenant": _tenant_to_string(tenant)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def inflate_ingress(
    packet: dict[str, Any],
    registered_actions: set[str],
) -> dict[str, Any]:
    if "action" not in packet:
        raise ValueError("Missing required field: action")

    action = packet["action"]
    if action not in registered_actions:
        raise KeyError(f"No handler registered for action '{action}'")

    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Missing or invalid field: payload (must be a dict)")

    tenant = packet.get("tenant", "unknown")
    declared_hash = packet.get("content_hash")
    if declared_hash is not None:
        computed_hash = _canonical_hash(action, payload, tenant)
        if declared_hash != computed_hash:
            raise ValueError("content_hash verification failed: payload may be tampered")

    lineage = packet.get("lineage") or {}
    hop_trace = packet.get("hop_trace") or []

    return {
        **packet,
        "tenant": tenant,
        "lineage": {
            "parent_ids": list(lineage.get("parent_ids", [])),
            "root_id": lineage.get("root_id"),
            "generation": int(lineage.get("generation", 0)),
            "derivation_type": lineage.get("derivation_type"),
        },
        "hop_trace": list(hop_trace),
    }


def build_egress(
    ingress: dict[str, Any],
    result_payload: dict[str, Any],
    *,
    policy_cleared: bool = False,
) -> dict[str, Any]:
    if ingress["action"] == "writeback" and not policy_cleared:
        raise PermissionError("Action 'writeback' requires policy clearance before egress")

    ingress_lineage = ingress.get("lineage", {})
    generation = int(ingress_lineage.get("generation", 0)) + 1
    ingress_packet_id = ingress.get("packet_id", "ingress-packet")

    hop_trace = list(ingress.get("hop_trace", []))
    hop_trace.append(
        {
            "node": CURRENT_NODE,
            "action": ingress["action"],
            "status": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    timestamp = datetime.now(UTC).isoformat()
    content_hash = _canonical_hash(ingress["action"], result_payload, ingress["tenant"])

    return {
        "packet_id": str(uuid.uuid4()),
        "packet_type": "enrichment_result",
        "action": ingress["action"],
        "payload": result_payload,
        "timestamp": timestamp,
        "content_hash": content_hash,
        "address": {
            "source_node": CURRENT_NODE,
            "destination_node": ingress.get("reply_to"),
            "reply_to": CURRENT_NODE,
        },
        "tenant": ingress["tenant"],
        "lineage": {
            "parent_ids": [ingress_packet_id],
            "root_id": ingress_lineage.get("root_id"),
            "generation": generation,
            "derivation_type": ingress_lineage.get("derivation_type"),
        },
        "governance": ingress.get("governance", {}),
        "hop_trace": hop_trace,
        "delegation_chain": ingress.get("delegation_chain", []),
    }


def make_valid_packet(
    *,
    action: str = "enrich",
    payload: dict[str, Any] | None = None,
    tenant: Any = "acme-corp",
    include_hash: bool = True,
    **overrides: Any,
) -> dict[str, Any]:
    if payload is None:
        payload = {
            "entity": {"name": "Acme Plastics"},
            "object_type": "Account",
            "objective": "Enrich company profile",
        }

    packet: dict[str, Any] = {
        "packet_id": "ingress-pkt-001",
        "action": action,
        "payload": payload,
        "tenant": tenant,
        "source_node": "score-engine",
        "reply_to": "route-engine",
        "lineage": {
            "parent_ids": ["root-pkt-000"],
            "root_id": "root-pkt-000",
            "generation": 2,
            "derivation_type": "dispatch",
        },
        "governance": {
            "intent": "enrichment",
            "audit_required": True,
            "compliance_tags": ["tenant:acme-corp"],
        },
        "hop_trace": [
            {
                "node": "gateway",
                "action": "dispatch",
                "status": "completed",
                "timestamp": "2026-04-06T20:00:00+00:00",
            }
        ],
        "delegation_chain": [],
    }
    if include_hash:
        packet["content_hash"] = _canonical_hash(action, payload, tenant)

    packet.update(overrides)
    return packet


class TestContentHashEnforcement:
    def test_valid_hash_passes(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet()
        inflated = inflate_ingress(packet, actions)
        assert inflated["action"] == "enrich"

    def test_mismatched_hash_raises(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(content_hash="bad-hash")
        with pytest.raises(ValueError, match="content_hash verification failed"):
            inflate_ingress(packet, actions)

    def test_missing_hash_skips_verification(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(include_hash=False)
        inflated = inflate_ingress(packet, actions)
        assert inflated["action"] == "enrich"


class TestPayloadTypeEnforcement:
    def test_non_dict_payload_raises(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(payload="not-a-dict")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="payload"):
            inflate_ingress(packet, actions)

    def test_list_payload_raises(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(payload=[{"name": "Acme"}])  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="payload"):
            inflate_ingress(packet, actions)


class TestActionRegistryEnforcement:
    def test_unknown_action_raises(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(action="unknown-action", include_hash=False)
        with pytest.raises(KeyError, match="No handler registered"):
            inflate_ingress(packet, actions)

    def test_all_registered_actions_accepted(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        for action in actions:
            packet = make_valid_packet(action=action)
            inflated = inflate_ingress(packet, actions)
            assert inflated["action"] == action


class TestLineageAndHopTrace:
    def test_lineage_generation_increments_by_one(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet()
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "completed"})
        assert egress["lineage"]["generation"] == inflated["lineage"]["generation"] + 1

    def test_egress_parent_ids_reference_ingress_packet(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(packet_id="ingress-pkt-abc")
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "completed"})
        assert egress["lineage"]["parent_ids"] == ["ingress-pkt-abc"]

    def test_hop_trace_appends_current_node(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet()
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "completed"})
        last_hop = egress["hop_trace"][-1]
        assert last_hop["node"] == CURRENT_NODE
        assert last_hop["action"] == inflated["action"]


class TestReplyToPreservation:
    def test_destination_node_uses_ingress_reply_to(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(reply_to="my-reply-node")
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "completed"})
        assert egress["address"]["destination_node"] == "my-reply-node"

    def test_source_and_reply_to_are_current_node_on_egress(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet()
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "completed"})
        assert egress["address"]["source_node"] == CURRENT_NODE
        assert egress["address"]["reply_to"] == CURRENT_NODE


class TestWritebackPolicyGate:
    def test_writeback_requires_policy_clearance(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(action="writeback")
        inflated = inflate_ingress(packet, actions)
        with pytest.raises(PermissionError, match="policy clearance"):
            build_egress(inflated, {"status": "written"})

    def test_writeback_succeeds_when_policy_cleared(
        self,
        packet_protocol: dict[str, Any],
    ) -> None:
        actions = {item["action"] for item in packet_protocol["registered_handlers"]}
        packet = make_valid_packet(action="writeback")
        inflated = inflate_ingress(packet, actions)
        egress = build_egress(inflated, {"status": "written"}, policy_cleared=True)
        assert egress["action"] == "writeback"
