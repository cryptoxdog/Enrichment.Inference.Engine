"""Automated enforcement of field naming conventions.

Rules enforced:
- No camelCase Pydantic/dataclass fields
- No flatcase fields (long single-word names)
- No Field(alias=...) usage
- No populate_by_name in model_config
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


def test_no_camelcase_pydantic_fields():
    """No camelCase field names in Pydantic models or dataclasses."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        name = item.target.id
                        if re.match(r"^[a-z]+[A-Z]", name):
                            violations.append(
                                f"{py_file.relative_to(REPO_ROOT)}:{item.lineno} "
                                f"camelCase field '{name}'"
                            )
    assert not violations, "camelCase fields found:\n" + "\n".join(violations)


def test_no_flatcase_pydantic_fields():
    """No flatcase fields (long single-word names > 12 chars).

    Standard English words that happen to exceed 12 chars are excluded.
    """
    allowed_words = {"recommendation", "recommendations", "configuration", "documentation"}
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        name = item.target.id
                        if len(name) > 12 and "_" not in name and name.islower():
                            if name not in allowed_words:
                                violations.append(
                                    f"{py_file.relative_to(REPO_ROOT)}:{item.lineno} "
                                    f"flatcase field '{name}'"
                                )
    assert not violations, "flatcase fields found:\n" + "\n".join(violations)


def test_no_field_aliases():
    """No Field(alias=...) usage in Pydantic models."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.value, ast.Call):
                        for kw in getattr(item.value, "keywords", []):
                            if kw.arg == "alias":
                                name = item.target.id if isinstance(item.target, ast.Name) else "?"
                                violations.append(
                                    f"{py_file.relative_to(REPO_ROOT)}:{item.lineno} "
                                    f"Field alias on '{name}'"
                                )
    assert not violations, "Field aliases found:\n" + "\n".join(violations)


def test_no_populate_by_name():
    """No populate_by_name in model_config."""
    violations = []
    for py_file in _get_engine_py_files():
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == "model_config":
                                src = ast.get_source_segment(source, item) or ""
                                if "populate_by_name" in src:
                                    violations.append(
                                        f"{py_file.relative_to(REPO_ROOT)}:{item.lineno} "
                                        f"populate_by_name in model_config"
                                    )
    assert not violations, "populate_by_name found:\n" + "\n".join(violations)
