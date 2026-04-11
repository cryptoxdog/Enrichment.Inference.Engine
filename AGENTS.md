# AGENTS.md — Enrichment.Inference.Engine

## What This Repo Is

Universal domain-aware entity enrichment API.
Stack: Python 3.12 / FastAPI chassis / Engine layer / Perplexity LLM / Neo4j graph / Redis cache / PostgreSQL state.

---

## Three Rules Every Agent Must Know

1. **Run `make agent-check` before every commit** — all 7 gates must pass.
2. **Respect your Tier** — see Autonomy Tiers below. T4/T5 changes require human review.
3. **This file is law** — if you see a conflict between documents, AGENTS.md wins.

---

## Agent Operating Model

This document defines the rules of engagement for AI agents (Manus, Copilot, Cursor, etc.) operating on this repository.

### Autonomy Tiers

| Tier | Scope | Allowed Without Human Review |
|------|-------|------------------------------|
| **T0 — Read-Only** | Browse, index, analyze, report | Always |
| **T1 — Lint & Fix** | Auto-fix lint, formatting, import ordering | Always |
| **T2 — Test & CI** | Add/modify tests, CI config, pre-commit | PR required |
| **T3 — Engine Logic** | Modify `app/engines/`, `app/score/`, `app/health/` | PR + review required |
| **T4 — Contract** | Modify transport contract bundle (see Protected Files: `chassis/envelope.py`, `chassis_endpoint`, `chassis_handlers`, `handlers.py`, `graph_sync_client.py`) | PR + 2 reviewers |
| **T5 — Schema** | Modify `app/models/`, `kb/` rule files | PR + 2 reviewers + CI green |

### Protected Files — Never Modify Without Human Review (T4/T5)

| File | Tier | Why |
|------|------|-----|
| `chassis/envelope.py` | T4 | TransportPacket inflate/deflate — no FastAPI, no `app/` imports |
| `chassis/router.py` | T4 | Inbound packet dispatch registry wiring |
| `app/api/v1/chassis_endpoint.py` | T4 | Transport-adjacent HTTP routes (e.g. `/v1/outcomes`) |
| `app/services/chassis_handlers.py` | T4 | SDK `register_handler` wiring / graph return channel |
| `app/engines/handlers.py` | T4 | Engine action handlers — keep in sync with envelope + SDK registration |
| `app/engines/graph_sync_client.py` | T4 | Graph protocol contract |
| `app/models/` (all files) | T5 | Pydantic schema — downstream breaking change risk |
| `kb/` rule files | T5 | Knowledge base — requires review + CI green |
| `.github/workflows/` | T2 | CI pipeline integrity |
| `AGENTS.md`, `CLAUDE.md`, `GUARDRAILS.md` | T4 | Governance documents |
| `Dockerfile`, `docker-compose*.yml` | T3 | Infrastructure immutability |

### First-Order Thinking Gates

Before any modification, run the 5 Gates:

1. **GATE 1 — Functional before cosmetic.** Does this change make the engine work better, or just look better?
2. **GATE 2 — Scope check.** Is this change within the PR's stated scope?
3. **GATE 3 — Contract preservation.** Does this change break any chassis/graph/score contract?
4. **GATE 4 — Test coverage.** Does this change have corresponding test coverage?
5. **GATE 5 — Rollback safety.** Can this change be reverted without data loss?

### Directory Ownership

| Directory | Owner | Agent Tier |
|-----------|-------|------------|
| `app/engines/` | Engine team | T3+ |
| `chassis/` | Platform team | T4+ (envelope + router; no domain logic) |
| `app/api/v1/chassis_endpoint.py` | Platform team | T4+ |
| `app/services/chassis_handlers.py` | Platform team | T4+ |
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

---

## Mandatory Pre-Commit Command

```bash
make agent-check
```

All 7 gates must pass before any commit.

