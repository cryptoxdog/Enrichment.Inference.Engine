"""
PacketEnvelope Contract Tests — Source: chassis/envelope.py
Markers: unit
"""
from __future__ import annotations
import pytest
import yaml
from tests.contracts.conftest_contracts import AGENTS_DIR

try:
    from chassis.envelope import inflate_ingress, deflate_egress, _compute_hash
    CHASSIS_AVAILABLE = True
except ImportError:
    CHASSIS_AVAILABLE = False

chassis_required = pytest.mark.skipif(not CHASSIS_AVAILABLE, reason="chassis not on PYTHONPATH")


@pytest.fixture(scope="module")
def envelope_contract() -> dict:
    path = AGENTS_DIR / "protocols" / "packet-envelope.yaml"
    if not path.exists():
        pytest.skip("packet-envelope.yaml missing")
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.mark.unit
def test_envelope_contract_has_ingress_schema(envelope_contract: dict) -> None:
    assert any(k in str(envelope_contract).lower() for k in ("ingress", "inflate", "inbound"))

@pytest.mark.unit
def test_envelope_contract_has_egress_schema(envelope_contract: dict) -> None:
    assert any(k in str(envelope_contract).lower() for k in ("egress", "deflate", "outbound", "result"))

@pytest.mark.unit
def test_envelope_contract_lists_actions(envelope_contract: dict) -> None:
    s = str(envelope_contract).lower()
    for action in ["enrich", "writeback", "converge", "discover"]:
        assert action in s, f"packet-envelope.yaml missing action '{action}'"

@pytest.mark.unit
def test_envelope_contract_documents_tenant(envelope_contract: dict) -> None:
    assert "tenant" in str(envelope_contract).lower()

@pytest.mark.unit
def test_envelope_contract_documents_content_hash(envelope_contract: dict) -> None:
    assert "content_hash" in str(envelope_contract)


# ── Behavioral invariants ─────────────────────────────────────────────────

@chassis_required
@pytest.mark.unit
def test_inflate_missing_action_raises() -> None:
    with pytest.raises(ValueError, match="action"):
        inflate_ingress({"payload": {}})

@chassis_required
@pytest.mark.unit
def test_inflate_missing_payload_raises() -> None:
    with pytest.raises(ValueError, match="payload"):
        inflate_ingress({"action": "enrich", "payload": "bad"})

@chassis_required
@pytest.mark.unit
def test_inflate_null_payload_raises() -> None:
    with pytest.raises(ValueError, match="payload"):
        inflate_ingress({"action": "enrich"})

@chassis_required
@pytest.mark.unit
def test_inflate_returns_guaranteed_fields() -> None:
    result = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1"})
    for field in ["packet_id", "action", "payload", "content_hash", "tenant", "lineage", "governance", "hop_trace", "timestamp"]:
        assert field in result, f"Missing guaranteed field: {field}"

@chassis_required
@pytest.mark.unit
def test_inflate_destination_node_fixed() -> None:
    result = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1"})
    assert result["address"]["destination_node"] == "enrichment-engine"

@chassis_required
@pytest.mark.unit
def test_inflate_computes_correct_hash() -> None:
    action, payload, tenant = "enrich", {"Name": "Acme"}, "acme-corp"
    result = inflate_ingress({"action": action, "payload": payload, "tenant": tenant})
    assert result["content_hash"] == _compute_hash(action, payload, tenant)

@chassis_required
@pytest.mark.unit
def test_inflate_tampered_hash_raises() -> None:
    with pytest.raises(ValueError, match="content_hash"):
        inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1", "content_hash": "bad" * 20})

@chassis_required
@pytest.mark.unit
def test_deflate_increments_generation() -> None:
    envelope = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1"})
    initial = envelope["lineage"]["generation"]
    egress = deflate_egress(envelope, {})
    assert egress["lineage"]["generation"] == initial + 1

@chassis_required
@pytest.mark.unit
def test_deflate_appends_hop_trace() -> None:
    envelope = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1"})
    initial_hops = len(envelope["hop_trace"])
    egress = deflate_egress(envelope, {})
    assert len(egress["hop_trace"]) == initial_hops + 1
    assert egress["hop_trace"][-1]["action"] == "respond"

@chassis_required
@pytest.mark.unit
def test_deflate_preserves_tenant() -> None:
    envelope = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "acme-corp"})
    egress = deflate_egress(envelope, {})
    assert egress["tenant"]["actor"] == "acme-corp"

@chassis_required
@pytest.mark.unit
def test_deflate_packet_type_is_result() -> None:
    envelope = inflate_ingress({"action": "enrich", "payload": {}, "tenant": "t1"})
    egress = deflate_egress(envelope, {})
    assert egress.get("packet_type") == "enrichment_result"

@chassis_required
@pytest.mark.unit
def test_inflate_lineage_defaults() -> None:
    envelope = inflate_ingress({"action": "discover", "payload": {}, "tenant": "t1"})
    lineage = envelope["lineage"]
    assert lineage["generation"] == 0
    assert lineage["derivation_type"] == "origin"
    assert lineage["parent_ids"] == []
