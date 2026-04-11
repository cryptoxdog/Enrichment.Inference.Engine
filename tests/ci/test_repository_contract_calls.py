"""Repository-wide method/param contract enforcement — Enrichment Engine.

Scans every Python file in the repo (respecting catalog exclude globs) and
validates that calls to protected methods use allowed literal values for
their guarded parameters.

Features:
- FAIL on literal values not in the allowlist.
- Per-pair dynamic_policy enforcement (prove_dynamic vs hybrid_warn).
- Positional + keyword argument resolution.
- Multi-param same-method validation (no short-circuit).
- Per-pair drift tracking with baseline_callsites.
- Dynamic pattern matching against catalog allow_patterns.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import logging
import pathlib
from collections import defaultdict

import pytest

from tests.ci._repository_contract_loader import (
    ContractCatalog,
    ContractPair,
    DynamicSourcePattern,
    load_catalog,
)
from tests.ci._scan_utils import get_repo_root, iter_python_files, parse_python_file

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Dynamic Pattern Matching Infrastructure
# ══════════════════════════════════════════════════════════


def _resolve_name(node: ast.expr) -> str:
    """Return ``ast.Name.id`` or ``'?'`` for non-Name nodes."""
    if isinstance(node, ast.Name):
        return node.id
    return "?"


def _resolve_dotted(node: ast.expr) -> str:
    """Walk ``ast.Attribute`` chains to produce ``'a.b.c'`` strings."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _matches_dynamic_pattern(
    node: ast.expr,
    patterns: list[DynamicSourcePattern],
) -> tuple[bool, str | None]:
    """Match an AST expression against ``allow_patterns`` from the YAML catalog.

    Supports 5 pattern kinds:
    1. enum_member — ScoreDimension.FIT, FieldSource.ENRICHMENT
    2. attribute_chain — self.source, ctx.scope
    3. variable — ast.Name(id="action")
    4. call — any ast.Call (permissive gate)
    5. dict_literal_key — metadata.get("scope")
    """
    for pat in patterns:
        kind = pat.kind
        pattern = pat.pattern

        if kind == "enum_member":
            if isinstance(node, ast.Attribute):
                full = f"{_resolve_name(node.value)}.{node.attr}"
                if fnmatch.fnmatch(full, pattern):
                    return True, f"enum_member:{pattern}"

        elif kind == "attribute_chain":
            if isinstance(node, ast.Attribute):
                full = _resolve_dotted(node)
                if full == pattern:
                    return True, f"attribute_chain:{pattern}"

        elif kind == "variable":
            if isinstance(node, ast.Name) and node.id == pattern:
                return True, f"variable:{pattern}"

        elif kind == "call":
            if isinstance(node, ast.Call):
                return True, "call:*"

        elif kind == "dict_literal_key":
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        full = f'{_resolve_dotted(node.func.value)}.get("{arg0.value}")'
                        if full == pattern:
                            return True, f"dict_literal_key:{pattern}"

    return False, None


# ══════════════════════════════════════════════════════════
# Positional + Keyword Argument Resolution
# ══════════════════════════════════════════════════════════


def _resolve_arg_node(
    call_node: ast.Call,
    param_name: str,
    param_position: int | None,
) -> ast.expr | None:
    """Find the argument node for a parameter."""
    for kw in call_node.keywords:
        if kw.arg == param_name:
            return kw.value

    if param_position is not None and param_position < len(call_node.args):
        return call_node.args[param_position]

    return None


# ══════════════════════════════════════════════════════════
# AST Helpers
# ══════════════════════════════════════════════════════════


def _get_call_name(node: ast.Call) -> str | None:
    """Extract the function/method name from an ``ast.Call`` node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _classify_expr(expr: ast.expr) -> tuple[str, str | None]:
    """Classify an AST expression into ``(kind, literal_value | None)``."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, (str, int, bool)):
        return ("literal", str(expr.value))
    if isinstance(expr, ast.Name):
        return ("name", None)
    if isinstance(expr, ast.Attribute):
        return ("attribute", None)
    if isinstance(expr, ast.Call):
        return ("call", None)
    if isinstance(expr, ast.Subscript):
        return ("subscript", None)
    if isinstance(expr, ast.JoinedStr):
        return ("joined_str", None)
    return ("other", None)


