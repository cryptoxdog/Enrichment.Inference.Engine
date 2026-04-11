"""Unit tests for the repository contract catalog loader.

These tests validate the generic YAML catalog loader used by CI contract
enforcement. They are transport-constitution aware in terminology, but they do
not assert manifest semantics directly.
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from tests.ci._repository_contract_loader import CatalogValidationError, load_catalog


@pytest.fixture
def tmp_catalog(tmp_path: pathlib.Path):
    """Write a temporary YAML contract catalog and return its path."""

    def _write(content: str) -> pathlib.Path:
        path = tmp_path / "test_catalog.yaml"
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return path

    return _write


class TestCatalogLoading:
    """Successful parse scenarios."""

    def test_minimal_valid_catalog(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "SDK runtime action registration"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        catalog = load_catalog(path)
        assert catalog.schema_version == "1.0.0"
        assert len(catalog.pairs) == 1
        assert catalog.pairs[0].method == "register_handler"

    def test_multiple_pairs(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "sdk"
              - method: "create_transport_packet"
                param: "action"
                allowed_literals: ["sync", "match"]
                dynamic_policy: "prove_dynamic"
                severity: "warning"
                description: "transport"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        catalog = load_catalog(path)
        assert len(catalog.pairs) == 2
        assert catalog.pairs[1].dynamic_policy == "prove_dynamic"

    def test_stage2_fields_loaded(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                param_position: 1
                baseline_callsites: 6
                drift_threshold_percent: 15
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "sdk"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        catalog = load_catalog(path)
        pair = catalog.pairs[0]
        assert pair.param_position == 1
        assert pair.baseline_callsites == 6
        assert pair.drift_threshold_percent == 15

    def test_stage2_defaults(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "sdk"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        catalog = load_catalog(path)
        pair = catalog.pairs[0]
        assert pair.param_position is None
        assert pair.baseline_callsites is None
        assert pair.drift_threshold_percent == 25

    def test_dynamic_sources_parsed(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "sdk"
            dynamic_sources:
              allow_patterns:
                - kind: "enum_member"
                  pattern: "RuntimeAction.*"
                  trust_level: "proven"
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        catalog = load_catalog(path)
        assert len(catalog.dynamic_sources) == 1
        assert catalog.dynamic_sources[0].kind == "enum_member"


class TestCatalogValidationErrors:
    """Failure conditions."""

    def test_missing_top_level_keys(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            """
        )
        with pytest.raises(CatalogValidationError, match="Missing required"):
            load_catalog(path)

    def test_duplicate_pairs(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: ["enrich"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
              - method: "register_handler"
                param: "action"
                allowed_literals: ["sync"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        with pytest.raises(CatalogValidationError, match="Duplicate"):
            load_catalog(path)

    def test_empty_allowlist(self, tmp_catalog) -> None:
        path = tmp_catalog(
            """
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "register_handler"
                param: "action"
                allowed_literals: []
                dynamic_policy: "hybrid_warn"
                severity: "error"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
            """
        )
        with pytest.raises(CatalogValidationError, match="non-empty"):
            load_catalog(path)

    def test_nonexistent_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_catalog(pathlib.Path("/nonexistent/catalog.yaml"))

    def test_non_mapping_root(self, tmp_catalog) -> None:
        path = tmp_catalog("- just a list")
        with pytest.raises(CatalogValidationError, match="mapping"):
            load_catalog(path)
