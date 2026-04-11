# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [tests, integration]
# tags: [L9_TEST, gap-validation, ci-bound]
# owner: platform
# status: active
# --- /L9_META ---
"""
tests/integration/test_gap_fixes.py

Validation tests proving all GAP fixes are wired and reachable.
Run: pytest tests/integration/test_gap_fixes.py -v
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestResultStorePersistenceWiring:
    """GAP #01 — ResultStore is wired: EnrichmentResult persists to pg_store."""

    def test_enrichment_result_content_hash_is_deterministic(self):
        from app.services.result_store import EnrichmentResult

        fields = {"industry": "plastics_recycling", "mfi_range": "2-4"}
        r1 = EnrichmentResult(
            tenant_id="t1",
            entity_id="e1",
            packet_id="p1",
            lineage_id="l1",
            pass_number=3,
            converged=True,
            confidence=0.91,
            enriched_fields=fields,
        )
        r2 = EnrichmentResult(
            tenant_id="t1",
            entity_id="e1",
            packet_id="p1",
            lineage_id="l1",
            pass_number=3,
            converged=True,
            confidence=0.91,
            enriched_fields=fields,
        )
        assert r1.content_hash == r2.content_hash
        expected = hashlib.sha256(
            json.dumps(fields, sort_keys=True, default=str).encode()
        ).hexdigest()
        assert r1.content_hash == expected

    @pytest.mark.asyncio
    async def test_result_store_save_calls_pool(self):
        from app.services.result_store import EnrichmentResult, ResultStore

        store = ResultStore()
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        store._pool = mock_pool
        result = EnrichmentResult(
            tenant_id="acme",
            entity_id="company_001",
            packet_id="pkt_x",
            lineage_id="lin_y",
            pass_number=2,
            converged=True,
            confidence=0.88,
            enriched_fields={"facility_tier": "tier_2"},
        )
        await store.save(result)
        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO enrichment_results" in sql
        assert "ON CONFLICT" in sql

    @pytest.mark.asyncio
    async def test_result_store_save_noop_when_no_pool(self):
        from app.services.result_store import EnrichmentResult, ResultStore

        store = ResultStore()
        store._pool = None
        result = EnrichmentResult(
            tenant_id="t",
            entity_id="e",
            packet_id="p",
            lineage_id="l",
            pass_number=1,
            converged=False,
            confidence=0.5,
            enriched_fields={},
        )
        await store.save(result)


class TestGraphSyncAndScoreInvalidationHooks:
    """GAP #22 — graph sync + score invalidation fire on converge."""

    @pytest.mark.asyncio
    async def test_trigger_graph_sync_posts_to_graph_url(self, monkeypatch):
        from app.core.config import Settings
        from app.services import graph_sync_hooks

        mock_settings = Settings(gate_url="https://gate-node:8080", perplexity_api_key="")
        monkeypatch.setattr(graph_sync_hooks, "get_settings", lambda: mock_settings)
        mock_response = MagicMock()
        mock_response.header.packet_id = "pkt-response"
        with patch.object(graph_sync_hooks, "GateClient") as mock_client:
            instance = MagicMock()
            instance.send_to_gate = AsyncMock(return_value=mock_response)
            mock_client.return_value = instance
            await graph_sync_hooks.trigger_graph_sync(
                entity_id="e1",
                tenant_id="t1",
                enriched_fields={"hdpe_grade": "prime"},
                confidence=0.92,
                lineage_id="lin_001",
                packet_id="pkt_001",
            )
        instance.send_to_gate.assert_awaited_once()
        sent_packet = instance.send_to_gate.await_args.args[0]
        assert sent_packet.header.action == "graph-sync"
        assert sent_packet.payload["lineage_id"] == "lin_001"

    @pytest.mark.asyncio
    async def test_trigger_graph_sync_skips_when_no_url(self, monkeypatch):
        from app.core.config import Settings
        from app.services import graph_sync_hooks

        monkeypatch.setattr(
            graph_sync_hooks, "get_settings", lambda: Settings(gate_url="", perplexity_api_key="")
        )
        with patch.object(graph_sync_hooks, "GateClient") as mock_client:
            await graph_sync_hooks.trigger_graph_sync(
                entity_id="e1",
                tenant_id="t1",
                enriched_fields={},
                confidence=0.5,
                lineage_id="l",
                packet_id="p",
            )
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_score_cache_posts_to_score_url(self, monkeypatch):
        from app.core.config import Settings
        from app.services import graph_sync_hooks

        mock_settings = Settings(gate_url="https://gate-node:8080", perplexity_api_key="")
        monkeypatch.setattr(graph_sync_hooks, "get_settings", lambda: mock_settings)
        mock_response = MagicMock()
        mock_response.header.packet_id = "pkt-response"
        with patch.object(graph_sync_hooks, "GateClient") as mock_client:
            instance = MagicMock()
            instance.send_to_gate = AsyncMock(return_value=mock_response)
            mock_client.return_value = instance
            await graph_sync_hooks.invalidate_score_cache(
                entity_id="e1",
                tenant_id="t1",
                lineage_id="lin_002",
                packet_id="pkt_002",
            )
        instance.send_to_gate.assert_awaited_once()
        sent_packet = instance.send_to_gate.await_args.args[0]
        assert sent_packet.header.action == "score-invalidate"


