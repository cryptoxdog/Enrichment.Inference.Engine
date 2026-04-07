#!/usr/bin/env python3
"""Portable terminology guard (replaces grep -P in compliance.yml for macOS/Linux)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("print(", re.compile(r"\bprint\s*\(")),
    ("Optional[", re.compile(r"\bOptional\s*\[")),
    ("List[", re.compile(r"\bList\s*\[")),
    ("Dict[", re.compile(r"\bDict\s*\[")),
]


def main() -> int:
    """One violation count per pattern if any file matches (parity with compliance.yml)."""
    all_py: list[Path] = []
    for root in (REPO_ROOT / "app", REPO_ROOT / "tests"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            all_py.append(path)

    violations = 0
    for label, rx in PATTERNS:
        # print() is disallowed in engine (app/) only — tests may reference it in docstrings/AST checks
        paths = (
            [p for p in all_py if p.is_relative_to(REPO_ROOT / "app")]
            if label == "print("
            else all_py
        )
        found: list[Path] = []
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            if rx.search(text):
                found.append(path)
        if found:
            print(f"Found forbidden term: {label}")
            for path in found:
                print(f"  {path.relative_to(REPO_ROOT)}")
            violations += 1
    if violations:
        print("\nUse: list[T], T | None, structlog instead of print()", file=sys.stderr)
        return 1
    print("Terminology is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
