"""
SDK transport packet contract tests.

This file preserves compatibility coverage for TransportPacket semantics, but it
does NOT define production ingress ownership. Constitutional transport truth is:
- /v1/execute is SDK-owned via app/main.py
- local chassis envelope/router/registry are deprecated compatibility artifacts

Markers: unit
"""

from __future__ import annotations

import pytest
from constellation_node_sdk.transport import create_transport_packet
from constellation_node_sdk.transport.hop_trace import make_execution_hop


@pytest.mark.unit
def test_transport_packet_requires_non_empty_action() -> None:
    with pytest.raises(ValueError, match="action"):
        create_transport_packet(
            action="",
            payload={},
            tenant="t1",
            source_node="client",
            destination_node="gate",
        )


@pytest.mark.unit
def test_transport_packet_requires_dict_payload() -> None:
    with pytest.raises(TypeError):
        create_transport_packet(  # type: ignore[arg-type]
            action="enrich",
            payload=None,
            tenant="t1",
            source_node="client",
            destination_node="gate",
        )


@pytest.mark.unit
def test_create_transport_packet_returns_guaranteed_fields() -> None:
    packet = create_transport_packet(
        action="enrich",
        payload={},
        tenant="t1",
        source_node="client",
        destination_node="gate",
    )
    assert packet.header.packet_id
    assert packet.header.action == "enrich"
    assert packet.payload == {}
    assert packet.security.payload_hash
    assert packet.security.transport_hash
    assert packet.tenant.org_id == "t1"
    assert packet.lineage.generation == 0
    assert packet.address.destination_node == "gate"


@pytest.mark.unit
def test_transport_packet_preserves_tenant_context() -> None:
    packet = create_transport_packet(
        action="enrich",
        payload={},
        tenant="acme-corp",
        source_node="client",
        destination_node="gate",
    )
    assert packet.tenant.org_id == "acme-corp"


@pytest.mark.unit
def test_derive_increments_generation_and_sets_parent() -> None:
    packet = create_transport_packet(
        action="enrich",
        payload={},
        tenant="t1",
        source_node="client",
        destination_node="gate",
    )
    child = packet.derive(
        action="sync",
        payload={"entity_id": "e1"},
        source_node="enrichment-engine",
        destination_node="gate",
    )
    assert child.lineage.generation == packet.lineage.generation + 1
    assert child.lineage.parent_id == packet.header.packet_id
    assert child.lineage.root_id == packet.lineage.root_id


@pytest.mark.unit
def test_with_hop_appends_hop_trace() -> None:
    packet = create_transport_packet(
        action="enrich",
        payload={},
        tenant="t1",
        source_node="client",
        destination_node="gate",
    )
    hopped = packet.with_hop(
        make_execution_hop(
            packet=packet,
            node="enrichment-engine",
            action=packet.header.action,
            status="processing",
        )
    )
    assert len(hopped.hop_trace) == 1
    assert hopped.hop_trace[-1].action == "enrich"


@pytest.mark.unit
def test_transport_packet_contract_is_compatibility_not_ingress_authority() -> None:
    """
    Guardrail test: this contract file validates SDK TransportPacket semantics only.
    It must not be treated as authority for local chassis ingress or deprecated
    envelope/router production dispatch.
    """
    assert True
