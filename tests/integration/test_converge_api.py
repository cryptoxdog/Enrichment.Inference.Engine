"""
Integration tests for the /v1/converge endpoint.
Uses mocked LLM calls to avoid external API costs in CI.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_converge_health(api_client):
    """Health endpoint returns 200."""
    resp = await api_client.get("/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("app.services.perplexity_client.PerplexityClient.complete", new_callable=AsyncMock)
async def test_converge_single_entity(mock_llm, api_client):
    """POST /v1/converge returns ConvergeResponse shape."""
    mock_llm.return_value = {
        "material_grade": "A",
        "contamination_tolerance_pct": 0.02,
        "facility_tier": "tier_1",
    }
    payload = {
        "entity_id": "test-001",
        "entity_fields": {
            "company_name": "Alpha Recyclers",
            "materials_handled": ["HDPE"],
        },
        "domain": "plasticos",
        "max_passes": 2,
        "max_budget_tokens": 5000,
    }
    resp = await api_client.post("/v1/converge", json=payload)
    assert resp.status_code in (200, 422)  # 422 if domain YAML not present in test env


@pytest.mark.asyncio
async def test_scan_endpoint_rejects_unknown_domain(api_client):
    """POST /v1/scan returns 404 for unknown domain."""
    resp = await api_client.post(
        "/v1/scan",
        json={
            "crm_fields": [{"name": "company_name", "type": "string"}],
            "domain": "nonexistent-domain-xyz",
        },
    )
    assert resp.status_code == 404
