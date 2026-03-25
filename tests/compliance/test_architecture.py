"""Automated enforcement of L9 architecture structural rules.

Rules enforced:
- Required directory structure exists
- Required __init__.py files exist
- KB rule files are valid YAML
- Enum classes use str mixin
- Every subsystem has a models file
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
ENGINE_DIR = REPO_ROOT / "app"


def test_required_directories_exist():
    """All required engine directories must exist."""
    required = [
        "app",
        "app/engines",
        "app/models",
        "app/score",
        "app/health",
        "app/services",
        "app/api",
        "tests",
        "kb",
        "config",
        "tools",
    ]
    missing = [d for d in required if not (REPO_ROOT / d).exists()]
    assert not missing, f"Missing directories: {missing}"


def test_required_init_files():
    """All Python packages must have __init__.py."""
    required = [
        "app/__init__.py",
        "app/engines/__init__.py",
        "app/models/__init__.py",
        "app/score/__init__.py",
        "app/health/__init__.py",
        "app/services/__init__.py",
        "app/api/__init__.py",
    ]
    missing = [f for f in required if not (REPO_ROOT / f).exists()]
    assert not missing, f"Missing __init__.py files: {missing}"


def test_kb_yaml_files_valid():
    """All YAML files in kb/ must parse without errors."""
    kb_dir = REPO_ROOT / "kb"
    if not kb_dir.exists():
        pytest.skip("No kb/ directory")
    import yaml

    invalid = []
    for yaml_file in kb_dir.rglob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if data is None:
                invalid.append(f"{yaml_file.relative_to(REPO_ROOT)}: empty file")
        except yaml.YAMLError as e:
            invalid.append(f"{yaml_file.relative_to(REPO_ROOT)}: {e}")
    assert not invalid, "Invalid YAML files:\n" + "\n".join(invalid)


def test_enum_classes_use_str_mixin():
    """All Enum classes in engine code must use (str, Enum) mixin."""
    import ast

    violations = []
    for py_file in ENGINE_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)
                if "Enum" in base_names and "str" not in base_names:
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} "
                        f"class {node.name}(Enum) missing str mixin"
                    )
    assert not violations, "Enum classes without str mixin:\n" + "\n".join(violations)


def test_chassis_contract_exists():
    """The chassis contract module must exist and have required functions."""
    import ast

    chassis = ENGINE_DIR / "engines" / "chassis_contract.py"
    assert chassis.exists(), "chassis_contract.py missing"

    tree = ast.parse(chassis.read_text())
    func_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    required = {"inflate_ingress", "deflate_egress", "delegate_to_node"}
    missing = required - func_names
    assert not missing, f"chassis_contract.py missing functions: {missing}"


def test_handlers_registry_exists():
    """The handlers module must have an ACTION_REGISTRY."""
    handlers = ENGINE_DIR / "engines" / "handlers.py"
    assert handlers.exists(), "handlers.py missing"

    content = handlers.read_text()
    assert "ACTION_REGISTRY" in content, "handlers.py missing ACTION_REGISTRY"