# ══════════════════════════════════════════════════════════
# Per-Pair Enforcement with Multi-Param Support
# ══════════════════════════════════════════════════════════


class ContractCallVisitor(ast.NodeVisitor):
    """AST visitor that checks method calls against contract pairs."""

    def __init__(
        self,
        pairs: list[ContractPair],
        dynamic_patterns: list[DynamicSourcePattern],
        filepath: pathlib.Path,
    ) -> None:
        self._method_map: dict[str, list[ContractPair]] = defaultdict(list)
        for pair in pairs:
            self._method_map[pair.method].append(pair)
        self._dynamic_patterns = dynamic_patterns
        self._filepath = filepath
        self.literal_valid: list[dict[str, str | int]] = []
        self.literal_invalid: list[dict[str, str | int]] = []
        self.dynamic_proven: list[dict[str, str | int]] = []
        self.dynamic_unproven: list[dict[str, str | int]] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Visit a Call node and enforce all matching contract pairs."""
        call_name = _get_call_name(node)
        if call_name is None or call_name not in self._method_map:
            self.generic_visit(node)
            return

        matching_pairs = self._method_map[call_name]
        for pair in matching_pairs:
            self._enforce_pair(node, pair)

        self.generic_visit(node)

    def _enforce_pair(self, node: ast.Call, pair: ContractPair) -> None:
        """Enforce a single contract pair against a call node."""
        arg_expr = _resolve_arg_node(node, pair.param, pair.param_position)
        if arg_expr is None:
            return

        if isinstance(arg_expr, (ast.Tuple, ast.List)):
            self._enforce_collection(node, arg_expr, pair)
            return

        kind, literal_value = _classify_expr(arg_expr)

        record: dict[str, str | int] = {
            "file": str(self._filepath),
            "line": node.lineno,
            "method": pair.method,
            "param": pair.param,
            "kind": kind,
        }

        if kind == "literal":
            record["value"] = literal_value if literal_value is not None else ""
            if literal_value in pair.allowed_literals:
                self.literal_valid.append(record)
            else:
                if "__dynamic_only__" not in pair.allowed_literals:
                    self.literal_invalid.append(record)
            return

        if pair.dynamic_policy == "prove_dynamic":
            matched, pat_desc = _matches_dynamic_pattern(
                arg_expr,
                self._dynamic_patterns,
            )
            if matched:
                record["pattern"] = pat_desc if pat_desc else "unknown"
                self.dynamic_proven.append(record)
            else:
                record["ast_dump"] = ast.dump(arg_expr)
                self.dynamic_unproven.append(record)

        elif pair.dynamic_policy == "hybrid_warn":
            record["ast_dump"] = ast.dump(arg_expr)
            self.dynamic_proven.append(record)

    def _enforce_collection(
        self, node: ast.Call, collection: ast.Tuple | ast.List, pair: ContractPair
    ) -> None:
        """Unpack a tuple/list argument and validate each element individually."""
        for elt in collection.elts:
            kind, literal_value = _classify_expr(elt)
            record: dict[str, str | int] = {
                "file": str(self._filepath),
                "line": node.lineno,
                "method": pair.method,
                "param": pair.param,
                "kind": kind,
            }
            if kind == "literal":
                record["value"] = literal_value if literal_value is not None else ""
                if literal_value in pair.allowed_literals:
                    self.literal_valid.append(record)
                elif "__dynamic_only__" not in pair.allowed_literals:
                    self.literal_invalid.append(record)
            else:
                if pair.dynamic_policy == "prove_dynamic":
                    matched, pat_desc = _matches_dynamic_pattern(elt, self._dynamic_patterns)
                    if matched:
                        record["pattern"] = pat_desc if pat_desc else "unknown"
                        self.dynamic_proven.append(record)
                    else:
                        record["ast_dump"] = ast.dump(elt)
                        self.dynamic_unproven.append(record)
                elif pair.dynamic_policy == "hybrid_warn":
                    record["ast_dump"] = ast.dump(elt)
                    self.dynamic_proven.append(record)


# ══════════════════════════════════════════════════════════
# Per-Pair Drift Tracking
# ══════════════════════════════════════════════════════════


def _count_callsites_per_pair(
    scan_results: dict[str, list[dict[str, str | int]]],
) -> dict[tuple[str, str], int]:
    """Count total callsites per ``(method, param)`` pair."""
    counts: dict[tuple[str, str], int] = defaultdict(int)

    for category in ("literal_valid", "literal_invalid", "dynamic_proven", "dynamic_unproven"):
        for record in scan_results.get(category, []):
            key = (str(record["method"]), str(record["param"]))
            counts[key] += 1

    return dict(counts)


def check_per_pair_drift(
    pairs: list[ContractPair],
    callsite_counts: dict[tuple[str, str], int],
) -> list[str]:
    """Check per-pair callsite drift against baselines."""
    violations: list[str] = []

    for pair in pairs:
        if pair.baseline_callsites is None:
            continue

        key = (pair.method, pair.param)
        actual = callsite_counts.get(key, 0)
        baseline = pair.baseline_callsites

        if baseline == 0:
            if actual > 0:
                violations.append(
                    f"{pair.method}.{pair.param}: "
                    f"baseline=0, actual={actual}, new callsites appeared"
                )
            continue

        drift = abs(actual - baseline) / baseline
        threshold = pair.drift_threshold_percent / 100

        if drift > threshold:
            violations.append(
                f"{pair.method}.{pair.param}: "
                f"baseline={baseline}, actual={actual}, "
                f"drift={drift:.0%} exceeds {pair.drift_threshold_percent}%"
            )

    return violations


# ══════════════════════════════════════════════════════════
# Snapshot Metrics
# ══════════════════════════════════════════════════════════


def _load_baseline(catalog: ContractCatalog, repo_root: pathlib.Path) -> dict:
    """Load baseline counts JSON, returning empty dict if absent."""
    if not catalog.baseline.file:
        return {}
    bl_path = repo_root / catalog.baseline.file
    if not bl_path.is_file():
        return {}
    try:
        raw = json.loads(bl_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def contract_catalog() -> ContractCatalog:
    """Load the contract catalog once per session."""
    return load_catalog()


@pytest.fixture(scope="session")
def contract_scan_results(
    contract_catalog: ContractCatalog,
) -> dict[str, list[dict[str, str | int]]]:
    """Scan the entire repo and return categorized results."""
    repo_root = get_repo_root()
    py_files = iter_python_files(
        repo_root,
        contract_catalog.scan.include_globs,
        contract_catalog.scan.exclude_globs,
    )

    all_valid: list[dict[str, str | int]] = []
    all_invalid: list[dict[str, str | int]] = []
    all_proven: list[dict[str, str | int]] = []
    all_unproven: list[dict[str, str | int]] = []

    for path in py_files:
        tree = parse_python_file(path)
        if tree is None:
            continue

        visitor = ContractCallVisitor(
            contract_catalog.pairs,
            contract_catalog.dynamic_sources,
            path.relative_to(repo_root),
        )
        visitor.visit(tree)

        all_valid.extend(visitor.literal_valid)
        all_invalid.extend(visitor.literal_invalid)
        all_proven.extend(visitor.dynamic_proven)
        all_unproven.extend(visitor.dynamic_unproven)

    total = len(all_valid) + len(all_invalid) + len(all_proven) + len(all_unproven)

    logger.info(
        "contract_scan_snapshot total=%d valid=%d invalid=%d proven=%d unproven=%d files=%d",
        total,
        len(all_valid),
        len(all_invalid),
        len(all_proven),
        len(all_unproven),
        len(py_files),
    )

    for dyn in all_unproven:
        logger.warning(
            "contract_dynamic_unproven file=%s line=%s method=%s param=%s",
            dyn["file"],
            dyn["line"],
            dyn["method"],
            dyn["param"],
        )

    return {
        "literal_valid": all_valid,
        "literal_invalid": all_invalid,
        "dynamic_proven": all_proven,
        "dynamic_unproven": all_unproven,
    }


# ══════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════


class TestRepositoryContractCalls:
    """Contract enforcement tests for the enrichment engine."""

    def test_catalog_loads_successfully(
        self,
        contract_catalog: ContractCatalog,
    ) -> None:
        """Contract catalog YAML is valid and loads without error."""
        assert contract_catalog.schema_version == "2.0.0"
        assert len(contract_catalog.pairs) > 0
        assert len(contract_catalog.scan.include_globs) > 0
        assert len(contract_catalog.scan.exclude_globs) > 0

    def test_no_duplicate_pairs_in_catalog(
        self,
        contract_catalog: ContractCatalog,
    ) -> None:
        """No duplicate ``(method, param)`` entries exist in the catalog."""
        seen: set[tuple[str, str]] = set()
        for pair in contract_catalog.pairs:
            key = (pair.method, pair.param)
            assert key not in seen, f"Duplicate contract pair: {key}"
            seen.add(key)

    def test_all_pairs_have_nonempty_allowlists(
        self,
        contract_catalog: ContractCatalog,
    ) -> None:
        """Every pair has at least one allowed literal value."""
        for pair in contract_catalog.pairs:
            assert len(pair.allowed_literals) > 0, (
                f"{pair.method}.{pair.param} has empty allowed_literals"
            )

    def test_no_invalid_literal_calls(
        self,
        contract_scan_results: dict[str, list[dict[str, str | int]]],
    ) -> None:
        """FAIL: No callsite passes a literal value outside the allowlist."""
        invalid = contract_scan_results["literal_invalid"]
        if invalid:
            lines = ["Literal contract violations found:"]
            for v in invalid:
                lines.append(
                    f"  {v['file']}:{v['line']} — {v['method']}({v['param']}={v['value']!r})"
                )
            pytest.fail("\n".join(lines))

    def test_no_unproven_dynamic_calls(
        self,
        contract_scan_results: dict[str, list[dict[str, str | int]]],
    ) -> None:
        """FAIL: All dynamic expressions for prove_dynamic pairs must match patterns."""
        unproven = contract_scan_results["dynamic_unproven"]
        if unproven:
            lines = ["Unproven dynamic expressions found (prove_dynamic pairs):"]
            for v in unproven:
                lines.append(
                    f"  {v['file']}:{v['line']} — "
                    f"{v['method']}({v['param']}=<dynamic>) "
                    f"AST: {v.get('ast_dump', 'N/A')[:80]}"
                )
            pytest.fail("\n".join(lines))

    def test_per_pair_drift_enforcement(
        self,
        contract_catalog: ContractCatalog,
        contract_scan_results: dict[str, list[dict[str, str | int]]],
    ) -> None:
        """Per-pair drift tracking against baselines."""
        callsite_counts = _count_callsites_per_pair(contract_scan_results)
        violations = check_per_pair_drift(contract_catalog.pairs, callsite_counts)

        if violations:
            lines = ["Per-pair drift violations found:"]
            lines.extend(f"  {v}" for v in violations)
            pytest.fail("\n".join(lines))

    def test_baseline_drift_global_warn_only(
        self,
        contract_catalog: ContractCatalog,
        contract_scan_results: dict[str, list[dict[str, str | int]]],
    ) -> None:
        """Global baseline drift emits a warning, does not fail."""
        repo_root = get_repo_root()
        baseline = _load_baseline(contract_catalog, repo_root)
        if not baseline:
            logger.info("contract_baseline_absent action=skip_drift_check")
            return

        total_now = sum(
            len(contract_scan_results[k])
            for k in ("literal_valid", "literal_invalid", "dynamic_proven", "dynamic_unproven")
        )
        total_prev = baseline.get("total_callsites", 0)
        if total_prev == 0:
            return

        drift_pct = abs(total_now - total_prev) / total_prev * 100
        threshold = contract_catalog.baseline.drift_threshold_percent

        if drift_pct > threshold:
            logger.warning(
                "contract_baseline_drift_global previous=%d current=%d drift=%.2f%% threshold=%d",
                total_prev,
                total_now,
                drift_pct,
                threshold,
            )
