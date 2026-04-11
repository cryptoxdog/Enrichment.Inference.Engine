"""
Unit tests for TransportPacket root/child behavior.
"""

from __future__ import annotations

import pytest
from constellation_node_sdk.transport import create_transport_packet

BASE_PAYLOAD = {"entity_id": "e-001", "fields": {"name": "Alpha Recyclers"}}


def test_create_transport_packet_produces_required_sections():
    packet = create_transport_packet(
        action="enrich",
        tenant="acme",
        payload=BASE_PAYLOAD,
        source_node="client",
        destination_node="gate",
    )
    assert packet.header.packet_id
    assert packet.address.destination_node == "gate"
    assert packet.tenant.org_id == "acme"
    assert packet.security.payload_hash
    assert packet.security.transport_hash
    assert packet.lineage.generation == 0


def test_create_transport_packet_computes_deterministic_hash():
    packet1 = create_transport_packet(
        action="enrich",
        tenant="acme",
        payload=BASE_PAYLOAD,
        source_node="client",
        destination_node="gate",
    )
    packet2 = create_transport_packet(
        action="enrich",
        tenant="acme",
        payload=BASE_PAYLOAD,
        source_node="client",
        destination_node="gate",
    )
    assert packet1.security.payload_hash == packet2.security.payload_hash


def test_derive_creates_child_packet():
    packet = create_transport_packet(
        action="enrich",
        tenant="acme",
        payload=BASE_PAYLOAD,
        source_node="client",
        destination_node="gate",
    )
    child = packet.derive(
        action="sync",
        payload={"entity_id": "e-001"},
        source_node="enrichment-engine",
        destination_node="gate",
    )
    assert child.header.packet_type == "request"
    assert child.lineage.generation == 1
    assert child.lineage.parent_id == packet.header.packet_id


def test_derive_preserves_root_id():
    packet = create_transport_packet(
        action="enrich",
        tenant="acme",
        payload=BASE_PAYLOAD,
        source_node="client",
        destination_node="gate",
    )
    child = packet.derive(
        action="sync",
        payload={"entity_id": "e-001"},
        source_node="enrichment-engine",
        destination_node="gate",
    )
    assert child.lineage.root_id == packet.lineage.root_id


def test_create_transport_packet_rejects_blank_action():
    with pytest.raises(ValueError, match="action"):
        create_transport_packet(
            action="",
            tenant="acme",
            payload=BASE_PAYLOAD,
            source_node="client",
            destination_node="gate",
        )


def test_create_transport_packet_requires_dict_payload():
    with pytest.raises(TypeError):
        create_transport_packet(  # type: ignore[arg-type]
            action="enrich",
            tenant="acme",
            payload=None,
            source_node="client",
            destination_node="gate",
        )
