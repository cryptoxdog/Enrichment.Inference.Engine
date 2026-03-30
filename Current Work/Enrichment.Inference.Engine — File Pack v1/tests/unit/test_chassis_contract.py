"""
Unit tests for chassis_contract.py (inflate/deflate/delegate).
These tests validate the PacketEnvelope protocol invariants.
"""

import pytest

from app.engines.chassis_contract import deflate_egress, delegate_to_node, inflate_ingress

BASE_RAW = {
    "action": "enrich",
    "tenant": "acme",
    "payload": {"entity_id": "e-001", "fields": {"name": "Alpha Recyclers"}},
}


def test_inflate_produces_required_keys():
    env = inflate_ingress(BASE_RAW)
    for key in (
        "packet_id",
        "packet_type",
        "action",
        "payload",
        "timestamp",
        "address",
        "tenant",
        "content_hash",
        "lineage",
        "governance",
        "hop_trace",
    ):
        assert key in env, f"Missing key: {key}"


def test_inflate_computes_deterministic_hash():
    env1 = inflate_ingress(BASE_RAW)
    env2 = inflate_ingress(BASE_RAW)
    assert env1["content_hash"] == env2["content_hash"]


def test_inflate_rejects_tampered_hash():
    raw = {**BASE_RAW, "content_hash": "bad_hash_value"}
    with pytest.raises(ValueError, match="content_hash"):
        inflate_ingress(raw)


def test_inflate_appends_hop_trace():
    env = inflate_ingress(BASE_RAW)
    assert len(env["hop_trace"]) == 1
    assert env["hop_trace"][0]["node"] == "enrichment-engine"


def test_deflate_creates_result_packet():
    env = inflate_ingress(BASE_RAW)
    result = deflate_egress(env, {"material_grade": "A"})
    assert result["packet_type"] == "enrichment_result"
    assert result["payload"]["material_grade"] == "A"


def test_deflate_increments_generation():
    env = inflate_ingress(BASE_RAW)
    result = deflate_egress(env, {})
    assert result["lineage"]["generation"] == 1


def test_deflate_hop_trace_has_respond_entry():
    env = inflate_ingress(BASE_RAW)
    result = deflate_egress(env, {})
    actions = [h["action"] for h in result["hop_trace"]]
    assert "respond" in actions


def test_delegate_forces_audit_required():
    env = inflate_ingress(BASE_RAW)
    derived = delegate_to_node(env, "graph-service", ["read", "sync"])
    assert derived["governance"]["audit_required"] is True


def test_delegate_appends_delegation_chain():
    env = inflate_ingress(BASE_RAW)
    derived = delegate_to_node(env, "graph-service", ["sync"])
    chain = derived["delegation_chain"]
    assert len(chain) == 1
    assert chain[0]["delegatee"] == "graph-service"


def test_inflate_missing_action_raises():
    with pytest.raises(ValueError, match="action"):
        inflate_ingress({"payload": {}})


def test_inflate_missing_payload_raises():
    with pytest.raises(ValueError, match="payload"):
        inflate_ingress({"action": "enrich"})
