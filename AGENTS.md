# AGENTS.md — Enrichment.Inference.Engine

## Agent Operating Model

This document defines the rules of engagement for AI agents (Manus, Copilot, Cursor, etc.) operating on this repository.

### Autonomy Tiers

| Tier | Scope | Allowed Without Human Review |
|------|-------|------------------------------|
| **T0 — Read-Only** | Browse, index, analyze, report | Always |
| **T1 — Lint & Fix** | Auto-fix lint, formatting, import ordering | Always |
| **T2 — Test & CI** | Add/modify tests, CI config, pre-commit | PR required |
| **T3 — Engine Logic** | Modify `app/engines/`, `app/score/`, `app/health/` | PR + review required |
| **T4 — Contract** | Modify `chassis_contract.py`, `handlers.py`, `graph_sync_client.py` | PR + 2 reviewers |
| **T5 — Schema** | Modify `app/models/`, `kb/` rule files | PR + 2 reviewers + CI green |

### First-Order Thinking Gates

Before any modification, run the 5 Gates:

1. **GATE 1 — Functional before cosmetic.** Does this change make the engine work better, or just look better?
2. **GATE 2 — Scope check.** Is this change within the PR's stated scope?
3. **GATE 3 — Contract preservation.** Does this change break any chassis/graph/score contract?
4. **GATE 4 — Test coverage.** Does this change have corresponding test coverage?
5. **GATE 5 — Rollback safety.** Can this change be reverted without data loss?

### CI Requirements

All PRs must pass:
- `make lint` — Ruff + MyPy
- `make test` — pytest with coverage
- `make audit` — 27-rule audit engine
- `make verify` — Contract verification
- Compliance tests (banned patterns, field names, import resolution, architecture)
- Contract call enforcement (repository_contract_pairs.yaml)

### Directory Ownership

| Directory | Owner | Agent Tier |
|-----------|-------|------------|
| `app/engines/` | Engine team | T3+ |
| `app/engines/chassis_contract.py` | Platform team | T4+ |
| `app/engines/handlers.py` | Platform team | T4+ |
| `app/engines/graph_sync_client.py` | Platform team | T4+ |
| `app/models/` | Schema team | T5 |
| `app/score/` | Score team | T3+ |
| `app/health/` | Health team | T3+ |
| `app/api/` | API team | T3+ |
| `app/services/` | Services team | T3+ |
| `kb/` | Knowledge team | T5 |
| `tests/` | Any | T2+ |
| `tools/` | Platform team | T2+ |
| `.github/` | Platform team | T2+ |

### Prohibited Actions

- **Never** modify `chassis_contract.py` without updating `handlers.py` in the same PR
- **Never** add new `ACTION_REGISTRY` entries without corresponding handler + test
- **Never** introduce FastAPI imports in engine modules (chassis isolation)
- **Never** use `eval()`, `exec()`, `compile()`, `pickle`
- **Never** hardcode API keys, tokens, or secrets
- **Never** use `print()` in engine code (use `structlog`)
- **Never** add Field(alias=...) to Pydantic models
- **Never** use camelCase for Python field names
