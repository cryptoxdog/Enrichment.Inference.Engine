#!/usr/bin/env python3
"""Universal AI code review script.

Usage:
    # Review staged changes (pre-commit)
    python scripts/ai_review.py --mode staged

    # Review a diff file (CI)
    python scripts/ai_review.py --mode file --diff-path pr_diff.txt

    # Review specific files
    python scripts/ai_review.py --mode files --paths app/main.py app/pipeline.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import httpx

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM_PROMPT = """You are a senior Python engineer performing a security-focused code review.
Analyze the provided code for:
1. **Bugs**: logic errors, off-by-one, None dereference, missing awaits on async calls
2. **Security**: injection, auth bypass, SSRF, path traversal, unvalidated input
3. **Concurrency**: race conditions, deadlocks, unbounded task fan-out, missing semaphores
4. **Error handling**: bare except, swallowed exceptions, missing finally/cleanup
5. **Performance**: N+1 patterns, unbounded memory, blocking calls in async context

Rules:
- Do NOT flag style, formatting, or naming.
- Do NOT flag missing docstrings or type hints.
- ONLY flag issues with real impact.

Output STRICT JSON (no markdown fences):
{
  "issues": [
    {
      "severity": "critical|high|medium",
      "file": "filename or 'diff'",
      "line_hint": "code snippet or line ref",
      "description": "what is wrong",
      "suggestion": "how to fix"
    }
  ],
  "summary": "1-2 sentence overall assessment",
  "block": true/false  // true only if critical/high issues exist
}
If no issues, return: {"issues": [], "summary": "No issues found.", "block": false}
"""


def get_api_key() -> str:
    import os

    key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not key:
        print("ERROR: PERPLEXITY_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


def call_review(code: str, api_key: str, model: str = "sonar-pro") -> dict:
    """Send code to Perplexity for review."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Review this code:\n```\n{code[:100_000]}\n```"},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(content)


def get_staged_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_file_contents(paths: list[str]) -> str:
    chunks = []
    for p in paths:
        path = Path(p)
        if path.exists() and path.stat().st_size < 80_000:
            chunks.append(f"# FILE: {p}\n{path.read_text()}")
    return "\n\n".join(chunks)


def print_results(result: dict) -> bool:
    """Print findings, return True if should block."""
    issues = result.get("issues", [])
    summary = result.get("summary", "")
    block = result.get("block", False)

    if not issues:
        print("\n✅ AI Review: No issues found.")
        print(f"   {summary}")
        return False

    print(f"\n⚠️  AI Review: {len(issues)} issue(s) found")
    print(f"   {summary}\n")

    for i, issue in enumerate(issues, 1):
        sev = issue.get("severity", "?").upper()
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(sev, "⚪")
        print(f"  {icon} [{sev}] {issue.get('description', '')}")
        if issue.get("file"):
            print(f"     File: {issue['file']}")
        if issue.get("line_hint"):
            print(f"     Near: {issue['line_hint']}")
        if issue.get("suggestion"):
            print(f"     Fix:  {issue['suggestion']}")
        print()

    if block:
        print("❌ BLOCKING — critical/high severity issues must be fixed.\n")
    return block


def main():
    parser = argparse.ArgumentParser(description="AI Code Review via Perplexity")
    parser.add_argument("--mode", choices=["staged", "file", "files"], default="staged")
    parser.add_argument("--diff-path", help="Path to diff file (mode=file)")
    parser.add_argument("--paths", nargs="*", help="File paths to review (mode=files)")
    parser.add_argument("--model", default="sonar-pro", help="Perplexity model")
    parser.add_argument("--no-block", action="store_true", help="Never exit non-zero")
    args = parser.parse_args()

    api_key = get_api_key()

    if args.mode == "staged":
        code = get_staged_diff()
        if not code.strip():
            print("No staged changes to review.")
            sys.exit(0)
    elif args.mode == "file":
        if not args.diff_path:
            print("ERROR: --diff-path required for mode=file", file=sys.stderr)
            sys.exit(1)
        code = Path(args.diff_path).read_text()
    elif args.mode == "files":
        if not args.paths:
            print("ERROR: --paths required for mode=files", file=sys.stderr)
            sys.exit(1)
        code = get_file_contents(args.paths)
    else:
        sys.exit(1)

    print(f"🔍 Running AI review ({args.model})...")
    result = call_review(code, api_key, model=args.model)
    should_block = print_results(result)

    if should_block and not args.no_block:
        sys.exit(1)


if __name__ == "__main__":
    main()
