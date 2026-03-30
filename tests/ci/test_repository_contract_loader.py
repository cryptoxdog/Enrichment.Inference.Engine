"""Unit tests for the YAML contract catalog loader."""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from tests.ci._repository_contract_loader import (
    CatalogValidationError,
    load_catalog,
)


@pytest.fixture
def tmp_catalog(tmp_path: pathlib.Path):
    """Helper to write a temporary YAML catalog and return its path."""

    def _write(content: str) -> pathlib.Path:
        p = tmp_path / "test_catalog.yaml"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    return _write


class TestCatalogLoading:
    """Successful parse scenarios."""

    def test_minimal_valid_catalog(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "test_method"
                param: "test_param"
                allowed_literals: ["value_a"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "test"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        catalog = load_catalog(path)
        assert catalog.schema_version == "1.0.0"
        assert len(catalog.pairs) == 1
        assert catalog.pairs[0].method == "test_method"

    def test_multiple_pairs(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "method_a"
                param: "param_a"
                allowed_literals: ["x"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "a"
              - method: "method_b"
                param: "param_b"
                allowed_literals: ["y", "z"]
                dynamic_policy: "prove_dynamic"
                severity: "warning"
                description: "b"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        catalog = load_catalog(path)
        assert len(catalog.pairs) == 2
        assert catalog.pairs[1].dynamic_policy == "prove_dynamic"

    def test_stage2_fields_loaded(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "test_method"
                param: "test_param"
                param_position: 3
                baseline_callsites: 42
                drift_threshold_percent: 15
                allowed_literals: ["val"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "test"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        catalog = load_catalog(path)
        pair = catalog.pairs[0]
        assert pair.param_position == 3
        assert pair.baseline_callsites == 42
        assert pair.drift_threshold_percent == 15

    def test_stage2_defaults(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "test_method"
                param: "test_param"
                allowed_literals: ["val"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "test"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        catalog = load_catalog(path)
        pair = catalog.pairs[0]
        assert pair.param_position is None
        assert pair.baseline_callsites is None
        assert pair.drift_threshold_percent == 25

    def test_dynamic_sources_parsed(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "m"
                param: "p"
                allowed_literals: ["v"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
                description: "d"
            dynamic_sources:
              allow_patterns:
                - kind: "enum_member"
                  pattern: "MyEnum.*"
                  trust_level: "proven"
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        catalog = load_catalog(path)
        assert len(catalog.dynamic_sources) == 1
        assert catalog.dynamic_sources[0].kind == "enum_member"


class TestCatalogValidationErrors:
    """Failure conditions."""

    def test_missing_top_level_keys(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
        """)
        with pytest.raises(CatalogValidationError, match="Missing required"):
            load_catalog(path)

    def test_duplicate_pairs(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "m"
                param: "p"
                allowed_literals: ["v"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
              - method: "m"
                param: "p"
                allowed_literals: ["w"]
                dynamic_policy: "hybrid_warn"
                severity: "error"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        with pytest.raises(CatalogValidationError, match="Duplicate"):
            load_catalog(path)

    def test_empty_allowlist(self, tmp_catalog):
        path = tmp_catalog("""
            schema_version: "1.0.0"
            scan:
              include_globs: ["**/*.py"]
              exclude_globs: [".venv/**"]
            pairs:
              - method: "m"
                param: "p"
                allowed_literals: []
                dynamic_policy: "hybrid_warn"
                severity: "error"
            dynamic_sources:
              allow_patterns: []
            baseline:
              file: ""
              drift_threshold_percent: 10
              drift_policy: "warn"
        """)
        with pytest.raises(CatalogValidationError, match="non-empty"):
            load_catalog(path)

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_catalog(pathlib.Path("/nonexistent/catalog.yaml"))

    def test_non_mapping_root(self, tmp_catalog):
        path = tmp_catalog("- just a list")
        with pytest.raises(CatalogValidationError, match="mapping"):
            load_catalog(path)
