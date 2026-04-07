"""
Data Model Contract Tests
Source: app/services/pg_models.py, migrations/versions/001_initial_schema.py
Markers: unit
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.contracts.conftest_contracts import DATA_DIR, load_json, load_yaml

MODEL_FILES = {
    "enrichment-result": DATA_DIR / "models" / "enrichment-result.schema.json",
    "convergence-run": DATA_DIR / "models" / "convergence-run.schema.json",
    "field-confidence-history": DATA_DIR / "models" / "field-confidence-history.schema.json",
    "schema-proposal": DATA_DIR / "models" / "schema-proposal.schema.json",
}

ENRICHMENT_RESULT_FIELDS = {
    "id": {"type": "string"},
    "state": {"type": "string"},
    "fields": {},
    "confidence": {},
    "inference_version": {"type": "string"},
    "processing_time_ms": {},
    "tokens_used": {},
    "quality_tier": {"type": "string"},
}

CONVERGENCE_RUN_FIELDS = {
    "run_id": {},
    "domain": {},
    "entity_id": {},
    "state": {},
    "pass_count": {},
    "consensus_threshold": {},
}

FIELD_CONFIDENCE_HISTORY_FIELDS = {
    "id": {},
    "entity_id": {},
    "field_name": {},
    "field_value": {},
    "confidence": {},
    "source": {},
}

SCHEMA_PROPOSAL_FIELDS = {
    "id": {},
    "domain": {},
    "field_name": {},
    "proposed_type": {},
    "status": {},
}

FIELD_GROUND_TRUTH = {
    "enrichment-result": ENRICHMENT_RESULT_FIELDS,
    "convergence-run": CONVERGENCE_RUN_FIELDS,
    "field-confidence-history": FIELD_CONFIDENCE_HISTORY_FIELDS,
    "schema-proposal": SCHEMA_PROPOSAL_FIELDS,
}


@pytest.mark.unit
@pytest.mark.parametrize("model_name,schema_path", MODEL_FILES.items())
def test_model_schema_is_valid_json(model_name: str, schema_path: Path) -> None:
    assert schema_path.exists(), f"Missing model schema: {schema_path}"
    data = load_json(schema_path)
    assert isinstance(data, dict)


@pytest.mark.unit
@pytest.mark.parametrize("model_name,schema_path", MODEL_FILES.items())
def test_model_has_schema_id(model_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert "$schema" in data, f"{model_name}: missing $schema"
    assert "$id" in data, f"{model_name}: missing $id — Phase 3.2"


@pytest.mark.unit
@pytest.mark.parametrize("model_name,schema_path", MODEL_FILES.items())
def test_model_has_description(model_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("description"), f"{model_name}: missing description — Phase 3.6 Rule 5"


@pytest.mark.unit
@pytest.mark.parametrize("model_name,schema_path", MODEL_FILES.items())
def test_model_has_examples(model_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("examples"), f"{model_name}: missing examples — Phase 3.2"


@pytest.mark.unit
@pytest.mark.parametrize("model_name,schema_path", MODEL_FILES.items())
def test_model_additional_properties_false(model_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("additionalProperties") is False, (
        f"{model_name}: additionalProperties must be false — Phase 3.2 strict mode"
    )


@pytest.mark.unit
@pytest.mark.parametrize("model_name,expected_fields", FIELD_GROUND_TRUTH.items())
def test_model_required_fields_present(model_name: str, expected_fields: dict) -> None:
    schema_path = MODEL_FILES[model_name]
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    props = data.get("properties", {})
    for field in expected_fields:
        assert field in props, (
            f"{model_name}: field '{field}' missing from properties. "
            "Source: app/services/pg_models.py"
        )


@pytest.mark.unit
@pytest.mark.parametrize("model_name,expected_fields", FIELD_GROUND_TRUTH.items())
def test_model_fields_have_descriptions(model_name: str, expected_fields: dict) -> None:
    schema_path = MODEL_FILES[model_name]
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    props = data.get("properties", {})
    for field in expected_fields:
        if field in props:
            assert props[field].get("description"), (
                f"{model_name}.{field}: missing description — Phase 3.6 Rule 5"
            )


@pytest.mark.unit
def test_graph_schema_has_node_labels() -> None:
    path = DATA_DIR / "graph-schema.yaml"
    if not path.exists():
        pytest.skip("graph-schema.yaml missing")
    schema = load_yaml(path)
    s = str(schema).lower()
    assert any(k in s for k in ("node_labels", "nodes", "node")), (
        "graph-schema.yaml must document node labels. Source: Neo4j CEG database."
    )


@pytest.mark.unit
def test_graph_schema_has_relationship_types() -> None:
    path = DATA_DIR / "graph-schema.yaml"
    if not path.exists():
        pytest.skip("graph-schema.yaml missing")
    schema = load_yaml(path)
    s = str(schema).lower()
    assert any(k in s for k in ("relationship", "edge", "connects")), (
        "graph-schema.yaml must document relationship types."
    )


@pytest.mark.unit
def test_migration_policy_exists_and_non_empty() -> None:
    path = DATA_DIR / "migrations" / "migration-policy.md"
    if not path.exists():
        pytest.skip("migration-policy.md missing")
    content = path.read_text()
    assert len(content) > 100, "migration-policy.md seems like a stub"
    assert "migration" in content.lower()


@pytest.mark.unit
def test_data_model_index_covers_all_models() -> None:
    index_path = DATA_DIR / "models" / "_index.yaml"
    if not index_path.exists():
        pytest.skip("_index.yaml missing")
    index = load_yaml(index_path)
    index_str = str(index)
    for model_name in MODEL_FILES:
        assert model_name in index_str or model_name.replace("-", "_") in index_str, (
            f"Model '{model_name}' not in data/models/_index.yaml"
        )
