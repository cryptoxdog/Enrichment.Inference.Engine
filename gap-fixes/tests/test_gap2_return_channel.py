"""Gap-2 tests: GRAPH→ENRICH bidirectional return channel."""

import math

import pytest

from engine.graph_return_channel import (
    GraphToEnrichReturnChannel,
    build_graph_inference_result_envelope,
)


@pytest.fixture(autouse=True)
def reset_channel():
    GraphToEnrichReturnChannel.reset_instance()
    yield
    GraphToEnrichReturnChannel.reset_instance()


@pytest.mark.asyncio
async def test_submit_and_drain():
    env = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=[
            {
                "entity_id": "e1",
                "field": "facility_tier",
                "value": "large",
                "confidence": 0.88,
                "rule": "louvain",
            }
        ],
    )
    ch = GraphToEnrichReturnChannel.get_instance()
    assert await ch.submit(env) == 1
    targets = await ch.drain("acme", timeout=0.1)
    assert len(targets) == 1
    assert targets[0].field_name == "facility_tier"
    assert math.isclose(targets[0].source_confidence, 0.88, rel_tol=1e-9)


@pytest.mark.asyncio
async def test_low_confidence_filtered():
    env = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=[
            {
                "entity_id": "e1",
                "field": "x",
                "value": "v",
                "confidence": 0.30,
                "rule": "r",
            }
        ],
    )
    ch = GraphToEnrichReturnChannel.get_instance()
    assert await ch.submit(env) == 0


@pytest.mark.asyncio
async def test_drain_returns_empty_when_nothing_pending():
    ch = GraphToEnrichReturnChannel.get_instance()
    targets = await ch.drain("no_such_tenant", timeout=0.05)
    assert targets == []


@pytest.mark.asyncio
async def test_tenant_isolation():
    ch = GraphToEnrichReturnChannel.get_instance()
    for tid in ("acme", "globex"):
        env = build_graph_inference_result_envelope(
            tenant_id=tid,
            inference_outputs=[
                {
                    "entity_id": "e1",
                    "field": "tier",
                    "value": tid,
                    "confidence": 0.9,
                    "rule": "r",
                }
            ],
        )
        await ch.submit(env)
    acme_targets = await ch.drain("acme", timeout=0.05)
    assert all(t.field_name == "tier" for t in acme_targets)
    globex_targets = await ch.drain("globex", timeout=0.05)
    assert all(t.seed_value == "globex" for t in globex_targets)
