"""Pipeline unit tests with mocked Perplexity."""
from __future__ import annotations

import pytest


@pytest.fixture
def mock_perplexity(monkeypatch):
    """Patch query_perplexity to return a canned response."""
    from app import perplexity_client
    from app.perplexity_client import SonarResponse

    async def _fake(payload, api_key, breaker, timeout=120):
        return SonarResponse(
            data={
                "material_type": "HDPE",
                "grade": "Blow Molding",
                "confidence": 0.85,
            },
            tokens_used=150,
        )

    monkeypatch.setattr(perplexity_client, "query_perplexity", _fake)


def test_enrich_with_mock(client, api_key, mock_perplexity):
    resp = client.post(
        "/api/v1/enrich",
        json={"entity": {"name": "HDPE resin", "polymer": "HDPE"}},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "confidence" in data
    assert data["variations_attempted"] >= 1
