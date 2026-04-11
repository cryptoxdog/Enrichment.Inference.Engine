"""
Agent Tool Contract Tests — Source: app/agents/mcp_server.py TOOL_REGISTRY
Markers: unit
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.contracts.conftest_contracts import AGENTS_DIR, load_json, load_yaml

TOOL_REGISTRY_GROUND_TRUTH = {
    "enrich_contact": {
        "required": ["domain", "entity_name"],
        "optional": ["entity_data", "quality_threshold"],
        "action": "enrich",
    },
    "lead_router": {"required": ["lead_data"], "optional": ["team_config"], "action": "enrich"},
    "deal_risk": {
        "required": ["deal_data"],
        "optional": ["historical_context"],
        "action": "enrich",
    },
    "data_hygiene": {"required": ["records", "domain"], "optional": [], "action": "enrich"},
    "writeback": {
        "required": ["crm_type", "object_type", "record_id", "enriched_data"],
        "optional": ["confidence_threshold"],
        "action": "writeback",
    },
}

TOOL_SCHEMA_FILES = {
    n: AGENTS_DIR / "tool-schemas" / f"{n.replace('_', '-')}.schema.json"
    for n in TOOL_REGISTRY_GROUND_TRUTH
}


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,schema_path", TOOL_SCHEMA_FILES.items())
def test_tool_schema_is_valid_json(tool_name: str, schema_path: Path) -> None:
    assert schema_path.exists(), f"Tool schema missing: {schema_path}"
    data = load_json(schema_path)
    assert isinstance(data, dict)


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,schema_path", TOOL_SCHEMA_FILES.items())
def test_tool_schema_has_meta_schema(tool_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert "$schema" in data and "json-schema.org" in data["$schema"]


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,schema_path", TOOL_SCHEMA_FILES.items())
def test_tool_schema_has_title_and_description(tool_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("title"), f"{tool_name}: missing title"
    assert data.get("description"), f"{tool_name}: missing description"


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,schema_path", TOOL_SCHEMA_FILES.items())
def test_tool_schema_has_examples(tool_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("examples"), f"{tool_name}: missing examples — Phase 3.2"


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,schema_path", TOOL_SCHEMA_FILES.items())
def test_tool_schema_has_source_file(tool_name: str, schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("x-source-file"), f"{tool_name}: missing x-source-file — Phase 3.6 Rule 1"
    assert "mcp_server.py" in data["x-source-file"]


@pytest.mark.unit
@pytest.mark.parametrize("tool_name", TOOL_REGISTRY_GROUND_TRUTH.keys())
def test_tool_required_params_match_registry(tool_name: str) -> None:
    schema_path = TOOL_SCHEMA_FILES[tool_name]
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    schema_required = set(data.get("required", []))
    expected_required = set(TOOL_REGISTRY_GROUND_TRUTH[tool_name]["required"])
    assert expected_required <= schema_required, (
        f"{tool_name}: required params mismatch. Expected {sorted(expected_required)}, "
        f"schema has {sorted(schema_required)}. Source: app/agents/mcp_server.py"
    )


@pytest.mark.unit
@pytest.mark.parametrize("tool_name", TOOL_REGISTRY_GROUND_TRUTH.keys())
def test_tool_all_params_in_properties(tool_name: str) -> None:
    schema_path = TOOL_SCHEMA_FILES[tool_name]
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    gt = TOOL_REGISTRY_GROUND_TRUTH[tool_name]
    all_params = gt["required"] + gt["optional"]
    props = data.get("properties", {})
    for p in all_params:
        assert p in props, f"{tool_name}: param '{p}' missing from properties"


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,gt", TOOL_REGISTRY_GROUND_TRUTH.items())
def test_tool_schema_declares_mcp_action(tool_name: str, gt: dict) -> None:
    schema_path = TOOL_SCHEMA_FILES[tool_name]
    if not schema_path.exists():
        pytest.skip(f"Missing: {schema_path}")
    data = load_json(schema_path)
    assert data.get("x-mcp-action") == gt["action"], (
        f"{tool_name}: x-mcp-action={data.get('x-mcp-action')!r}, expected {gt['action']!r}"
    )


@pytest.mark.unit
def test_tool_index_lists_all_tools() -> None:
    index_path = AGENTS_DIR / "tool-schemas" / "_index.yaml"
    if not index_path.exists():
        pytest.skip("_index.yaml missing")
    index = load_yaml(index_path)
    index_str = str(index)
    for tool_name in TOOL_REGISTRY_GROUND_TRUTH:
        assert tool_name in index_str or tool_name.replace("_", "-") in index_str, (
            f"Tool '{tool_name}' not in _index.yaml"
        )
