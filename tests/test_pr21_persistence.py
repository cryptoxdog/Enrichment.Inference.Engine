"""
tests/test_pr21_persistence.py

Proves GAP-5: ResultStore.persist_enrich_response is wired and callable.
Specifically validates that:
  - ResultStore.__init__ accepts tenant_id
  - persist_enrich_response delegates to pg_store.save_enrichment_result
  - the pg_store call receives correct tenant_id and entity_id
  - handle_enrich calls persist after a completed response
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import EnrichResponse
from app.services.result_store import ResultStore


@pytest.mark.asyncio
async def test_result_store_persist_delegates_to_pg_store():
    """ResultStore.persist_enrich_response must call pg_store.save_enrichment_result."""
    mock_record = MagicMock()
    mock_record.id = uuid.uuid4()

    with patch(
        "app.services.result_store.pg_store.save_enrichment_result",
        new_callable=AsyncMock,
        return_value=mock_record,
    ) as mock_save:
        store = ResultStore(tenant_id="acme")
        response = EnrichResponse(
            fields={"material_type": "HDPE", "mfi_range": "2-4 g/10min"},
            confidence=0.87,
            state="completed",
            tokens_used=620,
            processing_time_ms=1400,
            pass_count=2,
        )

        result_id = await store.persist_enrich_response(
            response=response,
            entity_id="ent-001",
            object_type="Account",
            domain="plastics",
        )

        mock_save.assert_awaited_once()
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["tenant_id"] == "acme"
        assert call_kwargs["entity_id"] == "ent-001"
        assert call_kwargs["object_type"] == "Account"
        assert call_kwargs["domain"] == "plastics"
        assert call_kwargs["confidence"] == pytest.approx(0.87)
        assert result_id == mock_record.id


@pytest.mark.asyncio
async def test_result_store_extracts_field_confidence_from_feature_vector():
    """persist_enrich_response extracts per-field confidence from feature_vector."""
    mock_record = MagicMock()
    mock_record.id = uuid.uuid4()

    response = EnrichResponse(
        fields={"material_type": "PP", "contamination_tolerance": "low"},
        confidence=0.75,
        state="completed",
        tokens_used=300,
        processing_time_ms=800,
        pass_count=1,
        feature_vector={
            "confidence_tracking": {
                "material_type": {"latest_confidence": 0.92},
                "contamination_tolerance": {"latest_confidence": 0.68},
            }
        },
    )

    captured: dict = {}

    async def capture_save(**kwargs):
        captured.update(kwargs)
        return mock_record

    with patch(
        "app.services.result_store.pg_store.save_enrichment_result",
        side_effect=capture_save,
    ):
        store = ResultStore(tenant_id="tenant-x")
        await store.persist_enrich_response(
            response=response,
            entity_id="ent-002",
            object_type="Lead",
        )

    assert captured.get("field_confidence_map") == {
        "material_type": 0.92,
        "contamination_tolerance": 0.68,
    }


@pytest.mark.asyncio
async def test_handle_enrich_calls_persist_on_completed():
    """GAP-5: handle_enrich must call ResultStore.persist_enrich_response when state=completed."""
    mock_response = EnrichResponse(
        fields={"material_type": "HDPE"},
        confidence=0.84,
        state="completed",
        tokens_used=500,
        processing_time_ms=1000,
        pass_count=1,
    )

    persist_calls: list = []

    async def mock_persist_and_sync(tenant, payload, result, object_type):
        persist_calls.append({"tenant": tenant, "payload": payload, "result": result})

    with patch(
        "app.engines.handlers.enrich_entity",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch(
            "app.engines.handlers._persist_and_sync",
            side_effect=mock_persist_and_sync,
        ):
            from app.engines.handlers import handle_enrich

            result = await handle_enrich(
                "tenant-acme",
                {
                    "entity": {"id": "ent-003", "Name": "Acme Plastics"},
                    "object_type": "Account",
                    "objective": "Enrich plastics supplier",
                },
            )

    assert result["state"] == "completed"
    assert len(persist_calls) == 1
    assert persist_calls[0]["tenant"] == "tenant-acme"


@pytest.mark.asyncio
async def test_handle_enrich_skips_persist_on_failed():
    """handle_enrich must NOT call persist when state=failed (no partial writes)."""
    mock_response = EnrichResponse(
        fields={},
        confidence=0.0,
        state="failed",
        failure_reason="sonar_timeout",
        tokens_used=0,
        processing_time_ms=5000,
        pass_count=0,
    )

    persist_calls: list = []

    async def mock_persist_and_sync(tenant, payload, result, object_type):
        persist_calls.append(True)

    with patch(
        "app.engines.handlers.enrich_entity",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch(
            "app.engines.handlers._persist_and_sync",
            side_effect=mock_persist_and_sync,
        ):
            from app.engines.handlers import handle_enrich

            await handle_enrich(
                "tenant-acme",
                {
                    "entity": {"id": "ent-fail"},
                    "object_type": "Account",
                    "objective": "test",
                },
            )

    assert len(persist_calls) == 0, "persist_and_sync must not fire on failed enrichment"