| Gate | Command | Blocks On |
|------|---------|-----------|
| 1/7 LINT | ruff check . | Any lint error |
| 2/7 FORMAT | ruff format --check . | Formatting inconsistency |
| 3/7 TYPES | mypy app | Type errors (non-blocking per WAIVER-001) |
| 4/7 UNIT TESTS | pytest tests/unit/ tests/compliance/ | Test failure or coverage < 60% |
| 5/7 CI TESTS | pytest tests/ci/ | Contract call enforcement failure |
| 6/7 AUDIT | python tools/audit_engine.py --strict | CRITICAL/HIGH rule violations |
| 7/7 CONTRACTS | python tools/verify_contracts.py | Contract manifest integrity failure |

Quick fix before re-check: `make agent-fix` (auto-fixes ruff lint + format)

---

## CI Requirements

All PRs must pass:
- `make lint` — Ruff + MyPy
- `make test` — pytest with coverage
- `make audit` — 27-rule audit engine
- `make verify` — Contract verification
- Compliance tests (banned patterns, field names, import resolution, architecture)
- Contract call enforcement (repository_contract_pairs.yaml)

---

## Architectural Contracts

| ID | Contract | Severity |
|----|----------|----------|
| C-01 | `from fastapi import` only in app/api/, app/main.py, handlers.py | CRITICAL |
| C-02 | Handler signature: `async def handle_*(tenant, payload, settings, neo4j, redis)` | CRITICAL |
| C-03 | Tenant isolation in all Neo4j queries: `WHERE n.tenant_id = $tenant` | CRITICAL |
| C-04 | structlog only — `print()` forbidden in engine code | HIGH |
| C-05 | `list[T]`, `T | None` — never `List[]`, `Optional[]`, `Dict[]` | HIGH |
| C-06 | `eval()`, `exec()`, `compile()`, `pickle` — forbidden always | CRITICAL |
| C-07 | Cypher strings via `sanitize_label()` — no f-string injection | CRITICAL |
| C-08 | `yaml.safe_load()` only — never `yaml.load()` | CRITICAL |
| C-09 | All env vars must use `L9_` prefix | HIGH |
| C-10 | Zero hardcoded credentials — env vars via pydantic-settings only | CRITICAL |
| C-11 | `TransportPacket` (constellation_node_sdk) and chassis wire envelopes are immutable at boundaries — never mutate in place | CRITICAL |
| C-12 | No `Field(alias=...)` in Pydantic models | HIGH |
| C-13 | Transport contract lockstep: `chassis/envelope.py`, `app/api/v1/chassis_endpoint.py`, `app/services/chassis_handlers.py`, and `app/engines/handlers.py` (plus SDK registry) must stay aligned — paired changes in one PR when altering dispatch or envelope semantics | CRITICAL |
| C-14 | New ACTION_REGISTRY entry requires handler + test in same PR | HIGH |
| C-15 | Coverage >= 60% — never lower the threshold | HIGH |
| C-16 | Python 3.12+ — no backports, no 3.11-only APIs | CRITICAL |
| C-17 | No camelCase Python field names | HIGH |
| C-18 | Ruff ignore list is frozen — do not add/remove ignores | HIGH |
| C-19 | GDS jobs must be spec-driven from domain YAML gds_jobs section | MEDIUM |
| C-20 | L9_META header required in all template-managed files | HIGH |

---

## Canonical Import Patterns

```python
# CORRECT — module-level imports, Pydantic v2 runtime safe
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog
from pydantic import BaseModel, Field, model_validator

from constellation_node_sdk.transport import TransportPacket, create_transport_packet
from engine.utils.security import sanitize_label
from engine.utils.neo4j import execute_cypher

# WRONG — never do these
from fastapi import FastAPI           # ARCH-001: forbidden in engine/
from typing import Optional, List, Dict  # C-05: use T | None, list[T], dict[K,V]
import yaml; yaml.load(...)           # C-08: always yaml.safe_load()
print("debug")                        # C-04: always structlog
```

---

## Forbidden Patterns

