from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ASYNCAPI_PATH = REPO_ROOT / "docs/contracts/events/asyncapi.yaml"


class EventContractError(ValueError):
    """Raised when an event violates the current event contract."""


def _load_yaml(path: Path) -> dict[str, Any]:
    result = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(result) if result else {}


@lru_cache(maxsize=1)
def _asyncapi() -> dict[str, Any]:
    return _load_yaml(ASYNCAPI_PATH)


def allowed_event_types() -> set[str]:
    return {message["name"] for message in _asyncapi()["components"]["messages"].values()}


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise EventContractError("event must be an object")

    required_fields = {"event_type", "entity_id", "tenant_id", "correlation_id", "occurred_at"}
    missing = [field for field in sorted(required_fields) if field not in event]
    if missing:
        raise EventContractError(f"event missing required fields: {missing}")

    event_type = event["event_type"]
    if event_type not in allowed_event_types():
        raise EventContractError(f"unsupported event_type: {event_type}")

    if not isinstance(event["entity_id"], str) or not event["entity_id"]:
        raise EventContractError("entity_id must be a non-empty string")
    if not isinstance(event["tenant_id"], str) or not event["tenant_id"]:
        raise EventContractError("tenant_id must be a non-empty string")
    if not isinstance(event["correlation_id"], str) or not event["correlation_id"]:
        raise EventContractError("correlation_id must be a non-empty string")
    if "domain" in event and event["domain"] is not None and not isinstance(event["domain"], str):
        raise EventContractError("domain must be a string or null")

    occurred_at = event["occurred_at"]
    if not isinstance(occurred_at, str) or not occurred_at:
        raise EventContractError("occurred_at must be a non-empty ISO8601 string")
    datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))

    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        raise EventContractError("payload must be an object")

    return {
        "event_type": event_type,
        "entity_id": event["entity_id"],
        "tenant_id": event["tenant_id"],
        "domain": event.get("domain"),
        "payload": dict(payload),
        "correlation_id": event["correlation_id"],
        "occurred_at": occurred_at,
    }


def to_stream_dict(event: dict[str, Any]) -> dict[str, str]:
    normalized = validate_event(event)
    return {
        "event_type": normalized["event_type"],
        "entity_id": normalized["entity_id"],
        "tenant_id": normalized["tenant_id"],
        "domain": "" if normalized["domain"] is None else normalized["domain"],
        "payload": json.dumps(normalized["payload"], sort_keys=True, separators=(",", ":")),
        "correlation_id": normalized["correlation_id"],
        "occurred_at": normalized["occurred_at"],
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
