"""Tests for GRAPH → ENRICH return channel."""
import pytest

from app.services.contract_enforcement import ContractViolationError
from app.services.graph_return_channel import (
    EnrichmentTarget,
    GraphInferenceResultEnvelope,
    GraphReturnChannel,
    build_graph_inference_result_envelope,
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
    """build_graph_inference_result_envelope should create valid hashes."""
    envelope = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {"entity_id": "e1", "field": "community_id", "value": 42, "confidence": 0.95, "rule": "louvain"}
        ],
    )
    assert envelope.packet_id.startswith("gir_")
    assert envelope.content_hash
    assert envelope.envelope_hash
    # Validation should pass
    envelope.validate()


def test_envelope_validation_catches_bad_hash():
    """Envelope with bad content_hash should fail validation."""
    envelope = GraphInferenceResultEnvelope(
        packet_id="gir_test",
        tenant_id="t1",
        inference_outputs=[{"entity_id": "e1", "field": "f1", "value": 1, "confidence": 0.9, "rule": "r1"}],
        content_hash="bad_hash",
        envelope_hash="some_hash",
    )
    with pytest.raises(ContractViolationError, match="content_hash mismatch"):
        envelope.validate()


def test_envelope_to_targets_filters_low_confidence():
    """Low confidence outputs should be filtered out."""
    envelope = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {"entity_id": "e1", "field": "f1", "value": "high", "confidence": 0.9, "rule": "r1"},
            {"entity_id": "e2", "field": "f2", "value": "low", "confidence": 0.3, "rule": "r2"},  # Below floor
        ],
    )
    targets = envelope.to_targets()
    assert len(targets) == 1
    assert targets[0].entity_id == "e1"


@pytest.mark.asyncio
async def test_submit_and_drain(return_channel):
    """Submit should enqueue targets, drain should retrieve them."""
    envelope = build_graph_inference_result_envelope(
        tenant_id="t1",
        inference_outputs=[
            {"entity_id": "e1", "field": "community_id", "value": 42, "confidence": 0.95, "rule": "louvain"},
            {"entity_id": "e2", "field": "community_id", "value": 43, "confidence": 0.95, "rule": "louvain"},
        ],
    )
    
    count = await return_channel.submit(envelope)
    assert count == 2
    
    targets = await return_channel.drain("t1", timeout=0.1)
    assert len(targets) == 2
    assert {t.entity_id for t in targets} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_drain_respects_tenant_isolation(return_channel):
    """Drain should only return targets for the specified tenant."""
    env1 = build_graph_inference_result_envelope(
        tenant_id="tenant_a",
        inference_outputs=[{"entity_id": "e1", "field": "f1", "value": 1, "confidence": 0.9, "rule": "r1"}],
    )
    env2 = build_graph_inference_result_envelope(
        tenant_id="tenant_b",
        inference_outputs=[{"entity_id": "e2", "field": "f2", "value": 2, "confidence": 0.9, "rule": "r2"}],
    )
    
    await return_channel.submit(env1)
    await return_channel.submit(env2)
    
    targets_a = await return_channel.drain("tenant_a", timeout=0.1)
    targets_b = await return_channel.drain("tenant_b", timeout=0.1)
    
    assert len(targets_a) == 1
    assert targets_a[0].entity_id == "e1"
    assert len(targets_b) == 1
    assert targets_b[0].entity_id == "e2"


@pytest.mark.asyncio
async def test_invalid_envelope_raises(return_channel):
    """Invalid envelope should raise ContractViolationError."""
    bad_envelope = GraphInferenceResultEnvelope(
        packet_id="",  # Invalid - empty
        tenant_id="t1",
        inference_outputs=[],
        content_hash="",
        envelope_hash="",
    )
    with pytest.raises(ContractViolationError):
        await return_channel.submit(bad_envelope)


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
