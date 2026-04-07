#!/usr/bin/env python3
"""Run shell commands from l9_contract_control select-gates JSON (stdin or file)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) > 1:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        payload = json.load(sys.stdin)

    commands = payload.get("commands", [])
    if not commands:
        print("[pr] select-gates: no commands selected")
        return 0

    seen: set[str] = set()
    ordered: list[str] = []
    for command in commands:
        if command not in seen:
            seen.add(command)
            ordered.append(command)

    for command in ordered:
        print(f"[pr] running: {command}")
        completed = subprocess.run(command, shell=True, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
