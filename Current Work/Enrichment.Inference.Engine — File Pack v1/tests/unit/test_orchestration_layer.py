"""
Unit tests for orchestration_layer.register() and chassis routing.
Validates that handlers are correctly wired through the chassis registry.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from l9.chassis.registry import clear_handlers, get_handler_map


@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry for each test."""
    clear_handlers()
    yield
    clear_handlers()


def test_register_wires_expected_actions():
    kb = MagicMock()
    kb.index.files_loaded = []
    kb.index.polymers = []
    kb.index.total_grades = 0
    kb.index.total_rules = 0

    with patch("app.engines.handlers.init_handlers"):
        from app.engines.orchestration_layer import register

        register(kb=kb, idem_store=None)

    handlers = get_handler_map()
    for action in ["enrich", "enrichbatch", "converge", "discover", "enrich_and_sync"]:
        assert action in handlers, f"Action '{action}' not registered"


@pytest.mark.asyncio
async def test_chassis_router_dispatches_to_enrich():
    from l9.chassis.registry import register_handler

    mock_handler = AsyncMock(return_value={"state": "completed", "fields": {"grade": "A"}})
    register_handler("enrich", mock_handler)

    from l9.chassis.router import route_packet

    result = await route_packet(
        {
            "action": "enrich",
            "tenant": "test-tenant",
            "payload": {"entity_id": "e-001"},
        }
    )
    assert result["packet_type"] == "enrichment_result"
    mock_handler.assert_awaited_once_with("test-tenant", {"entity_id": "e-001"})


@pytest.mark.asyncio
async def test_chassis_router_raises_key_error_for_unknown_action():
    from l9.chassis.router import route_packet

    with pytest.raises(KeyError, match="unknown_action"):
        await route_packet(
            {
                "action": "unknown_action",
                "tenant": "test",
                "payload": {},
            }
        )


@pytest.mark.asyncio
async def test_chassis_router_raises_value_error_for_missing_action():
    from l9.chassis.router import route_packet

    with pytest.raises(ValueError, match="action"):
        await route_packet({"tenant": "test", "payload": {}})
