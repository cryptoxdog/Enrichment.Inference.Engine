"""
Template Contract Tests
=======================
Validates docs/contracts/_templates/ against:
  1. All 5 template files present
  2. Each template contains the required structural elements
  3. Templates are syntactically valid (YAML or JSON)
  4. Templates contain placeholder markers
  5. Templates include version block header (Phase 3.1/3.2)

Markers: unit
"""

from __future__ import annotations

import json

import pytest
import yaml

from tests.contracts.conftest_contracts import TEMPLATES_DIR

TEMPLATE_FILES = {
    "api-endpoint.template.yaml": "yaml",
    "tool-schema.template.json": "json",
    "prompt-contract.template.yaml": "yaml",
    "event-channel.template.yaml": "yaml",
    "data-model.template.json": "json",
}

TEMPLATE_STRUCTURAL_REQUIREMENTS = {
    "api-endpoint.template.yaml": ["method", "path", "summary", "description"],
    "tool-schema.template.json": ["title", "description", "properties", "required"],
    "prompt-contract.template.yaml": ["prompt_name", "role", "template"],
    "event-channel.template.yaml": ["event_name", "channel"],
    "data-model.template.json": ["title", "description", "properties", "required"],
}


@pytest.mark.unit
@pytest.mark.parametrize("filename,fmt", TEMPLATE_FILES.items())
def test_template_file_exists(filename: str, fmt: str) -> None:
    path = TEMPLATES_DIR / filename
    assert path.exists(), f"Missing template: _templates/{filename}"


@pytest.mark.unit
@pytest.mark.parametrize("filename,fmt", TEMPLATE_FILES.items())
def test_template_file_is_parseable(filename: str, fmt: str) -> None:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        pytest.skip(f"Missing: {filename}")
    content = path.read_text()
    if fmt == "yaml":
        try:
            data = yaml.safe_load(content)
            assert data is not None, f"{filename}: YAML is empty or null"
        except yaml.YAMLError as exc:
            pytest.fail(f"{filename}: YAML parse error: {exc}")
    else:
        try:
            data = json.loads(content)
            assert isinstance(data, dict), f"{filename}: JSON root must be object"
        except json.JSONDecodeError as exc:
            pytest.fail(f"{filename}: JSON parse error: {exc}")


@pytest.mark.unit
@pytest.mark.parametrize("filename,required_fields", TEMPLATE_STRUCTURAL_REQUIREMENTS.items())
def test_template_contains_required_structure(filename: str, required_fields: list) -> None:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        pytest.skip(f"Missing: {filename}")
    content = path.read_text().lower()
    for field in required_fields:
        assert field.lower() in content, f"{filename}: missing required element '{field}'"


@pytest.mark.unit
@pytest.mark.parametrize("filename", TEMPLATE_STRUCTURAL_REQUIREMENTS.keys())
def test_template_has_placeholders(filename: str) -> None:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        pytest.skip(f"Missing: {filename}")
    content = path.read_text()
    placeholder_patterns = ["{", "<", "FILL", "TODO", "YOUR_", "PLACEHOLDER"]
    has_placeholder = any(p in content for p in placeholder_patterns)
    assert has_placeholder, f"{filename}: no placeholder markers found"


@pytest.mark.unit
@pytest.mark.parametrize("filename", [f for f, fmt in TEMPLATE_FILES.items() if fmt == "yaml"])
def test_yaml_template_has_version_block(filename: str) -> None:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        pytest.skip(f"Missing: {filename}")
    content = path.read_text()
    has_version = (
        "Version:" in content
        or "version:" in content.lower()
        or "# Contract:" in content
        or "# ═══" in content
    )
    assert has_version, f"{filename}: missing version block header (Phase 3.1)"


@pytest.mark.unit
@pytest.mark.parametrize("filename", [f for f, fmt in TEMPLATE_FILES.items() if fmt == "json"])
def test_json_template_has_schema_and_examples(filename: str) -> None:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        pytest.skip(f"Missing: {filename}")
    content = path.read_text()
    assert "$schema" in content, f"{filename}: missing $schema (Phase 3.2)"
    assert "examples" in content, f"{filename}: missing examples (Phase 3.2)"
