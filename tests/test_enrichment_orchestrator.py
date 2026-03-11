"""Tests for app/engines/enrichment_orchestrator.py

Covers: Single-pass enrichment pipeline (10 steps), circuit breaker,
        idempotency, response assembly.

Source: ~350 lines | Target coverage: 70%
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.enrichment_orchestrator import enrich_entity
from app.models.schemas import EnrichRequest, EnrichResponse


class TestEnrichmentOrchestrator:
    """Tests for 10-step single-pass orchestration."""

    @pytest.fixture
    def basic_request(self):
        return EnrichRequest(
            entity={"Name": "Acme Recycling", "polymer_type": "HDPE"},
            object_type="Account",
            objective="Enrich plastics recycling data",
        )

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.pplx_api_key = "test-key"
        settings.pplx_model = "sonar"
        settings.default_max_variations = 5
        return settings

    @pytest.fixture
    def mock_kb_resolver(self):
        resolver = MagicMock()
        resolver.resolve = MagicMock(
            return_value={
                "fragments": ["polymers.hdpe"],
                "content": "HDPE: MFI 0.1-25 g/10min",
            }
        )
        return resolver

    @pytest.mark.asyncio
    async def test_returns_enrich_response(self, basic_request, mock_settings, mock_kb_resolver):
        with patch(
            "app.engines.enrichment_orchestrator.call_perplexity", new_callable=AsyncMock
        ) as mock_pplx:
            mock_pplx.return_value = {
                "confidence": 0.85,
                "polymer_type": "HDPE",
                "mfi_range": "0.5-3.0",
            }
            response = await enrich_entity(basic_request, mock_settings, mock_kb_resolver)
            assert isinstance(response, EnrichResponse)

    @pytest.mark.asyncio
    async def test_response_has_fields(self, basic_request, mock_settings, mock_kb_resolver):
        with patch(
            "app.engines.enrichment_orchestrator.call_perplexity", new_callable=AsyncMock
        ) as mock_pplx:
            mock_pplx.return_value = {
                "confidence": 0.85,
                "polymer_type": "HDPE",
                "mfi_range": "0.5-3.0",
            }
            response = await enrich_entity(basic_request, mock_settings, mock_kb_resolver)
            assert response.fields is not None

    @pytest.mark.asyncio
    async def test_response_has_confidence(self, basic_request, mock_settings, mock_kb_resolver):
        with patch(
            "app.engines.enrichment_orchestrator.call_perplexity", new_callable=AsyncMock
        ) as mock_pplx:
            mock_pplx.return_value = {"confidence": 0.85, "x": "val"}
            response = await enrich_entity(basic_request, mock_settings, mock_kb_resolver)
            assert 0.0 <= response.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_response_has_processing_time(
        self, basic_request, mock_settings, mock_kb_resolver
    ):
        with patch(
            "app.engines.enrichment_orchestrator.call_perplexity", new_callable=AsyncMock
        ) as mock_pplx:
            mock_pplx.return_value = {"confidence": 0.85, "x": "val"}
            response = await enrich_entity(basic_request, mock_settings, mock_kb_resolver)
            assert response.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_idempotency_key_caching(self, basic_request, mock_settings, mock_kb_resolver):
        basic_request.idempotency_key = "test-key-123"
        idem_store = MagicMock()
        idem_store.get = AsyncMock(return_value=None)
        idem_store.set = AsyncMock()

        with patch(
            "app.engines.enrichment_orchestrator.call_perplexity", new_callable=AsyncMock
        ) as mock_pplx:
            mock_pplx.return_value = {"confidence": 0.85, "x": "val"}
            await enrich_entity(basic_request, mock_settings, mock_kb_resolver, idem_store)
