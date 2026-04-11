"""
Tier 2 — Enforcement: Transport Runtime Behavior
================================================
Proves the SDK-backed runtime preserves the node contract after the transport
cutover to TransportPacket.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from constellation_node_sdk.runtime.execution import execute_transport_packet
from constellation_node_sdk.runtime.handlers import clear_handlers, register_handler
from constellation_node_sdk.transport import create_transport_packet

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]

CURRENT_NODE = "enrichment-engine"
VALID_ACTIONS = (
    "converge",
    "discover",
    "enrich",
    "enrich-and-sync",
    "enrichbatch",
    "simulate",
    "writeback",
)


@pytest.fixture(autouse=True)
def reset_registry():
    clear_handlers()
    yield
    clear_handlers()


class TestActionRegistryEnforcement:
    @pytest.mark.asyncio
    async def test_unknown_action_raises(self) -> None:
        packet = create_transport_packet(
            action="unknown-action",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="gate",
        )

        with pytest.raises(ValueError, match="unknown-action"):
            await execute_transport_packet(packet, node_name=CURRENT_NODE, dev_mode=True)

    @pytest.mark.asyncio
    async def test_registered_action_executes(self) -> None:
        handler = AsyncMock(return_value={"status": "completed"})
        register_handler("enrich", handler)
        packet = create_transport_packet(
            action="enrich",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="gate",
        )

        response = await execute_transport_packet(
            packet,
            node_name=CURRENT_NODE,
            dev_mode=True,
            allowed_actions=VALID_ACTIONS,
        )

        assert response.payload["status"] == "completed"
        handler.assert_awaited_once_with("acme-corp", {"entity_id": "e-001"})


class TestLineageAndHopTrace:
    @pytest.mark.asyncio
    async def test_response_generation_increments_by_one(self) -> None:
        register_handler("discover", AsyncMock(return_value={"status": "completed"}))
        packet = create_transport_packet(
            action="discover",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="gate",
        )

        response = await execute_transport_packet(
            packet,
            node_name=CURRENT_NODE,
            dev_mode=True,
            allowed_actions=VALID_ACTIONS,
        )

        assert response.lineage.generation == packet.lineage.generation + 1
        assert response.lineage.parent_id == packet.header.packet_id
        assert response.lineage.root_id == packet.lineage.root_id

    @pytest.mark.asyncio
    async def test_hop_trace_appends_current_node(self) -> None:
        register_handler("simulate", AsyncMock(return_value={"status": "completed"}))
        packet = create_transport_packet(
            action="simulate",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="gate",
        )

        response = await execute_transport_packet(
            packet,
            node_name=CURRENT_NODE,
            dev_mode=True,
            allowed_actions=VALID_ACTIONS,
        )

        last_hop = response.hop_trace[-1]
        assert last_hop.node == CURRENT_NODE
        assert last_hop.action == "simulate"
        assert last_hop.status == "completed"


class TestReplyToPreservation:
    @pytest.mark.asyncio
    async def test_destination_node_uses_ingress_reply_to(self) -> None:
        register_handler("converge", AsyncMock(return_value={"status": "completed"}))
        packet = create_transport_packet(
            action="converge",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="route-engine",
        )

        response = await execute_transport_packet(
            packet,
            node_name=CURRENT_NODE,
            dev_mode=True,
            allowed_actions=VALID_ACTIONS,
        )

        assert response.address.destination_node == "route-engine"
        assert response.address.source_node == CURRENT_NODE
        assert response.address.reply_to == CURRENT_NODE


class TestPacketAwareHandlers:
    @pytest.mark.asyncio
    async def test_three_argument_handler_receives_packet(self) -> None:
        captured = {}

        async def handler(tenant: str, payload: dict[str, object], packet) -> dict[str, object]:
            captured["tenant"] = tenant
            captured["payload"] = payload
            captured["packet_id"] = packet.header.packet_id
            return {"status": "completed"}

        register_handler("enrich-and-sync", handler)
        packet = create_transport_packet(
            action="enrich-and-sync",
            payload={"entity_id": "e-001"},
            tenant="acme-corp",
            source_node="gate",
            destination_node=CURRENT_NODE,
            reply_to="gate",
        )

        response = await execute_transport_packet(
            packet,
            node_name=CURRENT_NODE,
            dev_mode=True,
            allowed_actions=VALID_ACTIONS,
        )

        assert response.payload["status"] == "completed"
        assert captured["tenant"] == "acme-corp"
        assert captured["payload"] == {"entity_id": "e-001"}
        assert captured["packet_id"] == packet.header.packet_id
