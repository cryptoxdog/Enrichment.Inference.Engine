#!/usr/bin/env python3
"""Optional local check mirroring l9-constitution-gate contract-bound-change-gate (PR diff)."""

from __future__ import annotations

import argparse
import subprocess
import sys

CONTRACT_BOUND_PREFIXES = (
    "app/api/v1/",
    "app/agents/",
    "app/engines/",
    "app/services/",
    "chassis/",
)
CONTRACT_FILES_PREFIXES = (
    "docs/contracts/",
    "tests/contracts/",
    "scripts/verify_node_constitution.py",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    diff = subprocess.check_output(
        ["git", "diff", "--name-only", args.base, args.head],
        text=True,
    ).splitlines()

    touched_bound = [p for p in diff if any(p.startswith(x) for x in CONTRACT_BOUND_PREFIXES)]
    touched_contracts = [p for p in diff if any(p.startswith(x) for x in CONTRACT_FILES_PREFIXES)]

    if touched_bound and not touched_contracts:
        msg = (
            "Contract-bound application files changed without corresponding "
            "docs/contracts, tests/contracts, or constitution verifier updates."
        )
        print(msg, file=sys.stderr)
        return 1
    print("contract-bound local check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
