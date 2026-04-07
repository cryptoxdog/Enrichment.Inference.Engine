# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, claude, delta]
# owner: platform
# status: active
# token_estimate: 210
# ssot_for: [claude-specific-delta]
# load_when: [claude_code, claude_pr_review]
# references: [AGENT.md, GUARDRAILS.md, ARCHITECTURE.md]
# --- /L9_META ---

# CLAUDE.md — Claude-Specific Delta

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> Delta-only file. AGENT.md is the primary governance document. Load AGENT.md first.
> This file contains ONLY Claude-specific overrides and additions not in AGENT.md.

---

## Claude-Specific Loading Order

1. AGENT_BOOTSTRAP.md — context strategy
2. AGENT.md — all contracts, tiers, forbidden patterns
3. GUARDRAILS.md — all prohibitions
4. ARCHITECTURE.md — system topology
5. This file — Claude delta only

---

## Terminology Corrections (Claude Output Guard)

Do NOT use these phrases in responses or code comments:

| Banned | Use Instead |
|---|---|
| "best practices" | Cite the specific contract ID (e.g., C-07 requires...) |
| "as needed" | Specify the exact condition |
| "you may want to" | Make a binary recommendation |
| "consider using" | State whether it is required or optional per contract |
| "it depends" | State which invariant or contract governs the decision |
| "generally speaking" | Reference the specific rule that applies |

---

## Claude Review Output Format

When producing PR review comments, use this exact template:

```
CONTRACT C-{N} VIOLATION — {rule-name}
File: {path} Line: {line}
Found: {offending_code}
Required: {corrected_code}
Evidence: AGENT.md Forbidden Patterns, .cursorrules CONTRACT {N}
```

For approvals:
```
All 20 contracts verified. No violations found.
Tier assessment: T{N} change. {0/1/2} reviewers required.
make agent-check gates: [verified / not verified — request confirmation]
```

---

## Ruff Ignore List — Complete (Do Not Restate Inline)

Do NOT restate these in code comments. Reference pyproject.toml [tool.ruff.lint] ignore.
Full list as of SHA 358d15d: E501, TC001, TC002, TC003, SIM105, TRY003, TRY400, ARG001, ARG002, ARG003, B007, B008.

---

## CI Response Protocol

| CI Step Fails | Claude Action |
|---|---|
| validate | Fix Python syntax or YAML before any other work |
| lint-ruff | Run make agent-fix then re-push |
| lint-mypy | Log warning; do not block (WAIVER-001) |
| test (coverage < 60%) | Add tests until coverage >= 60% |
| compliance-chassis | Remove FastAPI import from engine/; verify handler boundary |
| compliance-terminology | Replace print(), Optional[], List[], Dict[] |
| security-pip-audit | Log warning; do not block (WAIVER-002) |
| semgrep | Read .semgrep/ rules, fix violation, escalate if unclear |
