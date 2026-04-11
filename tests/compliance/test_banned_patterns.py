"""Automated enforcement of banned patterns for the post-envelope constitution."""

from __future__ import annotations

import ast
import re
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


def test_no_eval_exec_compile() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile"}:
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} {node.func.id}()"
                    )

    assert not violations, "Banned function calls found:\n" + "\n".join(violations)


def test_no_bare_except() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} bare except")

    assert not violations, "Bare except handlers found:\n" + "\n".join(violations)


def test_no_fastapi_in_engine_only_modules() -> None:
    allowed_files = {
        REPO_ROOT / "app" / "main.py",
        REPO_ROOT / "app" / "api" / "v1" / "chassis_endpoint.py",
    }
    allowed_dirs = {"app/api/", "app/middleware/", "app/core/", "app/bootstrap/"}
    allowed_paths = {"app/score/score_api.py"}
    violations: list[str] = []

    for py_file in _get_app_py_files():
        rel = py_file.relative_to(REPO_ROOT)
        rel_str = str(rel)
        if py_file in allowed_files:
            continue
        if any(d in rel_str for d in allowed_dirs):
            continue
        if rel_str in allowed_paths:
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("fastapi")
            ):
                violations.append(f"{rel}:{node.lineno} FastAPI import in engine-only module")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "fastapi" or alias.name.startswith("fastapi."):
                        violations.append(
                            f"{rel}:{node.lineno} fastapi import in engine-only module"
                        )

    assert not violations, "FastAPI drift found:\n" + "\n".join(violations)


def test_no_hardcoded_api_keys() -> None:
    patterns = [
        r'(?:api_key|apikey|secret_key)\s*=\s*["\'][a-zA-Z0-9\-\._]{20,}["\']',
        r"pplx-[a-zA-Z0-9]{20,}",
        r"sk-[a-zA-Z0-9]{20,}",
    ]
    violations: list[str] = []

    for py_file in _get_app_py_files():
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{index} potential hardcoded secret"
                    )

    assert not violations, "Potential hardcoded secrets found:\n" + "\n".join(violations)


def test_no_print_calls_in_app_code() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} print() call")

    assert not violations, "print() calls found:\n" + "\n".join(violations)


def test_no_deprecated_local_dispatch_imports_in_active_runtime_bundle() -> None:
    violations: list[str] = []

    banned_tokens = [
        "from chassis.router import",
        "import chassis.router",
        "from chassis.registry import",
        "import chassis.registry",
        "inflate_ingress(",
        "deflate_egress(",
    ]

    for py_file in ACTIVE_TRANSPORT_BUNDLE:
        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(REPO_ROOT)
        for token in banned_tokens:
            if token in content:
                violations.append(f"{rel}: contains deprecated local dispatch token {token!r}")

    assert not violations, "Deprecated local dispatch usage found:\n" + "\n".join(violations)


def test_no_silent_exception_swallowing() -> None:
    violations: list[str] = []

    for py_file in _get_app_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} except Exception: pass"
                        )

    assert not violations, "Silent exception swallowing found:\n" + "\n".join(violations)
