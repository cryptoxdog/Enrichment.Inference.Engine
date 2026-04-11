"""Automated enforcement of banned patterns for Enrichment.Inference.Engine.

Rules enforced:
- No eval/exec/compile calls in engine code
- No bare except handlers
- No FastAPI imports in engine modules (chassis isolation)
- No hardcoded API keys/secrets
- No print() in engine code (use structlog)
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
ENGINE_DIR = REPO_ROOT / "app"


def _get_engine_py_files():
    if not ENGINE_DIR.exists():
        return []
    return list(ENGINE_DIR.rglob("*.py"))


def test_no_eval_exec_compile():
    """No eval/exec/compile calls in engine code."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile"):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} {node.func.id}() call"
                    )
    assert not violations, "Banned function calls:\n" + "\n".join(violations)


def test_no_bare_except():
    """No bare except: handlers in engine code."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} bare except:")
    assert not violations, "Bare except handlers:\n" + "\n".join(violations)


def test_no_fastapi_in_engine():
    """No FastAPI imports in engine modules (chassis isolation).

    FastAPI imports are only allowed in:
    - app/api/ (API layer)
    - app/main.py (application entry point)
    - app/engines/handlers.py (chassis bridge)
    """
    allowed_files = {"main.py", "handlers.py"}
    allowed_dirs = {"api/", "middleware/", "core/", "bootstrap/"}
    allowed_paths = {"app/score/score_api.py"}
    violations = []
    for py_file in _get_engine_py_files():
        rel = py_file.relative_to(REPO_ROOT)
        rel_str = str(rel)
        if rel.name in allowed_files:
            continue
        if any(d in rel_str for d in allowed_dirs):
            continue
        if rel_str in allowed_paths:
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("fastapi"):
                    violations.append(f"{rel}:{node.lineno} FastAPI import in engine module")
    assert not violations, "FastAPI imports in engine:\n" + "\n".join(violations)


def test_no_hardcoded_api_keys():
    """No hardcoded API keys or secrets in engine code."""
    violations = []
    patterns = [
        r'(?:api_key|apikey|secret_key)\s*=\s*["\'][a-zA-Z0-9\-._]{20,}["\']',
        r"pplx-[a-zA-Z0-9]{20,}",
        r"sk-[a-zA-Z0-9]{20,}",
    ]
    for py_file in _get_engine_py_files():
        lines = py_file.read_text().split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{i} potential hardcoded secret"
                    )
    assert not violations, "Hardcoded secrets:\n" + "\n".join(violations)


def test_no_print_in_engine():
    """No print() calls in engine code (use structlog)."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} print() call"
                    )
    assert not violations, "print() calls in engine (use structlog):\n" + "\n".join(violations)


def test_no_silent_exception_swallowing():
    """No except Exception: pass patterns."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} except Exception: pass"
                        )
    assert not violations, "Silent exception swallowing:\n" + "\n".join(violations)
