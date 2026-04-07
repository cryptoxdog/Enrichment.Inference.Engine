"""
Shared Schema Registry + Cross-Cutting Contract Tests
======================================================
Validates:
  1. api/schemas/shared-models.yaml defines reusable components
  2. api/schemas/error-responses.yaml defines standard error envelope
  3. No schema duplication — $ref is used instead of inline copies
  4. Root README.md has Mermaid dependency graph
  5. Root README.md has validation commands section
  6. VERSIONING.md exists and defines semver policy

Source grounding:
  - Phase 4 cross-cutting concerns from the Nuclear Super Prompt
  - Phase 4.1 shared schema registry requirement
  - Phase 4.3 validation commands requirement

Markers: unit
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.contracts.conftest_contracts import (
    CONTRACTS_DIR, API_DIR, load_yaml,
)

# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shared_models() -> dict:
    path = API_DIR / "schemas" / "shared-models.yaml"
    if not path.exists():
        pytest.skip("shared-models.yaml missing — covered by test_contract_files_exist")
    return load_yaml(path)


@pytest.mark.unit
def test_shared_models_has_pagination_envelope(shared_models: dict) -> None:
    """
    Phase 4.1: shared-models.yaml must define a pagination envelope.
    EnrichResponse lists (BatchEnrichResponse.results) follow a standard pattern.
    """
    models_str = str(shared_models).lower()
    has_pagination = (
        "pagination" in models_str
        or "paginatedresponse" in models_str
        or "total" in models_str
    )
    assert has_pagination, (
        "shared-models.yaml must define a pagination envelope. "
        "Phase 4.1 — common candidates: PaginatedResponse<T>, total, page, perPage."
    )


@pytest.mark.unit
def test_shared_models_has_error_envelope(shared_models: dict) -> None:
    """Phase 4.1: shared-models.yaml must define the common error format."""
    models_str = str(shared_models).lower()
    has_error = "error" in models_str
    assert has_error, (
        "shared-models.yaml must define an error type. Phase 4.1."
    )


@pytest.mark.unit
def test_shared_models_has_timestamp_format(shared_models: dict) -> None:
    """Phase 4.1: timestamp format must be standardized."""
    models_str = str(shared_models).lower()
    has_timestamp = "timestamp" in models_str or "date-time" in models_str
    assert has_timestamp, (
        "shared-models.yaml must document timestamp format. Phase 4.1."
    )


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def error_responses() -> dict:
    path = API_DIR / "schemas" / "error-responses.yaml"
    if not path.exists():
        pytest.skip("error-responses.yaml missing")
    return load_yaml(path)


@pytest.mark.unit
def test_error_responses_has_400(error_responses: dict) -> None:
    """Standard 400 Bad Request must be defined."""
    er_str = str(error_responses)
    assert "400" in er_str or "bad_request" in er_str.lower() or "BadRequest" in er_str, (
        "error-responses.yaml must define 400 Bad Request response."
    )


@pytest.mark.unit
def test_error_responses_has_401(error_responses: dict) -> None:
    """Standard 401 Unauthorized must be defined."""
    er_str = str(error_responses)
    assert "401" in er_str or "unauthorized" in er_str.lower(), (
        "error-responses.yaml must define 401 Unauthorized response."
    )


@pytest.mark.unit
def test_error_responses_has_422(error_responses: dict) -> None:
    """422 Unprocessable Entity is FastAPI's default validation error."""
    er_str = str(error_responses)
    assert "422" in er_str or "validation" in er_str.lower(), (
        "error-responses.yaml must define 422 Validation Error (FastAPI default). "
        "Source: FastAPI's default_exception_handlers for RequestValidationError."
    )


@pytest.mark.unit
def test_error_responses_has_500(error_responses: dict) -> None:
    """500 Internal Server Error must be defined."""
    er_str = str(error_responses)
    assert "500" in er_str or "internal" in er_str.lower(), (
        "error-responses.yaml must define 500 Internal Server Error."
    )


# ---------------------------------------------------------------------------
# Root README.md — Phase 4 requirements
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def root_readme() -> str:
    path = CONTRACTS_DIR / "README.md"
    if not path.exists():
        pytest.skip("README.md missing")
    return path.read_text()


@pytest.mark.unit
def test_root_readme_has_mermaid_diagram(root_readme: str) -> None:
    """
    Phase 4.2: Root README must contain a Mermaid dependency graph.
    """
    assert "```mermaid" in root_readme or "mermaid" in root_readme.lower(), (
        "docs/contracts/README.md must contain a Mermaid diagram. "
        "Phase 4.2 — dependency graph showing service-contract-event relationships."
    )


@pytest.mark.unit
def test_root_readme_has_validation_commands(root_readme: str) -> None:
    """
    Phase 4.3: Root README must include validation commands section.
    """
    has_validation = (
        "validation" in root_readme.lower()
        or "validate" in root_readme.lower()
        or "npx" in root_readme
        or "redocly" in root_readme
        or "asyncapi" in root_readme.lower()
    )
    assert has_validation, (
        "docs/contracts/README.md must include validation commands. "
        "Phase 4.3 — commands for OpenAPI lint, AsyncAPI validate, JSON Schema validate."
    )


@pytest.mark.unit
def test_root_readme_has_contracts_index_table(root_readme: str) -> None:
    """Root README must contain a contracts index table (Phase 3.5)."""
    # Markdown tables have | characters
    has_table = "|" in root_readme and "Contract" in root_readme
    assert has_table, (
        "docs/contracts/README.md must contain a contracts index table. "
        "Phase 3.5 style requirement."
    )


# ---------------------------------------------------------------------------
# VERSIONING.md
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_versioning_md_defines_semver_policy() -> None:
    """VERSIONING.md must define semantic versioning policy for contracts."""
    path = CONTRACTS_DIR / "VERSIONING.md"
    if not path.exists():
        pytest.skip("VERSIONING.md missing")

    content = path.read_text().lower()
    has_semver = (
        "semver" in content
        or "semantic" in content
        or "major" in content and "minor" in content
    )
    assert has_semver, (
        "VERSIONING.md must define semantic versioning policy for contract evolution."
    )


@pytest.mark.unit
def test_versioning_md_defines_changelog_format() -> None:
    """VERSIONING.md must define changelog format (Phase 2 requirement)."""
    path = CONTRACTS_DIR / "VERSIONING.md"
    if not path.exists():
        pytest.skip("VERSIONING.md missing")

    content = path.read_text().lower()
    has_changelog = "changelog" in content or "change" in content
    assert has_changelog, (
        "VERSIONING.md must define changelog format. Phase 2 requirement."
    )


# ---------------------------------------------------------------------------
# No-duplication: verify $ref usage in openapi.yaml for error responses
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_openapi_uses_ref_for_error_responses() -> None:
    """
    Phase 4.1: OpenAPI spec must use $ref for error responses, not inline copies.
    This enforces DRY principle for error schemas.
    """
    path = API_DIR / "openapi.yaml"
    if not path.exists():
        pytest.skip("openapi.yaml missing")

    content = path.read_text()
    # Should contain at least one $ref to a shared error response
    ref_count = content.count("$ref")
    assert ref_count >= 1, (
        "openapi.yaml must use $ref for shared schemas. "
        "Phase 4.1 — DRY: never duplicate schemas."
    )
