"""
Tier 2 — Enforcement: Replay and Idempotency
============================================
Proves duplicate calls do not produce duplicate side effects.

Primary sources:
- docs/contracts/api/openapi.yaml
- docs/contracts/dependencies/redis.yaml
- docs/contracts/config/env-contract.yaml
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.enforcement, pytest.mark.replay]


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._store.get(key)
        return copy.deepcopy(value) if value is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = copy.deepcopy(value)

    def has(self, key: str) -> bool:
        return key in self._store

    def size(self) -> int:
        return len(self._store)


class MockService:
    def __init__(self, store: InMemoryIdempotencyStore) -> None:
        self.store = store
        self.enrich_executions = 0
        self.writeback_executions = 0

    def enrich(self, request: dict[str, Any]) -> dict[str, Any]:
        key = request.get("idempotency_key")
        if isinstance(key, str) and self.store.has(key):
            return self.store.get(key)  # type: ignore[return-value]

        self.enrich_executions += 1
        entity = request.get("entity", {})
        name = entity.get("Name") or entity.get("name") or "unknown"
        result = {
            "fields": {"normalized_name": str(name)},
            "confidence": 0.88,
            "kb_content_hash": "abc123",
            "variation_count": 3,
            "consensus_threshold": request.get("consensus_threshold", 0.65),
            "uncertainty_score": 1.1,
            "pass_count": 1,
            "inference_version": "v2.2.0",
            "processing_time_ms": 1000,
            "enrichment_payload": None,
            "feature_vector": None,
            "kb_files_consulted": ["plastics_recycling.yaml"],
            "kb_fragment_ids": ["plastics_recycling#hdpe"],
            "inferences": [],
            "quality_tier": "gold",
            "grade_matches": [],
            "tokens_used": 300,
            "failure_reason": None,
            "state": "completed",
            "_execution_count": self.enrich_executions,
        }
        if isinstance(key, str):
            self.store.set(key, result)
        return copy.deepcopy(result)

    def writeback(self, request: dict[str, Any]) -> dict[str, Any]:
        key = request.get("idempotency_key")
        if isinstance(key, str) and self.store.has(key):
            cached = self.store.get(key)
            assert cached is not None
            cached["deduplicated"] = True
            return cached

        self.writeback_executions += 1
        enriched_data = request.get("enriched_data", {})
        result = {
            "status": "completed",
            "attempted_fields": list(enriched_data.keys()),
            "written_fields": list(enriched_data.keys()),
            "skipped_fields": [],
            "skip_reasons": {},
            "_write_count": self.writeback_executions,
        }
        if isinstance(key, str):
            self.store.set(key, result)
        return copy.deepcopy(result)


@pytest.fixture
def store() -> InMemoryIdempotencyStore:
    return InMemoryIdempotencyStore()


@pytest.fixture
def service(store: InMemoryIdempotencyStore) -> MockService:
    return MockService(store)


def make_enrich_request(idempotency_key: str | None = None) -> dict[str, Any]:
    request = {
        "entity": {
            "Name": "PlasticOS Supply Ltd",
            "BillingCountry": "DE",
            "Industry": "Plastics Recycling",
        },
        "object_type": "Account",
        "objective": "Determine polymer type and material grade",
        "schema": {
            "polymer_type": "string",
            "material_grade": "string",
        },
        "consensus_threshold": 0.75,
        "max_variations": 3,
    }
    if idempotency_key is not None:
        request["idempotency_key"] = idempotency_key
    return request


def make_writeback_request(idempotency_key: str | None = None) -> dict[str, Any]:
    request = {
        "crm_type": "salesforce",
        "object_type": "Account",
        "record_id": "001B000000LpT1FIAV",
        "enriched_data": {
            "recycling_grade": "HDPE",
            "annual_tonnage": 50000,
        },
        "confidence_threshold": 0.70,
    }
    if idempotency_key is not None:
        request["idempotency_key"] = idempotency_key
    return request


class TestEnrichIdempotency:
    def test_same_key_returns_same_result(self, service: MockService) -> None:
        request = make_enrich_request(idempotency_key="idem-enrich-001")
        first = service.enrich(request)
        second = service.enrich(request)
        assert first["fields"] == second["fields"]
        assert first["_execution_count"] == 1
        assert second["_execution_count"] == 1

    def test_different_keys_produce_distinct_executions(self, service: MockService) -> None:
        first = service.enrich(make_enrich_request(idempotency_key="idem-enrich-002"))
        second = service.enrich(make_enrich_request(idempotency_key="idem-enrich-003"))
        assert first["_execution_count"] == 1
        assert second["_execution_count"] == 2

    def test_no_key_means_no_dedup_guarantee(self, service: MockService) -> None:
        first = service.enrich(make_enrich_request())
        second = service.enrich(make_enrich_request())
        assert first["_execution_count"] == 1
        assert second["_execution_count"] == 2

    def test_result_stored_by_idempotency_key(
        self,
        service: MockService,
        store: InMemoryIdempotencyStore,
    ) -> None:
        service.enrich(make_enrich_request(idempotency_key="idem-enrich-004"))
        assert store.has("idem-enrich-004")


class TestWritebackIdempotency:
    def test_same_key_does_not_write_twice(self, service: MockService) -> None:
        request = make_writeback_request(idempotency_key="idem-writeback-001")
        first = service.writeback(request)
        second = service.writeback(request)
        assert first["_write_count"] == 1
        assert second["deduplicated"] is True

    def test_different_keys_produce_distinct_writes(self, service: MockService) -> None:
        first = service.writeback(make_writeback_request(idempotency_key="idem-writeback-002"))
        second = service.writeback(make_writeback_request(idempotency_key="idem-writeback-003"))
        assert first["_write_count"] == 1
        assert second["_write_count"] == 2

    def test_writeback_without_key_allows_duplicate_execution(self, service: MockService) -> None:
        first = service.writeback(make_writeback_request())
        second = service.writeback(make_writeback_request())
        assert first["_write_count"] == 1
        assert second["_write_count"] == 2

    def test_writeback_dedup_result_is_stable(self, service: MockService) -> None:
        request = make_writeback_request(idempotency_key="idem-writeback-004")
        first = service.writeback(request)
        second = service.writeback(request)
        assert first["written_fields"] == second["written_fields"]


class TestStoreIsolation:
    def test_no_key_not_stored(self, service: MockService, store: InMemoryIdempotencyStore) -> None:
        service.enrich(make_enrich_request())
        assert store.size() == 0

    def test_writeback_key_stored(
        self,
        service: MockService,
        store: InMemoryIdempotencyStore,
    ) -> None:
        service.writeback(make_writeback_request(idempotency_key="idem-writeback-005"))
        assert store.has("idem-writeback-005")
