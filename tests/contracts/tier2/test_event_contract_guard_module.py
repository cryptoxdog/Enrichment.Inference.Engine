from __future__ import annotations

import json

import pytest

from app.services.event_contract_guard import (
    EventContractError,
    emit_event,
    to_stream_dict,
    validate_event,
)

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]


def make_event(event_type: str = "enrichment_completed") -> dict[str, object]:
    return {
        "event_type": event_type,
        "entity_id": "001B000000LpT1FIAV",
        "tenant_id": "acme-corp",
        "domain": "plasticos",
        "payload": {"fields_count": 8, "confidence": 0.87, "tokens_used": 4200},
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "occurred_at": "2026-04-05T19:54:14+00:00",
    }


def test_validate_event_accepts_current_contract_event() -> None:
    normalized = validate_event(make_event())
    assert normalized["event_type"] == "enrichment_completed"


def test_validate_event_rejects_unknown_event_type() -> None:
    with pytest.raises(EventContractError, match="unsupported event_type"):
        validate_event(make_event(event_type="enrichment.completed"))


def test_to_stream_dict_serializes_payload_to_json_string() -> None:
    wire = to_stream_dict(make_event())
    assert isinstance(wire["payload"], str)
    parsed = json.loads(wire["payload"])
    assert parsed["fields_count"] == 8


def test_emit_event_swallows_failure_when_non_critical() -> None:
    def failing_emitter(_: dict[str, str]) -> None:
        raise ConnectionError("Redis unavailable")

    result = emit_event(failing_emitter, make_event(), raise_on_failure=False)
    assert result["emitted"] is False
    assert "error" in result


def test_emit_event_raises_when_requested() -> None:
    def failing_emitter(_: dict[str, str]) -> None:
        raise ConnectionError("Redis unavailable")

    with pytest.raises(ConnectionError):
        emit_event(failing_emitter, make_event(), raise_on_failure=True)
