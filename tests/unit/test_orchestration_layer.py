"""
Unit tests for orchestration_layer.register() and SDK runtime execution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from constellation_node_sdk.runtime.execution import execute_transport_packet
from constellation_node_sdk.runtime.handlers import (
    clear_handlers,
    register_handler,
    registered_actions,
)
from constellation_node_sdk.transport import create_transport_packet


@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry for each test."""
    clear_handlers()
    yield
    clear_handlers()


def test_register_wires_expected_actions():
    from app.engines import orchestration_layer

    kb = MagicMock()
    kb.index.files_loaded = []
    kb.index.polymers = []
    kb.index.total_grades = 0
    kb.index.total_rules = 0

    with (
        patch.object(orchestration_layer, "init_handlers"),
        patch.object(orchestration_layer, "GraphSyncClient"),
    ):
        orchestration_layer.register(kb=kb, idem_store=None)

    handlers = registered_actions()
    for action in ["enrich", "enrichbatch", "converge", "discover", "enrich-and-sync"]:
        assert action in handlers, f"Action '{action}' not registered"


@pytest.mark.asyncio
async def test_sdk_runtime_dispatches_to_enrich():
    mock_handler = AsyncMock(return_value={"state": "completed", "fields": {"grade": "A"}})
    register_handler("enrich", mock_handler)

    packet = create_transport_packet(
        action="enrich",
        payload={"entity_id": "e-001"},
        tenant="test-tenant",
        source_node="gate",
        destination_node="enrichment-engine",
        reply_to="gate",
    )
    result = await execute_transport_packet(
        packet,
        node_name="enrichment-engine",
        dev_mode=True,
        allowed_actions=("enrich",),
    )
    assert result.header.packet_type == "response"
    assert result.payload["state"] == "completed"
    mock_handler.assert_awaited_once_with("test-tenant", {"entity_id": "e-001"})


@pytest.mark.asyncio
async def test_sdk_runtime_raises_for_unknown_action():
    packet = create_transport_packet(
        action="unknown-action",
        payload={},
        tenant="test",
        source_node="gate",
        destination_node="enrichment-engine",
        reply_to="gate",
    )
    with pytest.raises(ValueError, match="unknown-action"):
        await execute_transport_packet(
            packet,
            node_name="enrichment-engine",
            dev_mode=True,
        )


@pytest.mark.asyncio
async def test_transport_packet_requires_action():
    with pytest.raises(ValueError, match="action"):
        create_transport_packet(
            action="",
            payload={},
            tenant="test",
            source_node="gate",
            destination_node="enrichment-engine",
            reply_to="gate",
        )
