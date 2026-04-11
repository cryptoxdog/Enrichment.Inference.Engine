# CLAUDE.md — Claude-Specific Instructions

> **Primary document**: `AGENTS.md` — read that first.
> This file contains Claude-specific additions only.

---

## Loading Order

1. `AGENTS.md` — contracts, tiers, forbidden patterns
2. `ARCHITECTURE.md` — system topology
3. This file — Claude-specific guidance

---

## Output Guidelines

### Banned Phrases

Do NOT use vague language. Be specific.

| Banned | Use Instead |
|--------|-------------|
| "best practices" | Cite the specific contract (e.g., "C-07 requires...") |
| "as needed" | Specify the exact condition |
| "you may want to" | Make a binary recommendation |
| "consider using" | State whether required or optional per contract |
| "it depends" | State which contract governs the decision |
| "generally speaking" | Reference the specific rule |

---

## PR Review Format

### For Violations

```
CONTRACT C-{N} VIOLATION — {rule-name}
File: {path} Line: {line}
Found: {offending_code}
Required: {corrected_code}
```

### For Approvals

```
All contracts verified. No violations found.
Tier: T{N} change — {0/1/2} reviewers required.
```

---

## CI Response

| Failed Job | Action |
|------------|--------|
| `validate` | Fix syntax/YAML first |
| `lint-ruff` | Run `make agent-fix` |
| `lint-mypy` | Log warning only (WAIVER-001) |
| `test` | Fix tests, ensure coverage >= 60% |
| `compliance-*` | Fix the violation |
| `security-*` | Log warning only (waivers apply) |

---

## Ruff Ignores

Do not add `# noqa` comments for these — they're globally ignored in `pyproject.toml`:

`E501`, `TC001`, `TC002`, `TC003`, `SIM105`, `TRY003`, `TRY400`, `ARG001`, `ARG002`, `ARG003`, `B007`, `B008`

---

## Key Commands

```bash
make agent-check  # Full 7-gate validation
make agent-fix    # Auto-fix lint/format
make test         # Run tests
make verify       # Contract verification
```
