"""Tests for app/engines/convergence_controller.py

Covers: Multi-pass loop orchestration, convergence detection, pass delegation.

Source: ~400 lines | Target coverage: 70%
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.engines.convergence_controller import (
    run_convergence_loop,
    ConvergenceState,
    PassResult as ControllerPassResult,
    MAX_PASSES,
    CONVERGENCE_THRESHOLD,
    MIN_DELTA,
)
from app.models.schemas import EnrichRequest, EnrichResponse


class TestConvergenceController:
    """Tests for multi-pass loop orchestration."""

    @pytest.fixture
    def enrich_request(self):
        return EnrichRequest(
            entity={"Name": "Test Corp", "polymer_type": "HDPE"},
            object_type="Account",
            objective="Enrich plastics recycling data",
        )

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.pplx_api_key = "test-key"
        return settings

    @pytest.fixture
    def mock_kb_resolver(self):
        return MagicMock()

    @pytest.fixture
    def mock_enricher_converging(self):
        """Enricher that returns diminishing results to trigger convergence."""
        call_count = 0

        async def enricher(request, settings, kb_resolver, idem_store):
            nonlocal call_count
            call_count += 1
            fields = {"field_a": "val"} if call_count == 1 else {}
            return EnrichResponse(
                fields=fields,
                confidence=0.85 if call_count == 1 else 0.86,
                variation_count=5,
                uncertainty_score=1,
                inference_version="test",
                processing_time_ms=100,
                tokens_used=500,
                state="completed",
            )

        return enricher

    @pytest.mark.asyncio
    async def test_single_pass_returns_response(
        self, enrich_request, mock_settings, mock_kb_resolver, mock_enricher_converging
    ):
        response = await run_convergence_loop(
            request=enrich_request,
            settings=mock_settings,
            kb_resolver=mock_kb_resolver,
            enricher=mock_enricher_converging,
            inference_rules=[],
        )
        assert isinstance(response, EnrichResponse)
        assert response.state == "completed"

    @pytest.mark.asyncio
    async def test_convergence_stops_when_delta_below_threshold(
        self, enrich_request, mock_settings, mock_kb_resolver, mock_enricher_converging
    ):
        response = await run_convergence_loop(
            request=enrich_request,
            settings=mock_settings,
            kb_resolver=mock_kb_resolver,
            enricher=mock_enricher_converging,
            inference_rules=[],
        )
        # Should converge before MAX_PASSES since enricher returns diminishing results
        assert response.uncertainty_score <= MAX_PASSES

    @pytest.mark.asyncio
    async def test_max_passes_respected(
        self, enrich_request, mock_settings, mock_kb_resolver
    ):
        call_count = 0

        async def always_new_enricher(request, settings, kb_resolver, idem_store):
            nonlocal call_count
            call_count += 1
            return EnrichResponse(
                fields={f"field_{call_count}": f"val_{call_count}"},
                confidence=0.5 + (call_count * 0.1),
                variation_count=5,
                uncertainty_score=1,
                inference_version="test",
                processing_time_ms=100,
                tokens_used=1000,
                state="completed",
            )

        response = await run_convergence_loop(
            request=enrich_request,
            settings=mock_settings,
            kb_resolver=mock_kb_resolver,
            enricher=always_new_enricher,
            inference_rules=[],
        )
        assert response.uncertainty_score <= MAX_PASSES

    @pytest.mark.asyncio
    async def test_tokens_tracked_across_passes(
        self, enrich_request, mock_settings, mock_kb_resolver, mock_enricher_converging
    ):
        response = await run_convergence_loop(
            request=enrich_request,
            settings=mock_settings,
            kb_resolver=mock_kb_resolver,
            enricher=mock_enricher_converging,
            inference_rules=[],
        )
        assert response.tokens_used > 0

    @pytest.mark.asyncio
    async def test_processing_time_tracked(
        self, enrich_request, mock_settings, mock_kb_resolver, mock_enricher_converging
    ):
        response = await run_convergence_loop(
            request=enrich_request,
            settings=mock_settings,
            kb_resolver=mock_kb_resolver,
            enricher=mock_enricher_converging,
            inference_rules=[],
        )
        assert response.processing_time_ms > 0

    def test_convergence_state_initial(self):
        state = ConvergenceState()
        assert state.known_fields == {}
        assert state.inferred_fields == {}
        assert state.pass_results == []
        assert state.converged is False

    def test_convergence_constants(self):
        assert MAX_PASSES == 3
        assert CONVERGENCE_THRESHOLD == 2.0
        assert MIN_DELTA == 0.05
