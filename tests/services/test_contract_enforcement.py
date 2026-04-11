"""Tests for PacketEnvelope contract enforcement."""
import pytest

from app.services.contract_enforcement import (
    ContractViolationError,
    build_graph_sync_packet,
    build_schema_proposal_packet,
    build_enrich_result_packet,
    enforce_packet_envelope,
)


def test_bare_dict_rejected():
    """Bare dict without required fields should be rejected."""
    with pytest.raises(ContractViolationError):
        enforce_packet_envelope(
            {"entity_type": "account", "batch": []}, 
            expected_type="graph_sync"
        )


def test_type_mismatch_raises():
    """Packet type mismatch should raise ContractViolationError."""
    pkt = build_graph_sync_packet(
        tenant_id="t1", 
        entity_type="account", 
        batch=[{"id": "1"}]
    )
    with pytest.raises(ContractViolationError, match="mismatch"):
        enforce_packet_envelope(pkt, expected_type="enrich_request")


def test_valid_graph_sync_passes():
    """Valid graph_sync packet should pass validation."""
    pkt = build_graph_sync_packet(
        tenant_id="t1", 
        entity_type="account", 
        batch=[{"id": "1"}]
    )
    result = enforce_packet_envelope(pkt, expected_type="graph_sync")
    assert result["packet_type"] == "graph_sync"
    assert result["content_hash"]
    assert result["envelope_hash"]


def test_schema_proposal_type_allowed():
    """schema_proposal packet type should be allowed."""
    pkt = build_schema_proposal_packet(
        tenant_id="t1",
        proposed_fields=[{"name": "facility_tier", "type": "string"}],
    )
    result = enforce_packet_envelope(pkt, expected_type="schema_proposal")
    assert result["packet_id"].startswith("sp_")


def test_enrich_result_type_allowed():
    """enrich_result packet type should be allowed."""
    pkt = build_enrich_result_packet(
        tenant_id="t1",
        entity_id="ent_123",
        enriched_fields={"company_name": "Acme Corp"},
        confidence=0.85,
        pass_count=2,
    )
    result = enforce_packet_envelope(pkt, expected_type="enrich_result")
    assert result["packet_id"].startswith("er_")
    assert result["entity_id"] == "ent_123"


def test_tampered_content_hash_rejected():
    """Tampered content_hash should be rejected."""
    pkt = build_graph_sync_packet(
        tenant_id="t1", 
        entity_type="account", 
        batch=[{"id": "1"}]
    )
    pkt["content_hash"] = "deadbeef"
    with pytest.raises(ContractViolationError, match="content_hash mismatch"):
        enforce_packet_envelope(pkt, expected_type="graph_sync")


def test_missing_required_field_rejected():
    """Missing required field should be rejected."""
    pkt = build_graph_sync_packet(
        tenant_id="t1", 
        entity_type="account", 
        batch=[{"id": "1"}]
    )
    del pkt["tenant_id"]
    with pytest.raises(ContractViolationError, match="tenant_id"):
        enforce_packet_envelope(pkt, expected_type="graph_sync")


def test_unknown_packet_type_rejected():
    """Unknown packet type should be rejected."""
    pkt = {
        "packet_id": "test_123",
        "packet_type": "unknown_type",
        "tenant_id": "t1",
    }
    with pytest.raises(ContractViolationError, match="not in the allowed set"):
        enforce_packet_envelope(pkt, expected_type="unknown_type")


def test_empty_envelope_hash_rejected():
    """Empty envelope_hash should be rejected."""
    pkt = build_graph_sync_packet(
        tenant_id="t1", 
        entity_type="account", 
        batch=[{"id": "1"}]
    )
    pkt["envelope_hash"] = ""
    with pytest.raises(ContractViolationError, match="envelope_hash is empty"):
        enforce_packet_envelope(pkt, expected_type="graph_sync")
