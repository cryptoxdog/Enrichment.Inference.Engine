"""Tests for TransportPacket contract enforcement."""

import pytest

from app.services.contract_enforcement import (
    ContractViolationError,
    build_enrich_result_packet,
    build_graph_sync_packet,
    build_schema_proposal_packet,
    enforce_transport_packet,
)


def test_bare_dict_rejected():
    """Bare dict should be rejected because the contract surface is TransportPacket."""
    with pytest.raises(ContractViolationError):
        enforce_transport_packet(
            {"entity_type": "account", "batch": []},
            expected_type="graph_sync",
        )


def test_type_mismatch_raises():
    """Action mismatch should raise ContractViolationError."""
    pkt = build_graph_sync_packet(
        tenant_id="t1",
        entity_type="account",
        batch=[{"id": "1"}],
    )
    with pytest.raises(ContractViolationError, match="mismatch"):
        enforce_transport_packet(pkt, expected_type="enrich_request")


def test_valid_graph_sync_passes():
    """Valid graph-sync packet should pass validation."""
    pkt = build_graph_sync_packet(
        tenant_id="t1",
        entity_type="account",
        batch=[{"id": "1"}],
    )
    result = enforce_transport_packet(pkt, expected_type="graph_sync")
    assert result.header.action == "graph-sync"
    assert result.security.payload_hash
    assert result.security.transport_hash


def test_schema_proposal_type_allowed():
    """schema-proposal action should be allowed."""
    pkt = build_schema_proposal_packet(
        tenant_id="t1",
        proposed_fields=[{"name": "facility_tier", "type": "string"}],
    )
    result = enforce_transport_packet(pkt, expected_type="schema_proposal")
    assert result.header.action == "schema-proposal"


def test_enrich_result_type_allowed():
    """enrich-result action should be allowed."""
    pkt = build_enrich_result_packet(
        tenant_id="t1",
        entity_id="ent_123",
        enriched_fields={"company_name": "Acme Corp"},
        confidence=0.85,
        pass_count=2,
    )
    result = enforce_transport_packet(pkt, expected_type="enrich_result")
    assert result.header.action == "enrich-result"
    assert result.payload["entity_id"] == "ent_123"


def test_missing_required_field_rejected():
    """Missing required field should be rejected."""
    pkt = build_graph_sync_packet(
        tenant_id="t1",
        entity_type="account",
        batch=[{"id": "1"}],
    )
    pkt = pkt.model_copy(update={"payload": {"entity_type": "account"}})
    with pytest.raises(ContractViolationError, match="batch"):
        enforce_transport_packet(pkt, expected_type="graph_sync")


def test_unknown_packet_type_rejected():
    """Unknown action should be rejected."""
    pkt = build_graph_sync_packet(
        tenant_id="t1",
        entity_type="account",
        batch=[{"id": "1"}],
    )
    with pytest.raises(ContractViolationError, match="not in the allowed set"):
        enforce_transport_packet(pkt, expected_type="unknown_type")
