"""YAML contract catalog loader and schema validator.

Loads ``repository_contract_pairs.yaml``, validates structural invariants,
and returns typed in-memory models for the AST-scanning test engine.

Adapted for Enrichment.Inference.Engine from L9 10X CI pack.
"""
from __future__ import annotations

import dataclasses
import pathlib

import yaml

import logging

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class DynamicSourcePattern:
    """A recognized dynamic expression pattern for promotion."""

    kind: str
    pattern: str
    trust_level: str


@dataclasses.dataclass(frozen=True, slots=True)
class ContractPair:
    """A single method/param allowlist contract.

    Fields:
    - ``param_position``: positional arg index for resolution
    - ``baseline_callsites``: known count for drift tracking
    - ``drift_threshold_percent``: per-pair drift threshold
    """

    method: str
    param: str
    allowed_literals: list[str]
    dynamic_policy: str
    severity: str
    description: str
    param_position: int | None = None
    baseline_callsites: int | None = None
    drift_threshold_percent: int = 25


@dataclasses.dataclass(frozen=True, slots=True)
class ScanConfig:
    """Glob configuration for file collection."""

    include_globs: list[str]
    exclude_globs: list[str]


@dataclasses.dataclass(frozen=True, slots=True)
class BaselineConfig:
    """Baseline drift detection configuration."""

    file: str
    drift_threshold_percent: int
    drift_policy: str


@dataclasses.dataclass(frozen=True, slots=True)
class ContractCatalog:
    """Top-level catalog containing all contract definitions."""

    schema_version: str
    scan: ScanConfig
    pairs: list[ContractPair]
    dynamic_sources: list[DynamicSourcePattern]
    baseline: BaselineConfig


# ── Errors ───────────────────────────────────────────────────


class CatalogValidationError(Exception):
    """Raised when the YAML catalog fails structural validation."""


# ── Loader ───────────────────────────────────────────────────

_REQUIRED_TOP_KEYS = frozenset({
    "schema_version",
    "scan",
    "pairs",
    "dynamic_sources",
    "baseline",
})


def _validate_raw(raw: dict) -> None:
    """Validate structural invariants on the raw YAML dict."""
    missing = _REQUIRED_TOP_KEYS - set(raw)
    if missing:
        msg = f"Missing required top-level keys: {sorted(missing)}"
        raise CatalogValidationError(msg)

    scan = raw["scan"]
    if not isinstance(scan, dict):
        msg = "scan must be a mapping"
        raise CatalogValidationError(msg)

    for key in ("include_globs", "exclude_globs"):
        val = scan.get(key)
        if not isinstance(val, list) or len(val) == 0:
            msg = f"scan.{key} must be a non-empty list"
            raise CatalogValidationError(msg)

    pairs = raw["pairs"]
    if not isinstance(pairs, list):
        msg = "pairs must be a list"
        raise CatalogValidationError(msg)

    seen: set[tuple[str, str]] = set()
    for idx, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            msg = f"pairs[{idx}] must be a mapping"
            raise CatalogValidationError(msg)

        for req_key in ("method", "param", "allowed_literals", "dynamic_policy", "severity"):
            if req_key not in pair:
                msg = f"pairs[{idx}] missing required key: {req_key}"
                raise CatalogValidationError(msg)

        al = pair["allowed_literals"]
        if not isinstance(al, list) or len(al) == 0:
            msg = f"pairs[{idx}] allowed_literals must be a non-empty list"
            raise CatalogValidationError(msg)

        key = (pair["method"], pair["param"])
        if key in seen:
            msg = f"Duplicate (method, param) pair: {key}"
            raise CatalogValidationError(msg)
        seen.add(key)

    baseline = raw.get("baseline", {})
    if not isinstance(baseline, dict):
        msg = "baseline must be a mapping"
        raise CatalogValidationError(msg)


def _build_catalog(raw: dict) -> ContractCatalog:
    """Convert validated raw dict into typed ``ContractCatalog``."""
    scan_raw = raw["scan"]
    scan = ScanConfig(
        include_globs=list(scan_raw["include_globs"]),
        exclude_globs=list(scan_raw["exclude_globs"]),
    )

    pairs: list[ContractPair] = []
    for p in raw["pairs"]:
        pairs.append(
            ContractPair(
                method=p["method"],
                param=p["param"],
                allowed_literals=list(p["allowed_literals"]),
                dynamic_policy=p.get("dynamic_policy", "hybrid_warn"),
                severity=p.get("severity", "error"),
                description=p.get("description", ""),
                param_position=p.get("param_position"),
                baseline_callsites=p.get("baseline_callsites"),
                drift_threshold_percent=p.get("drift_threshold_percent", 25),
            )
        )

    ds_raw = raw.get("dynamic_sources", {})
    patterns_raw = ds_raw.get("allow_patterns", []) if isinstance(ds_raw, dict) else []
    dynamic_sources: list[DynamicSourcePattern] = []
    for dp in patterns_raw:
        dynamic_sources.append(
            DynamicSourcePattern(
                kind=dp["kind"],
                pattern=dp["pattern"],
                trust_level=dp.get("trust_level", "unknown"),
            )
        )

    bl_raw = raw.get("baseline", {})
    baseline = BaselineConfig(
        file=bl_raw.get("file", ""),
        drift_threshold_percent=int(bl_raw.get("drift_threshold_percent", 10)),
        drift_policy=bl_raw.get("drift_policy", "warn"),
    )

    return ContractCatalog(
        schema_version=str(raw["schema_version"]),
        scan=scan,
        pairs=pairs,
        dynamic_sources=dynamic_sources,
        baseline=baseline,
    )


def load_catalog(catalog_path: pathlib.Path | None = None) -> ContractCatalog:
    """Load and validate the contract catalog from YAML.

    Parameters
    ----------
    catalog_path:
        Absolute or relative path to the YAML catalog file.
        If ``None``, resolves to
        ``config/contracts/repository_contract_pairs.yaml``
        relative to the repo root.

    Returns
    -------
    ContractCatalog
        Validated, typed catalog ready for test engine consumption.

    Raises
    ------
    CatalogValidationError
        If the YAML is structurally invalid.
    FileNotFoundError
        If the catalog file does not exist.
    """
    if catalog_path is None:
        from tests.ci._scan_utils import get_repo_root

        catalog_path = (
            get_repo_root() / "config" / "contracts" / "repository_contract_pairs.yaml"
        )

    if not catalog_path.is_file():
        msg = f"Catalog file not found: {catalog_path}"
        raise FileNotFoundError(msg)

    raw_text = catalog_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text)

    if not isinstance(raw, dict):
        msg = "Catalog YAML root must be a mapping"
        raise CatalogValidationError(msg)

    _validate_raw(raw)
    catalog = _build_catalog(raw)

    logger.info(
        "contract_catalog_loaded schema_version=%s pair_count=%d path=%s",
        catalog.schema_version,
        len(catalog.pairs),
        catalog_path,
    )

    return catalog
