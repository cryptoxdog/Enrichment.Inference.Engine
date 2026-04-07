#!/usr/bin/env python3
"""KB YAML schema validation — parity with compliance.yml (extended for list-root rule files)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _check_rule_dict(rule: object, f: Path, label: str) -> list[str]:
    err: list[str] = []
    if not isinstance(rule, dict):
        err.append(f"{f}: {label} must be a mapping")
        return err
    if "field" not in rule:
        err.append(f"{f}: {label} missing required key: field")
    if "conditions" not in rule and "when" not in rule:
        err.append(f"{f}: {label} missing conditions/when block")
    return err


def main() -> int:
    errors: list[str] = []
    kb_dir = REPO_ROOT / "kb"
    if not kb_dir.is_dir():
        print("No kb/ directory found, skipping")
        return 0

    for f in kb_dir.glob("*.yaml"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data is None:
                continue
            if isinstance(data, list):
                for i, rule in enumerate(data):
                    if not isinstance(rule, dict):
                        errors.append(f"{f}: Item {i} must be a mapping")
                        continue
                    # Inference-style rules (plastics_recycling.yaml): name + conditions, no top-level field
                    if "name" in rule and "conditions" in rule:
                        continue
                    if "rules" in rule:
                        errors.append(f"{f}: Unexpected nested 'rules' in list item {i}")
                        continue
                    errors.extend(_check_rule_dict(rule, f, f"Rule {i}"))
            elif isinstance(data, dict):
                if "rules" in data:
                    for i, rule in enumerate(data["rules"]):
                        errors.extend(_check_rule_dict(rule, f, f"Rule {i}"))
            else:
                errors.append(f"{f}: Root must be a YAML mapping or a list of rule objects")
        except yaml.YAMLError as e:
            errors.append(f"{f}: {e}")

    if errors:
        for e in errors:
            print(f"  {e}")
        print(f"\n{len(errors)} KB validation error(s)", file=sys.stderr)
        return 1
    print("All KB YAML files are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
