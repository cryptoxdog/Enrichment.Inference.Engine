"""
Event Contract Tests
Source: app/services/event_emitter.py
Markers: unit
"""

from __future__ import annotations

import pytest

from tests.contracts.conftest_contracts import EVENTS_DIR, load_yaml

CONTRACTED_EVENTS = [
    "enrichment_completed",
    "enrichment_failed",
    "convergence_completed",
    "schema_proposed",
]


@pytest.fixture(scope="module")
def asyncapi_spec() -> dict:
    path = EVENTS_DIR / "asyncapi.yaml"
    if not path.exists():
        pytest.skip("asyncapi.yaml missing")
    return load_yaml(path)


@pytest.mark.unit
def test_asyncapi_version_is_3(asyncapi_spec: dict) -> None:
    v = str(asyncapi_spec.get("asyncapi", ""))
    assert v.startswith("3."), f"Expected AsyncAPI 3.x, got: {v!r}"


@pytest.mark.unit
def test_asyncapi_has_info_block(asyncapi_spec: dict) -> None:
    info = asyncapi_spec.get("info", {})
    assert info.get("title") and info.get("version")


@pytest.mark.unit
def test_asyncapi_has_channels(asyncapi_spec: dict) -> None:
    channels = asyncapi_spec.get("channels", {})
    assert channels, "asyncapi.yaml has no channels"


@pytest.mark.unit
@pytest.mark.parametrize("event_name", CONTRACTED_EVENTS)
def test_event_channel_documented(asyncapi_spec: dict, event_name: str) -> None:
    spec_str = str(asyncapi_spec)
    assert event_name in spec_str, (
        f"Event '{event_name}' not documented in asyncapi.yaml. "
        "Source: app/services/event_emitter.py"
    )


@pytest.mark.unit
def test_asyncapi_has_redis_binding(asyncapi_spec: dict) -> None:
    spec_str = str(asyncapi_spec).lower()
    has_redis = "redis" in spec_str or "stream" in spec_str
    assert has_redis, "asyncapi.yaml must document Redis Streams binding"


@pytest.mark.unit
def test_event_envelope_exists_and_has_required_fields() -> None:
    path = EVENTS_DIR / "schemas" / "event-envelope.yaml"
    if not path.exists():
        pytest.skip("event-envelope.yaml missing")
    schema = load_yaml(path)
    s = str(schema)
    for field in ["event_id", "event_type", "timestamp", "payload", "tenant"]:
        assert field in s, f"event-envelope.yaml missing field: {field}"


@pytest.mark.unit
@pytest.mark.parametrize("event_name", CONTRACTED_EVENTS)
def test_event_channel_has_example(asyncapi_spec: dict, event_name: str) -> None:
    spec_str = str(asyncapi_spec)
    if event_name not in spec_str:
        pytest.skip(f"{event_name} not in spec")
    channels = asyncapi_spec.get("channels", {})
    channel_data = channels.get(event_name, {})
    if not channel_data:
        for v in channels.values():
            if event_name in str(v):
                channel_data = v
                break
    has_example = "example" in str(channel_data).lower()
    assert has_example, (
        f"Channel '{event_name}' has no examples. "
        "Phase 3.4: message examples required for every channel."
    )


@pytest.mark.unit
def test_channels_index_lists_all_events() -> None:
    index_path = EVENTS_DIR / "channels" / "_index.yaml"
    if not index_path.exists():
        pytest.skip("_index.yaml missing")
    index_str = str(load_yaml(index_path)).lower()
    for event in CONTRACTED_EVENTS:
        stem = event.split(".")[0]
        assert stem in index_str, f"Event '{event}' not in channels/_index.yaml"


@pytest.mark.unit
def test_events_have_delivery_guarantees() -> None:
    channels_path = EVENTS_DIR / "channels" / "enrichment-events.yaml"
    if not channels_path.exists():
        pytest.skip("enrichment-events.yaml missing")
    content = channels_path.read_text().lower()
    assert any(k in content for k in ["at_least_once", "at-least-once", "delivery", "guarantee"]), (
        "enrichment-events.yaml must document delivery guarantees. Phase 1.4."
    )
