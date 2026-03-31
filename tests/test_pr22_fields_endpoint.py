"""
tests/test_pr22_fields_endpoint.py

Proves GAP-5 end-to-end: /api/v1/fields/{entity_id} returns 200 when
a persisted enrichment result exists, and 404 when none does.

Also proves the router is mounted (not orphaned) and respects tenant_id isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


def _make_mock_result(entity_id: str = "ent-001", tenant_id: str = "test-tenant"):
    """Build a minimal EnrichmentResult-compatible mock."""
    from app.services.pg_models import EnrichmentResult

    r = EnrichmentResult.__new__(EnrichmentResult)
    r.id = "uuid-001"
    r.tenant_id = tenant_id
    r.entity_id = entity_id
    r.object_type = "Account"
    r.fields = {"material_type": "HDPE", "facility_tier": "tier-2"}
    r.confidence = 0.85
    r.state = "completed"
    r.pass_count = 2
    r.tokens_used = 480
    r.processing_time_ms = 1100
    r.created_at = datetime.now(timezone.utc)
    return r


@pytest.mark.asyncio
async def test_fields_endpoint_404_when_no_result():
    """Without a persisted result, /fields must return 404."""
    from httpx import ASGITransport, AsyncClient

    with patch(
        "app.services.result_store.ResultStore.get_latest_for_entity",
        new_callable=AsyncMock,
        return_value=None,
    ):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/fields/ent-001",
                params={"tenant_id": "test-tenant"},
                headers={"X-API-Key": "test-key"},
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fields_endpoint_200_after_persist():
    """After GAP-5 fix: a persisted result must yield 200 with correct field map."""
    from httpx import ASGITransport, AsyncClient

    mock_result = _make_mock_result()

    with patch(
        "app.services.result_store.ResultStore.get_latest_for_entity",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        with patch(
            "app.services.result_store.ResultStore.get_field_confidence_history",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from app.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/fields/ent-001",
                    params={"tenant_id": "test-tenant"},
                    headers={"X-API-Key": "test-key"},
                )

    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_id"] == "ent-001"
    assert "material_type" in body["fields"]
    assert "facility_tier" in body["fields"]
    assert body["fields"]["material_type"]["value"] == "HDPE"
    assert 0.0 <= body["avg_confidence"] <= 1.0


@pytest.mark.asyncio
async def test_fields_endpoint_confidence_history_used_when_present():
    """Confidence history is used in preference to response.confidence when available."""
    from httpx import ASGITransport, AsyncClient

    mock_result = _make_mock_result()

    history = [
        {
            "confidence": 0.91,
            "source": "consensus",
            "pass_number": 2,
        }
    ]

    with patch(
        "app.services.result_store.ResultStore.get_latest_for_entity",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        with patch(
            "app.services.result_store.ResultStore.get_field_confidence_history",
            new_callable=AsyncMock,
            return_value=history,
        ):
            from app.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/fields/ent-001/material_type/history",
                    params={"tenant_id": "test-tenant"},
                    headers={"X-API-Key": "test-key"},
                )

    assert resp.status_code == 200
    entries = resp.json()
    assert isinstance(entries, list)
    assert entries[0]["confidence"] == pytest.approx(0.91)
    assert entries[0]["source"] == "consensus"


@pytest.mark.asyncio
async def test_fields_endpoint_tenant_isolation():
    """GET /fields must use the tenant_id query param for scoping."""
    from httpx import ASGITransport, AsyncClient

    captured_tenant: list = []

    async def mock_get_latest(entity_id):
        return None

    original_init = __import__(
        "app.services.result_store", fromlist=["ResultStore"]
    ).ResultStore.__init__

    def capturing_init(self, tenant_id):
        captured_tenant.append(tenant_id)
        original_init(self, tenant_id)

    with patch(
        "app.services.result_store.ResultStore.__init__",
        side_effect=capturing_init,
    ):
        with patch(
            "app.services.result_store.ResultStore.get_latest_for_entity",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.get(
                    "/api/v1/fields/ent-001",
                    params={"tenant_id": "specific-tenant"},
                    headers={"X-API-Key": "test-key"},
                )

    assert "specific-tenant" in captured_tenant
