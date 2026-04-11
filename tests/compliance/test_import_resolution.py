"""Automated enforcement of import resolution and runtime boundary rules."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
APP_DIR = REPO_ROOT / "app"

ACTIVE_TRANSPORT_BUNDLE = {
    REPO_ROOT / "app" / "main.py",
    REPO_ROOT / "app" / "api" / "v1" / "chassis_endpoint.py",
    REPO_ROOT / "app" / "services" / "chassis_handlers.py",
    REPO_ROOT / "app" / "engines" / "orchestration_layer.py",
    REPO_ROOT / "app" / "engines" / "handlers.py",
    REPO_ROOT / "app" / "engines" / "graph_sync_client.py",
}


def _get_app_py_files() -> list[Path]:
    if not APP_DIR.exists():
        return []
    return list(APP_DIR.rglob("*.py"))


def test_all_internal_imports_resolve() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                mod_path = REPO_ROOT / node.module.replace(".", "/")
                if not (
                    mod_path.with_suffix(".py").exists() or (mod_path / "__init__.py").exists()
                ):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} unresolved import '{node.module}'"
                    )

    assert not violations, "Unresolved internal imports found:\n" + "\n".join(violations)


def test_no_engine_to_api_imports_in_engine_only_modules() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        rel = py_file.relative_to(REPO_ROOT)

        if "app/api/" in str(rel):
            continue
        if py_file in ACTIVE_TRANSPORT_BUNDLE:
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if "api" in parts:
                    violations.append(f"{rel}:{node.lineno} engine-only module imports API layer")

    assert not violations, "Engine-to-API imports found:\n" + "\n".join(violations)


def test_no_star_imports() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names:
                for alias in node.names:
                    if alias.name == "*":
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} star import from {node.module}"
                        )

    assert not violations, "Star imports found:\n" + "\n".join(violations)


def test_no_active_runtime_imports_of_deprecated_local_dispatch() -> None:
    violations: list[str] = []

    for py_file in ACTIVE_TRANSPORT_BUNDLE:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        rel = py_file.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in {"chassis.router", "chassis.registry"}:
                    violations.append(f"{rel}:{node.lineno} imports deprecated {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"chassis.router", "chassis.registry"}:
                        violations.append(f"{rel}:{node.lineno} imports deprecated {alias.name}")

    assert not violations, "Deprecated local dispatch imports found:\n" + "\n".join(violations)
