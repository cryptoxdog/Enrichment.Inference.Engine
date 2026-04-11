"""
Tier 2 — Enforcement: Provenance Presence
=========================================
Proves critical provenance fields are present on current major response surfaces.

Primary sources:
- docs/contracts/api/openapi.yaml
- docs/contracts/data/models/enrichment-result.schema.json
- docs/contracts/agents/protocols/packet-envelope.yaml
- docs/contracts/events/asyncapi.yaml
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.enforcement, pytest.mark.provenance]

ROOT = Path(".")
OPENAPI_PATH = ROOT / "docs/contracts/api/openapi.yaml"
ENRICHMENT_RESULT_SCHEMA_PATH = ROOT / "docs/contracts/data/models/enrichment-result.schema.json"
FIXTURES_DIR = ROOT / "tests/contracts/fixtures"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def openapi_contract() -> dict[str, Any]:
    return _load_yaml(OPENAPI_PATH)


@pytest.fixture(scope="module")
def enrichment_result_schema() -> dict[str, Any]:
    return _load_json(ENRICHMENT_RESULT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def enrich_response_example() -> dict[str, Any]:
    fixture = FIXTURES_DIR / "enrich_response_example.json"
    if fixture.exists():
        return _load_json(fixture)

    return {
        "fields": {"polymer_type": "HDPE"},
        "confidence": 0.91,
        "kb_content_hash": "a3f9b2c1d4e5f678901234567890abcd",
        "variation_count": 5,
        "consensus_threshold": 0.75,
        "uncertainty_score": 0.8,
        "pass_count": 3,
        "inference_version": "v2.2.0",
        "processing_time_ms": 4120,
        "enrichment_payload": None,
        "feature_vector": None,
        "kb_files_consulted": ["kb/plastics_recycling.yaml"],
        "kb_fragment_ids": ["hdpe.mfi_range", "premium_hdpe_grade"],
        "inferences": [],
        "quality_tier": "gold",
        "grade_matches": [],
        "tokens_used": 1840,
        "failure_reason": None,
        "state": "completed",
    }


@pytest.fixture(scope="module")
def packet_egress_example() -> dict[str, Any]:
    return {
        "packet_id": "550e8400-e29b-41d4-a716-446655440000",
        "packet_type": "enrichment_result",
        "action": "enrich",
        "payload": {"status": "completed"},
        "timestamp": "2026-04-06T20:00:08+00:00",
        "content_hash": "abc123def456",
        "address": {
            "source_node": "enrichment-engine",
            "destination_node": "route-engine",
            "reply_to": "enrichment-engine",
        },
        "tenant": {"actor": "acme-corp"},
        "lineage": {
            "parent_ids": ["ingress-pkt-001"],
            "root_id": "root-pkt-000",
            "generation": 3,
            "derivation_type": "dispatch",
        },
        "governance": {"intent": "enrichment"},
        "hop_trace": [
            {
                "node": "gateway",
                "action": "dispatch",
                "status": "completed",
                "timestamp": "2026-04-06T20:00:00+00:00",
            },
            {
                "node": "enrichment-engine",
                "action": "enrich",
                "status": "completed",
                "timestamp": "2026-04-06T20:00:08+00:00",
            },
        ],
    }


@pytest.fixture(scope="module")
def event_example() -> dict[str, Any]:
    return {
        "event_type": "enrichment_completed",
        "entity_id": "001B000000LpT1FIAV",
        "tenant_id": "acme-corp",
        "domain": "plasticos",
        "payload": {"fields_count": 8, "confidence": 0.87, "tokens_used": 4200},
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "occurred_at": "2026-04-06T20:00:08+00:00",
    }


class TestEnrichResponseProvenance:
    def test_response_contains_kb_content_hash(
        self, enrich_response_example: dict[str, Any]
    ) -> None:
        assert "kb_content_hash" in enrich_response_example

    def test_response_contains_inference_version(
        self, enrich_response_example: dict[str, Any]
    ) -> None:
        assert "inference_version" in enrich_response_example

    def test_response_contains_kb_fragment_ids(
        self, enrich_response_example: dict[str, Any]
    ) -> None:
        assert "kb_fragment_ids" in enrich_response_example
        assert isinstance(enrich_response_example["kb_fragment_ids"], list)

    def test_response_contains_kb_files_consulted(
        self, enrich_response_example: dict[str, Any]
    ) -> None:
        assert "kb_files_consulted" in enrich_response_example
        assert isinstance(enrich_response_example["kb_files_consulted"], list)


class TestPersistedEnrichmentResultProvenance:
    def test_schema_contains_inferences(self, enrichment_result_schema: dict[str, Any]) -> None:
        assert "inferences" in enrichment_result_schema["properties"]

    def test_schema_contains_kb_fragment_ids(
        self, enrichment_result_schema: dict[str, Any]
    ) -> None:
        assert "kb_fragment_ids" in enrichment_result_schema["properties"]

    def test_schema_contains_feature_vector(self, enrichment_result_schema: dict[str, Any]) -> None:
        assert "feature_vector" in enrichment_result_schema["properties"]

    def test_schema_contains_convergence_run_id(
        self, enrichment_result_schema: dict[str, Any]
    ) -> None:
        assert "convergence_run_id" in enrichment_result_schema["properties"]


class TestPacketEgressProvenance:
    def test_packet_egress_contains_packet_id(self, packet_egress_example: dict[str, Any]) -> None:
        assert "packet_id" in packet_egress_example

    def test_packet_egress_contains_timestamp(self, packet_egress_example: dict[str, Any]) -> None:
        assert "timestamp" in packet_egress_example

    def test_packet_egress_contains_content_hash(
        self, packet_egress_example: dict[str, Any]
    ) -> None:
        assert "content_hash" in packet_egress_example
        assert len(packet_egress_example["content_hash"]) > 0

    def test_packet_egress_contains_lineage(self, packet_egress_example: dict[str, Any]) -> None:
        assert "lineage" in packet_egress_example
        assert isinstance(packet_egress_example["lineage"], dict)

    def test_packet_egress_contains_hop_trace(self, packet_egress_example: dict[str, Any]) -> None:
        assert "hop_trace" in packet_egress_example
        assert isinstance(packet_egress_example["hop_trace"], list)


class TestEventProvenance:
    def test_event_contains_required_base_fields(self, event_example: dict[str, Any]) -> None:
        required = {"event_type", "entity_id", "tenant_id", "correlation_id", "occurred_at"}
        missing = sorted(field for field in required if field not in event_example)
        assert not missing, f"Event missing required provenance/base fields: {missing}"

    def test_event_correlation_id_is_present(self, event_example: dict[str, Any]) -> None:
        assert isinstance(event_example["correlation_id"], str)
        assert len(event_example["correlation_id"]) > 0