| Rule ID | Pattern | Severity |
|---------|---------|----------|
| SEC-001 | f-string Cypher without sanitize_label() | CRITICAL |
| SEC-002 | `eval(` anywhere | CRITICAL |
| SEC-003 | `exec(` anywhere | CRITICAL |
| SEC-004 | `pickle.loads(` | CRITICAL |
| SEC-005 | `subprocess.shell=True` | CRITICAL |
| SEC-006 | `compile(` in engine code | CRITICAL |
| SEC-007 | `yaml.load(` not safe_load | CRITICAL |
| ARCH-001 | `from fastapi import` outside allowed modules | CRITICAL |
| ARCH-002 | `import fastapi` outside allowed modules | CRITICAL |
| ARCH-003 | `from engine import` from app/api/ or app/main.py | HIGH |
| ERR-001 | `except:` bare (no exception type) | HIGH |
| OBS-001 | `structlog.configure(` in engine/ | HIGH |
| STUB-001 | `pass` in a non-test function body | HIGH |
| STUB-002 | `...` as a non-test function body | HIGH |
| STUB-003 | TODO / FIXME in committed code | MEDIUM |
| TYPE-001 | `Optional[` anywhere | HIGH |
| TYPE-002 | `List[` anywhere | HIGH |
| TYPE-003 | `Dict[` anywhere | HIGH |

---

## Prohibited Actions

- **Never** change transport/envelope dispatch (`chassis/envelope.py`, `chassis_endpoint`, `chassis_handlers`, `handlers.py`) without updating the **paired** modules in the same PR (C-13)
- **Never** add new `ACTION_REGISTRY` entries without corresponding handler + test
- **Never** introduce FastAPI imports in engine modules (chassis isolation)
- **Never** use `eval()`, `exec()`, `compile()`, `pickle`
- **Never** hardcode API keys, tokens, or secrets
- **Never** use `print()` in engine code (use `structlog`)
- **Never** add `Field(alias=...)` to Pydantic models
- **Never** use camelCase for Python field names
- **Never** modify authentication or authorization logic without review
- **Never** change the signal schema contract
- **Never** modify `.github/workflows/` without review
- **Never** log API keys, partner data, or LLM responses at INFO level or above

---

## Agent Modes

### Code Generation
1. Determine your Tier for the files being modified.
2. Check forbidden patterns table before writing.
3. Use canonical import patterns.
4. Run `make agent-check` before committing.
5. Every new public function needs a docstring and type annotations.

### Code Review (PR)
1. Load `AI_AGENT_REVIEW_CHECKLIST.md` as primary guide.
2. Check all C-01 through C-20 contracts against changed files.
3. Comment format: `CONTRACT C-{N} VIOLATION — {rule}`.

### Refactoring
1. Confirm the change is within your Tier scope.
2. Verify all changed function signatures still match C-02.
3. Run `make test-compliance` and `make test-contracts` after refactoring.
4. If moving code across module boundaries, verify chassis isolation (C-01) is preserved.

### Question-Answering and Analysis
- T0 operation — always permitted.
- Reference specific section titles and contract IDs in answers.

---

## Agent Capabilities

### Permitted Commands
- `make agent-check` — full gate sequence
- `make agent-fix` — auto-fix lint/format
- `make test`, `make test-unit`, `make test-compliance`, `make test-contracts`
- `make audit`, `make audit-json` — informational audit
- `make verify` — contract verification
- `python tools/audit_engine.py` — direct audit invocation
- `python tools/verify_contracts.py` — direct verification

### Forbidden Commands
- `make prod`, `make prod-build`, `make deploy` — production infrastructure
- `make dev-clean` — destroys volumes
- `docker system prune` — destructive
- `git push --force` or `git reset --hard`
- `alembic upgrade head` in production context

---

## Quick Reference

| Question | Section |
|----------|---------|
| What can I do without human review? | Autonomy Tiers |
| What is forbidden? | Prohibited Actions, Forbidden Patterns |
| Which files can I never modify? | Protected Files (T4/T5) |
| What are the 7 gates? | Mandatory Pre-Commit Command |
| What are the contracts? | Architectural Contracts (C-01 to C-20) |
