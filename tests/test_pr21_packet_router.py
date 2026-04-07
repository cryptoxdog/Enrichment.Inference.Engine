"""
tests/test_pr21_packet_router.py

Proves GAP-1 and GAP-6:
  - dispatch_to_score does NOT exist in packet_router (confirms broken ref is gone)
  - notify_graph_sync builds a valid PacketEnvelope and POSTs to /v1/execute
  - notify_score_invalidate fires a fire-and-forget envelope with correct action
  - get_router() returns a singleton PacketRouter
  - orchestration_layer no longer imports the non-existent dispatch_to_score
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.packet_router import NodeTarget, PacketRouter, _build_envelope, get_router


def test_dispatch_to_score_symbol_absent():
    """GAP-1: dispatch_to_score must not exist in packet_router."""
    import app.engines.packet_router as pr

    assert not hasattr(pr, "dispatch_to_score"), (
        "dispatch_to_score must be absent — orchestration_layer must use "
        "get_router().notify_score_invalidate() instead"
    )


def test_orchestration_layer_does_not_import_dispatch_to_score():
    """GAP-1: orchestration_layer source must not contain a dispatch_to_score import."""
    import ast
    import pathlib

    src_path = pathlib.Path("app/engines/orchestration_layer.py")
    if not src_path.exists():
        pytest.skip("orchestration_layer.py not found in cwd")
    tree = ast.parse(src_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.names:
                names = [alias.name for alias in node.names]
                assert "dispatch_to_score" not in names, (
                    f"Stale import 'dispatch_to_score' found at line {node.lineno}"
                )


def test_build_envelope_structure():
    """PacketEnvelope must contain header with packet_id, tenant_id, content_hash."""
    env = _build_envelope(
        action="graph_sync",
        tenant_id="tenant-x",
        payload={"entity_id": "ent-001", "fields": {"material_type": "HDPE"}},
    )
    assert "header" in env
    assert env["header"]["action"] == "graph_sync"
    assert env["header"]["tenant_id"] == "tenant-x"
    assert "packet_id" in env["header"]
    assert "content_hash" in env["header"]
    assert "created_at" in env["header"]
    assert env["header"]["content_hash"] == env["content_hash"]


@pytest.mark.asyncio
async def test_notify_graph_sync_posts_to_graph_node():
    """GAP-6: notify_graph_sync must POST a PacketEnvelope to the graph node."""
    router = PacketRouter(node_urls={NodeTarget.GRAPH.value: "https://graph-node:8001"})

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "synced"}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(
        router._http, "post", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_post:
        result = await router.notify_graph_sync(
            tenant_id="tenant-acme",
            entity_id="ent-001",
            fields={"material_type": "HDPE", "mfi_range": "2-4"},
            domain="plastics",
        )
        assert result == {"status": "synced"}
        call_json = mock_post.call_args.kwargs["json"]
    assert call_json["header"]["action"] == "graph_sync"
    assert call_json["header"]["tenant_id"] == "tenant-acme"
    assert call_json["payload"]["entity_id"] == "ent-001"
    assert call_json["payload"]["domain"] == "plastics"


@pytest.mark.asyncio
async def test_notify_graph_sync_returns_none_when_no_graph_url():
    """notify_graph_sync returns None if graph node URL not configured."""
    router = PacketRouter(node_urls={})
    result = await router.notify_graph_sync(
        tenant_id="t", entity_id="e", fields={}, domain="plastics"
    )
    assert result is None


def test_notify_score_invalidate_is_fire_and_forget():
    """GAP-1: notify_score_invalidate must call route_fire_and_forget (non-blocking)."""
    router = PacketRouter(node_urls={NodeTarget.SCORE.value: "https://score-node:8002"})

    fired: list = []

    def capture_fff(target, action, tenant_id, payload, correlation_id=None):
        fired.append({"target": target, "action": action, "tenant_id": tenant_id})

    router.route_fire_and_forget = capture_fff

    import asyncio

    asyncio.get_event_loop().run_until_complete(
        router.notify_score_invalidate(tenant_id="tenant-x", entity_id="ent-007", domain="plastics")
    )

    assert len(fired) == 1
    assert fired[0]["action"] == "score_invalidate"
    assert fired[0]["tenant_id"] == "tenant-x"
    assert fired[0]["target"] == NodeTarget.SCORE


def test_get_router_returns_singleton():
    """get_router() must return the same PacketRouter instance per process."""
    from app.core.config import Settings

    settings = Settings(
        perplexity_api_key="test",
        api_secret_key="test",
        graph_node_url="https://graph:8001",
        score_node_url="https://score:8002",
    )

    r1 = get_router(settings)
    r2 = get_router(settings)
    assert r1 is r2, "get_router must be a singleton (lru_cache)"
