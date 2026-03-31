"""
tests/test_pr20_import_fix.py

Proves PR#20 import path fix is live:
  - rank_fields_by_unlock and RuleRegistry are importable from
    app.engines.inference.rule_loader (corrected path)
  - meta_prompt_planner.py does not contain any reference to the
    old stale path "inference_rule_loader"
  - inference_unlock_scorer.py does not reference the stale path
"""

from __future__ import annotations

import ast
import pathlib


def test_rule_loader_import_resolves():
    """PR#20: rank_fields_by_unlock must be importable from the corrected path."""
    from app.engines.inference.rule_loader import rank_fields_by_unlock, RuleRegistry  # noqa: F401

    assert callable(rank_fields_by_unlock)
    assert RuleRegistry is not None


def test_rank_fields_by_unlock_returns_list():
    """rank_fields_by_unlock must return a list given a registry and entity dict."""
    from app.engines.inference.rule_loader import rank_fields_by_unlock, RuleRegistry

    registry = RuleRegistry(rules=[])
    result = rank_fields_by_unlock(
        registry=registry,
        entity={"material_type": "HDPE"},
        confidence_map={"material_type": 0.85},
    )
    assert isinstance(result, list)


def _find_stale_import(src: str, stale: str) -> list[int]:
    """Return line numbers where stale import name appears in AST import nodes."""
    tree = ast.parse(src)
    bad_lines = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raw = ast.dump(node)
            if stale in raw:
                bad_lines.append(node.lineno)
    return bad_lines


def test_meta_prompt_planner_no_stale_import():
    """PR#20: meta_prompt_planner.py must not reference 'inference_rule_loader'."""
    path = pathlib.Path("app/engines/meta_prompt_planner.py")
    if not path.exists():
        import pytest
        pytest.skip("meta_prompt_planner.py not found in cwd")
    lines = _find_stale_import(path.read_text(), "inference_rule_loader")
    assert lines == [], (
        f"Stale import 'inference_rule_loader' found in meta_prompt_planner.py "
        f"at lines: {lines}"
    )


def test_inference_unlock_scorer_no_stale_import():
    """PR#20: inference_unlock_scorer.py must not reference 'inference_rule_loader'."""
    path = pathlib.Path("app/engines/inference_unlock_scorer.py")
    if not path.exists():
        import pytest
        pytest.skip("inference_unlock_scorer.py not found in cwd")
    lines = _find_stale_import(path.read_text(), "inference_rule_loader")
    assert lines == [], (
        f"Stale import 'inference_rule_loader' found in inference_unlock_scorer.py "
        f"at lines: {lines}"
    )


def test_no_module_level_import_of_stale_path_in_pkg():
    """Broad scan: no Python file in app/engines/ may import inference_rule_loader."""
    import pytest

    engines_dir = pathlib.Path("app/engines")
    if not engines_dir.exists():
        pytest.skip("app/engines/ not found in cwd")

    offenders: list[str] = []
    for py_file in engines_dir.rglob("*.py"):
        try:
            src = py_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if "inference_rule_loader" in src:
            offenders.append(str(py_file))

    assert offenders == [], (
        f"Files still reference stale 'inference_rule_loader': {offenders}"
    )
