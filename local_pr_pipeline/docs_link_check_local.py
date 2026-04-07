#!/usr/bin/env python3
"""Portable markdown link check (readme/, docs/, root *.md) — no grep -P."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def check_file(md_path: Path) -> list[str]:
    broken: list[str] = []
    text = md_path.read_text(encoding="utf-8", errors="replace")
    base_dir = md_path.parent
    for _m, target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (target.startswith("./") or target.startswith("../")):
            continue
        resolved = (base_dir / target).resolve()
        try:
            resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            broken.append(f"{md_path}: {target} (escapes repo)")
            continue
        if not resolved.is_file() and not resolved.is_dir():
            broken.append(f"{md_path}: {target}")
    return broken


def main() -> int:
    broken_all: list[str] = []
    globs = [REPO_ROOT.glob("*.md")]
    for sub in ("readme", "docs"):
        p = REPO_ROOT / sub
        if p.is_dir():
            globs.append(p.rglob("*.md"))
    seen: set[Path] = set()
    for g in globs:
        for f in g:
            if f in seen:
                continue
            seen.add(f)
            broken_all.extend(check_file(f))
    if broken_all:
        print("Broken internal link(s):", file=sys.stderr)
        for line in broken_all:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("All checked markdown links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
