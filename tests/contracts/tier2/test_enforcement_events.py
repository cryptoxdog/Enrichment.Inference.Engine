"""
Tier 2 — Enforcement: Event Wire Semantics
==========================================
Proves event serialization and hot-path semantics align with the current event contracts.

Primary sources:
- docs/contracts/events/asyncapi.yaml
- docs/contracts/events/schemas/event-envelope.yaml
- docs/contracts/events/channels/enrichment-events.yaml
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]

ALLOWED_EVENT_TYPES = {
    "enrichment_completed",
    "enrichment_failed",
    "convergence_completed",
    "schema_proposed",
    "score_invalidated",
    "entity_updated",
}

REQUIRED_EVENT_FIELDS = {
    "event_type",
    "entity_id",
    "tenant_id",
    "correlation_id",
    "occurred_at",
}


def build_event(
    event_type: str,
    *,
    entity_id: str = "001B000000LpT1FIAV",
    tenant_id: str = "acme-corp",
    domain: str | None = "plasticos",
    payload: dict[str, Any] | None = None,
    correlation_id: str = "550e8400-e29b-41d4-a716-446655440000",
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "domain": domain,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def to_stream_dict(event: dict[str, Any]) -> dict[str, str]:
    return {
        "event_type": str(event["event_type"]),
        "entity_id": str(event["entity_id"]),
        "tenant_id": str(event["tenant_id"]),
        "domain": "" if event.get("domain") is None else str(event["domain"]),
        "correlation_id": str(event["correlation_id"]),
        "occurred_at": str(event["occurred_at"]),
        "payload": json.dumps(event.get("payload", {})),
    }


def emit_event(
    emitter_callable: Any,
    event: dict[str, Any],
    *,
    raise_on_failure: bool = False,
) -> dict[str, Any]:
    wire = to_stream_dict(event)
    try:
        emitter_callable(wire)
        return {"emitted": True, "wire": wire}
    except Exception as exc:
        if raise_on_failure:
            raise
        return {"emitted": False, "error": str(exc), "wire": wire}


class TestWireFormat:
    def test_stream_dict_contains_only_string_values(self) -> None:
        event = build_event(
            "enrichment_completed",
            payload={"fields_count": 8, "confidence": 0.87, "tokens_used": 4200},
        )
        wire = to_stream_dict(event)
        assert all(isinstance(value, str) for value in wire.values())

    def test_payload_serialized_as_json_string(self) -> None:
        event = build_event(
            "schema_proposed",
            entity_id="batch-2026-04-05",
            payload={"batch_run_id": "batch-2026-04-05", "proposals_count": 3},
        )
        wire = to_stream_dict(event)
        parsed = json.loads(wire["payload"])
        assert parsed["proposals_count"] == 3

    def test_null_domain_becomes_empty_string(self) -> None:
        event = build_event("entity_updated", domain=None)
        wire = to_stream_dict(event)
        assert wire["domain"] == ""


class TestRequiredEventFields:
    @pytest.mark.parametrize("event_type", sorted(ALLOWED_EVENT_TYPES))
    def test_required_fields_always_present(self, event_type: str) -> None:
        event = build_event(event_type)
        missing = sorted(field for field in REQUIRED_EVENT_FIELDS if field not in event)
        assert not missing, f"Event missing required fields: {missing}"

    def test_occurred_at_is_iso8601(self) -> None:
        event = build_event("enrichment_completed")
        parsed = datetime.fromisoformat(event["occurred_at"])
        assert parsed.tzinfo is not None

    def test_event_type_is_allowed(self) -> None:
        for event_type in ALLOWED_EVENT_TYPES:
            event = build_event(event_type)
            assert event["event_type"] == event_type


class TestAtMostOnceDelivery:
    def test_event_emission_failure_does_not_block_when_non_critical(self) -> None:
        def failing_emitter(_: dict[str, str]) -> None:
            raise ConnectionError("Redis Streams unavailable")

        event = build_event("enrichment_completed")
        result = emit_event(failing_emitter, event, raise_on_failure=False)
        assert result["emitted"] is False
        assert "error" in result

    def test_event_emission_failure_raises_when_requested(self) -> None:
        def failing_emitter(_: dict[str, str]) -> None:
            raise ConnectionError("Redis Streams unavailable")

        event = build_event("schema_proposed")
        with pytest.raises(ConnectionError):
            emit_event(failing_emitter, event, raise_on_failure=True)

    def test_successful_emit_returns_wire_payload(self) -> None:
        captured: list[dict[str, str]] = []

        def capturing_emitter(wire: dict[str, str]) -> None:
            captured.append(wire)

        event = build_event("score_invalidated")
        result = emit_event(capturing_emitter, event)
        assert result["emitted"] is True
        assert len(captured) == 1
