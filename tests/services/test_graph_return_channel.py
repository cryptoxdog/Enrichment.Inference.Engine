"""Tests for GRAPH -> ENRICH TransportPacket return channel."""

import pytest
from constellation_node_sdk.transport import create_transport_packet
from constellation_node_sdk.transport.errors import TransportValidationError

from app.services.graph_return_channel import (
    EnrichmentTarget,
    GraphReturnChannel,
    build_graph_inference_result_envelope,
    extract_targets_from_packet,
    validate_graph_inference_packet,
)


@pytest.fixture
def return_channel():
    """Fresh return channel instance for each test."""
    GraphReturnChannel.reset_instance()
    return GraphReturnChannel.get_instance()


def test_singleton_pattern():
    """GraphReturnChannel should be a singleton."""
    GraphReturnChannel.reset_instance()
    c1 = GraphReturnChannel.get_instance()
    c2 = GraphReturnChannel.get_instance()
    assert c1 is c2


def test_build_envelope_creates_valid_hashes():
    """build_graph_inference_result_envelope should create a valid packet."""
    packet = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {
                "entity_id": "e1",
                "field": "community_id",
                "value": 42,
                "confidence": 0.95,
                "rule": "louvain",
            }
        ],
    )
    assert packet.header.action == "graph-inference-result"
    assert packet.security.payload_hash
    assert packet.security.transport_hash
    validate_graph_inference_packet(packet)


def test_envelope_validation_catches_bad_hash():
    """Packet with wrong action should fail semantic validation."""
    packet = create_transport_packet(
        action="not-graph-result",
        payload={"inference_outputs": []},
        tenant="t1",
        source_node="graph-service",
        destination_node="gate",
        reply_to="graph-service",
    )
    with pytest.raises(TransportValidationError, match="expected action"):
        validate_graph_inference_packet(packet)


def test_envelope_to_targets_filters_low_confidence():
    """Low confidence outputs should be filtered out."""
    packet = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {"entity_id": "e1", "field": "f1", "value": "high", "confidence": 0.9, "rule": "r1"},
            {
                "entity_id": "e2",
                "field": "f2",
                "value": "low",
                "confidence": 0.3,
                "rule": "r2",
            },  # Below floor
        ],
    )
    targets = extract_targets_from_packet(packet)
    assert len(targets) == 1
    assert targets[0].entity_id == "e1"


@pytest.mark.asyncio
async def test_submit_and_drain(return_channel):
    """Submit should enqueue targets, drain should retrieve them."""
    packet = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {
                "entity_id": "e1",
                "field": "community_id",
                "value": 42,
                "confidence": 0.95,
                "rule": "louvain",
            },
            {
                "entity_id": "e2",
                "field": "community_id",
                "value": 43,
                "confidence": 0.95,
                "rule": "louvain",
            },
        ],
    )

    count = await return_channel.submit(packet)
    assert count == 2

    targets = await return_channel.drain("t1", timeout=0.1)
    assert len(targets) == 2
    assert {t.entity_id for t in targets} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_drain_respects_tenant_isolation(return_channel):
    """Drain should only return targets for the specified tenant."""
    packet1 = build_graph_inference_result_envelope(
        tenant_id="tenant_a",
        inference_outputs=[
            {"entity_id": "e1", "field": "f1", "value": 1, "confidence": 0.9, "rule": "r1"}
        ],
    )
    packet2 = build_graph_inference_result_envelope(
        tenant_id="tenant_b",
        inference_outputs=[
            {"entity_id": "e2", "field": "f2", "value": 2, "confidence": 0.9, "rule": "r2"}
        ],
    )

    await return_channel.submit(packet1)
    await return_channel.submit(packet2)

    targets_a = await return_channel.drain("tenant_a", timeout=0.1)
    targets_b = await return_channel.drain("tenant_b", timeout=0.1)

    assert len(targets_a) == 1
    assert targets_a[0].entity_id == "e1"
    assert len(targets_b) == 1
    assert targets_b[0].entity_id == "e2"


@pytest.mark.asyncio
async def test_invalid_envelope_raises(return_channel):
    """Invalid packet should raise TransportValidationError."""
    bad_packet = create_transport_packet(
        action="graph-inference-result",
        payload={"wrong": []},
        tenant="t1",
        source_node="graph-service",
        destination_node="gate",
        reply_to="graph-service",
    )
    with pytest.raises(TransportValidationError):
        await return_channel.submit(bad_packet)


def test_enrichment_target_to_dict():
    """EnrichmentTarget.to_dict should serialize correctly."""
    target = EnrichmentTarget(
        entity_id="e1",
        tenant_id="t1",
        field_name="community_id",
        seed_value=42,
        source_confidence=0.95,
        origin_packet_id="gir_123",
        origin_inference_rule="louvain",
    )
    d = target.to_dict()
    assert d["entity_id"] == "e1"
    assert d["field_name"] == "community_id"
    assert d["seed_value"] == 42
    assert d["source_confidence"] == 0.95