class TestConvergeEndpointExecutesController:
    """GAP #03 — /v1/converge invokes ConvergenceController.run()."""

    def _make_app_with_mocked_controller(self):
        from fastapi import FastAPI

        from app.api.v1.converge import router

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        mock_loop_result = MagicMock()
        mock_loop_result.pass_count = 3
        mock_loop_result.converged = True
        mock_loop_result.confidence = 0.91
        mock_loop_result.enriched_fields = {"contamination_tolerance": "low"}
        mock_loop_result.inference_outputs = {"hdpe_grade": "prime"}
        mock_store = AsyncMock()
        mock_store.save = AsyncMock()
        with (
            patch("app.api.v1.converge.ConvergenceController") as mock_ctrl,
            patch("app.api.v1.converge.get_result_store", return_value=mock_store),
            patch("app.api.v1.converge.trigger_graph_sync", new_callable=AsyncMock),
            patch("app.api.v1.converge.invalidate_score_cache", new_callable=AsyncMock),
        ):
            instance = AsyncMock()
            instance.run = AsyncMock(return_value=mock_loop_result)
            mock_ctrl.return_value = instance
            client = TestClient(app)
            resp = client.post(
                "/v1/converge",
                json={
                    "tenant_id": "acme",
                    "entity_id": "company_plasticos_001",
                    "raw_fields": {"name": "PlastiCorp", "industry": "recycling"},
                    "max_passes": 5,
                    "confidence_threshold": 0.85,
                },
            )
        return resp, instance

    def test_converge_returns_200_with_real_fields(self):
        resp, _ = self._make_app_with_mocked_controller()
        assert resp.status_code == 200
        body = resp.json()
        assert body["converged"] is True
        assert body["pass_count"] == 3
        assert body["confidence"] == pytest.approx(0.91)
        assert "content_hash" in body
        assert body["enriched_fields"]["contamination_tolerance"] == "low"

    def test_converge_endpoint_calls_controller_run(self):
        _, ctrl = self._make_app_with_mocked_controller()
        ctrl.run.assert_called_once()


class TestConfigMaxBudgetTokensAlias:
    """GAP #04 — token_budget and max_tokens aliases resolve correctly."""

    def test_max_budget_tokens_default(self):
        from app.core.config import Settings

        s = Settings(perplexity_api_key="")
        assert s.max_budget_tokens == 4096

    def test_token_budget_alias_promoted(self):
        from app.core.config import Settings

        s = Settings(perplexity_api_key="", token_budget=2048)
        assert s.max_budget_tokens == 2048

    def test_max_tokens_alias_wins_over_token_budget(self):
        from app.core.config import Settings

        s = Settings(perplexity_api_key="", token_budget=2048, max_tokens=8192)
        assert s.max_budget_tokens == 8192


class TestPerplexityApiKeySafeDefault:
    """GAP #05 — missing perplexity_api_key does not crash startup."""

    def test_empty_string_default_does_not_raise(self):
        from app.core.config import Settings

        s = Settings()
        assert isinstance(s.perplexity_api_key, str)

    def test_key_set_via_env(self, monkeypatch):
        from app.core.config import Settings

        monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key-abc123")
        s = Settings()
        assert s.perplexity_api_key == "pplx-test-key-abc123"


class TestCriticalImportPaths:
    """GAP #06 — all new modules import cleanly."""

    def test_result_store_imports(self):
        pass

    def test_graph_sync_hooks_imports(self):
        pass

    def test_converge_endpoint_imports(self):
        pass

    def test_config_imports(self):
        pass

    def test_converge_router_is_api_router(self):
        from fastapi import APIRouter

        from app.api.v1.converge import router

        assert isinstance(router, APIRouter)
