from __future__ import annotations

import pytest

from app.services.packet_enforcement import (
    PacketPolicyError,
    PacketValidationError,
    build_egress_packet,
    canonical_packet_hash,
    validate_ingress_packet,
)

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]


def make_ingress_packet(action: str = "enrich") -> dict[str, object]:
    payload = {
        "entity": {"Name": "Acme Recycling Corp"},
        "object_type": "Account",
        "objective": "Enrich polymer data",
    }
    tenant = "acme-corp"
    return {
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
        "governance": {"intent": action},
        "hop_trace": [
            {
                "node": "gateway",
                "action": "dispatch",
                "status": "completed",
                "timestamp": "2026-04-06T20:00:00+00:00",
            }
        ],
        "delegation_chain": [],
        "content_hash": canonical_packet_hash(action, payload, tenant),
    }


def test_validate_ingress_packet_accepts_valid_contract_packet() -> None:
    packet = make_ingress_packet()
    normalized = validate_ingress_packet(packet)
    assert normalized["action"] == "enrich"
    assert normalized["lineage"]["generation"] == 2


def test_validate_ingress_packet_rejects_bad_hash() -> None:
    packet = make_ingress_packet()
    packet["content_hash"] = "deadbeef"
    with pytest.raises(PacketValidationError, match="content_hash verification failed"):
        validate_ingress_packet(packet)


def test_validate_ingress_packet_rejects_unknown_action() -> None:
    packet = make_ingress_packet(action="unknown_action")
    packet["content_hash"] = None
    with pytest.raises(PacketValidationError, match="packet.action is not registered"):
        validate_ingress_packet(packet)


def test_build_egress_packet_increments_lineage_and_preserves_reply_to() -> None:
    ingress = validate_ingress_packet(make_ingress_packet())
    egress = build_egress_packet(
        ingress,
        {"status": "completed"},
        current_node="enrichment-engine",
        policy_cleared=True,
    )
    assert egress["lineage"]["generation"] == 3
    assert egress["address"]["destination_node"] == "route-engine"
    assert egress["hop_trace"][-1]["node"] == "enrichment-engine"


def test_writeback_requires_policy_clearance() -> None:
    ingress = validate_ingress_packet(make_ingress_packet(action="writeback"))
    with pytest.raises(PacketPolicyError, match="requires explicit policy clearance"):
        build_egress_packet(
            ingress,
            {"status": "completed"},
            current_node="enrichment-engine",
            policy_cleared=False,
        )
