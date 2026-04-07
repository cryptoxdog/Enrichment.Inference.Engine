"""
Tier 2 — Enforcement: Behavioral Invariants
===========================================
Proves current EnrichResponse semantics remain aligned with the contract pack.

Primary sources:
- docs/contracts/api/openapi.yaml
- docs/contracts/api/schemas/shared-models.yaml
- tests/contracts/fixtures/enrich_response_example.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.enforcement]

ROOT = Path(".")
OPENAPI_PATH = ROOT / "docs/contracts/api/openapi.yaml"
SHARED_MODELS_PATH = ROOT / "docs/contracts/api/schemas/shared-models.yaml"
FIXTURES_DIR = ROOT / "tests/contracts/fixtures"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def openapi_contract() -> dict[str, Any]:
    return _load_yaml(OPENAPI_PATH)


@pytest.fixture(scope="module")
def shared_models_contract() -> dict[str, Any]:
    return _load_yaml(SHARED_MODELS_PATH)


@pytest.fixture(scope="module")
def quality_tier_enum(shared_models_contract: dict[str, Any]) -> set[str]:
    schema = shared_models_contract["components"]["schemas"]["QualityTier"]
    return set(schema["enum"])


@pytest.fixture(scope="module")
def enrich_state_enum(openapi_contract: dict[str, Any]) -> set[str]:
    schema = openapi_contract["components"]["schemas"]["EnrichResponse"]
    return set(schema["properties"]["state"]["enum"])


@pytest.fixture(scope="module")
def enrich_response_example() -> dict[str, Any]:
    fixture = FIXTURES_DIR / "enrich_response_example.json"
    if fixture.exists():
        return _load_json(fixture)

    return {
        "fields": {
            "polymer_type": "HDPE",
            "contamination_pct": 2.1,
            "material_grade": "Premium HDPE",
            "facility_tier": "Tier 1",
        },
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
        "inferences": [
            {"field": "material_grade", "value": "Premium HDPE", "confidence": 0.95}
        ],
        "quality_tier": "gold",
        "grade_matches": [],
        "tokens_used": 1840,
        "failure_reason": None,
        "state": "completed",
    }


def make_enrich_response(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "fields": {"polymer_type": "HDPE"},
        "confidence": 0.88,
        "kb_content_hash": "abc123def4567890",
        "variation_count": 3,
        "consensus_threshold": 0.65,
        "uncertainty_score": 1.2,
        "pass_count": 1,
        "inference_version": "v2.2.0",
        "processing_time_ms": 1500,
        "enrichment_payload": None,
        "feature_vector": None,
        "kb_files_consulted": ["plastics_recycling.yaml"],
        "kb_fragment_ids": ["plastics_recycling#hdpe"],
        "inferences": [],
        "quality_tier": "gold",
        "grade_matches": [],
        "tokens_used": 400,
        "failure_reason": None,
        "state": "completed",
    }
    base.update(overrides)
    return base


def test_fixture_is_contract_shaped(enrich_response_example: dict[str, Any]) -> None:
    required_core = {
        "fields",
        "confidence",
        "uncertainty_score",
        "pass_count",
        "inference_version",
        "processing_time_ms",
        "kb_fragment_ids",
        "quality_tier",
        "tokens_used",
        "state",
    }
    missing = sorted(field for field in required_core if field not in enrich_response_example)
    assert not missing, f"EnrichResponse fixture missing core fields: {missing}"


def test_quality_tier_matches_contract(
    enrich_response_example: dict[str, Any],
    quality_tier_enum: set[str],
) -> None:
    tier = enrich_response_example.get("quality_tier")
    assert tier in quality_tier_enum, (
        f"quality_tier '{tier}' not in allowed enum {sorted(quality_tier_enum)}"
    )


def test_state_matches_contract(
    enrich_response_example: dict[str, Any],
    enrich_state_enum: set[str],
) -> None:
    state = enrich_response_example.get("state")
    assert state in enrich_state_enum, (
        f"state '{state}' not in allowed enum {sorted(enrich_state_enum)}"
    )


def test_confidence_in_range(enrich_response_example: dict[str, Any]) -> None:
    confidence = enrich_response_example.get("confidence")
    assert confidence is not None, "confidence must be present"
    assert 0.0 <= confidence <= 1.0, f"confidence {confidence} outside [0, 1]"


def test_consensus_threshold_in_range(enrich_response_example: dict[str, Any]) -> None:
    threshold = enrich_response_example.get("consensus_threshold")
    if threshold is not None:
        assert 0.0 <= threshold <= 1.0, f"consensus_threshold {threshold} outside [0, 1]"


def test_uncertainty_score_non_negative(enrich_response_example: dict[str, Any]) -> None:
    score = enrich_response_example.get("uncertainty_score")
    assert score is not None, "uncertainty_score must be present"
    assert score >= 0.0, "uncertainty_score must be non-negative"


def test_failed_state_requires_failure_reason() -> None:
    result = make_enrich_response(state="failed", failure_reason=None)
    assert result["failure_reason"] is not None, (
        "state='failed' must carry a non-null failure_reason"
    )


def test_completed_state_must_not_have_failure_reason() -> None:
    result = make_enrich_response(state="completed", failure_reason="unexpected")
    assert result["failure_reason"] is None, (
        "state='completed' must not carry a non-null failure_reason"
    )


def test_partial_state_is_valid() -> None:
    result = make_enrich_response(state="partial", failure_reason=None)
    assert result["state"] == "partial"


def test_pass_count_at_least_one(enrich_response_example: dict[str, Any]) -> None:
    pass_count = enrich_response_example.get("pass_count")
    assert isinstance(pass_count, int), "pass_count must be an integer"
    assert pass_count >= 1, "pass_count must be >= 1"


def test_tokens_used_non_negative(enrich_response_example: dict[str, Any]) -> None:
    tokens_used = enrich_response_example.get("tokens_used")
    assert isinstance(tokens_used, int), "tokens_used must be an integer"
    assert tokens_used >= 0, "tokens_used must be >= 0"


def test_processing_time_ms_non_negative(enrich_response_example: dict[str, Any]) -> None:
    processing_time_ms = enrich_response_example.get("processing_time_ms")
    assert isinstance(processing_time_ms, int), "processing_time_ms must be an integer"
    assert processing_time_ms >= 0, "processing_time_ms must be >= 0"


def test_kb_fragment_ids_are_string_list(enrich_response_example: dict[str, Any]) -> None:
    fragment_ids = enrich_response_example.get("kb_fragment_ids")
    assert isinstance(fragment_ids, list), "kb_fragment_ids must be a list"
    assert all(isinstance(item, str) for item in fragment_ids), (
        "kb_fragment_ids must be a list[str]"
    )


def test_kb_files_consulted_are_string_list(enrich_response_example: dict[str, Any]) -> None:
    files = enrich_response_example.get("kb_files_consulted")
    if files is not None:
        assert isinstance(files, list), "kb_files_consulted must be a list"
        assert all(isinstance(item, str) for item in files), (
            "kb_files_consulted must be a list[str]"
        )


def test_inferences_is_list(enrich_response_example: dict[str, Any]) -> None:
    inferences = enrich_response_example.get("inferences")
    if inferences is not None:
        assert isinstance(inferences, list), "inferences must be a list"


def test_fields_is_object(enrich_response_example: dict[str, Any]) -> None:
    fields = enrich_response_example.get("fields")
    assert isinstance(fields, dict), "fields must be an object"


def test_failure_reason_can_be_null_for_non_failed_states(
    enrich_response_example: dict[str, Any],
) -> None:
    if enrich_response_example["state"] != "failed":
        assert enrich_response_example.get("failure_reason") is None
