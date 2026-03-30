"""Automated enforcement of import resolution.

Rules enforced:
- Every internal import must resolve to an existing file
- No circular imports from engine to API layer
- No star imports
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
ENGINE_DIR = REPO_ROOT / "app"


def _get_engine_py_files():
    if not ENGINE_DIR.exists():
        return []
    return list(ENGINE_DIR.rglob("*.py"))


def test_all_internal_imports_resolve():
    """Every internal import (app.*) must resolve to an existing module."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("app."):
                    mod_path = REPO_ROOT / node.module.replace(".", "/")
                    if not (
                        mod_path.with_suffix(".py").exists() or (mod_path / "__init__.py").exists()
                    ):
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} "
                            f"unresolved import '{node.module}'"
                        )
    assert not violations, "Phantom imports:\n" + "\n".join(violations)


def test_no_engine_to_api_imports():
    """Engine modules must not import from the API layer.

    Allowed exceptions: handlers.py (chassis bridge).
    """
    violations = []
    for py_file in _get_engine_py_files():
        rel = py_file.relative_to(REPO_ROOT)
        # Skip API layer files and handlers
        if "api/" in str(rel) or rel.name in ("main.py", "handlers.py"):
            continue
        # Only check engine modules
        if not any(
            d in str(rel) for d in ("engines/", "score/", "health/", "models/", "services/")
        ):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if "api" in parts:
                    violations.append(
                        f"{rel}:{node.lineno} engine imports from API layer: {node.module}"
                    )
    assert not violations, "Engine→API imports:\n" + "\n".join(violations)


def test_no_star_imports():
    """No wildcard imports in engine code."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names:
                for alias in node.names:
                    if alias.name == "*":
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} "
                            f"star import from {node.module}"
                        )
    assert not violations, "Star imports:\n" + "\n".join(violations)
