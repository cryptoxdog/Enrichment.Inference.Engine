# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, contracts, law]
# owner: platform
# status: active
# token_estimate: 2075
# ssot_for: [contracts, forbidden-patterns, gate-sequence, autonomy-tiers, canonical-imports]
# load_when: [every_session, code_gen, refactor, review]
# references: [AGENT_BOOTSTRAP.md, GUARDRAILS.md, INVARIANTS.md, .cursorrules]
# --- /L9_META ---

# AGENT.md — Universal AI Agent Instruction Manual

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> Authority: Highest-priority governance document. When conflict exists, this file wins.
> Load AGENT_BOOTSTRAP.md first to determine whether to load this file.

---

## Agent Autonomy Tiers

Source: AGENTS.md SHA c4272ba — canonical definition lives here.

| Tier | Scope | Allowed Without Human Review |
|---|---|---|
| T0 — Read-Only | Browse, index, analyze, report | Always |
| T1 — Lint and Fix | Auto-fix lint, formatting, import ordering | Always |
| T2 — Test and CI | Add/modify tests, CI config, pre-commit | PR required |
| T3 — Engine Logic | app/engines/, app/score/, app/health/ | PR + review required |
| T4 — Contract | chassis_contract.py, handlers.py, graph_sync_client.py | PR + 2 reviewers |
| T5 — Schema | app/models/, kb/ rule files | PR + 2 reviewers + CI green |

### Protected Files — Never Modify Without Human Review (T4/T5)

| File | Tier | Why |
|---|---|---|
| app/engines/chassis_contract.py | T4 | Core dispatch contract |
| app/engines/handlers.py | T4 | Must stay in sync with chassis_contract.py |
| app/engines/graph_sync_client.py | T4 | Graph protocol contract |
| app/models/ (all files) | T5 | Pydantic schema — downstream breaking change risk |
| kb/ rule files | T5 | Knowledge base — requires review + CI green |
| .github/workflows/ | T2 | CI pipeline integrity |
| GUARDRAILS.md, AGENTS.md, CLAUDE.md | T4 | Governance documents |
| Dockerfile, docker-compose*.yml | T3 | Infrastructure immutability |

---

## Mandatory Pre-Commit Command

SSOT for the 7-gate sequence. All other documents reference here.

```bash
make agent-check
```

All 7 gates must pass before any commit.

| Gate | Command | Blocks On |
|---|---|---|
| 1/7 LINT | ruff check . | Any lint error |
| 2/7 FORMAT | ruff format --check . | Formatting inconsistency |
| 3/7 TYPES | mypy app | Type errors (non-blocking per WAIVER-001) |
| 4/7 UNIT TESTS | pytest tests/unit/ tests/compliance/ | Test failure or coverage less than 60% |
| 5/7 CI TESTS | pytest tests/ci/ | Contract call enforcement failure |
| 6/7 AUDIT | python tools/audit_engine.py --strict | CRITICAL/HIGH rule violations |
| 7/7 CONTRACTS | python tools/verify_contracts.py | Contract manifest integrity failure |

Quick fix before re-check: `make agent-fix` (auto-fixes ruff lint + format)

---

## Architectural Contracts (Summary of .cursorrules)

For full contract definitions, see .cursorrules. This table is a quick-reference index.

| ID | Contract | Severity | Automated Check |
|---|---|---|---|
| C-01 | from fastapi import only in app/api/, app/main.py, handlers.py | CRITICAL | compliance.yml Chassis Isolation |
| C-02 | Handler signature: async def handle_*(tenant, payload, settings, neo4j, redis) | CRITICAL | tests/compliance/ |
| C-03 | Tenant isolation in all Neo4j queries: WHERE n.tenant_id = $tenant | CRITICAL | None (INV-3 gap) |
| C-04 | structlog only — print() forbidden in engine code | HIGH | compliance.yml Terminology Guard |
| C-05 | list[T], T or None — never List[], Optional[], Dict[] | HIGH | compliance.yml Terminology Guard |
| C-06 | eval(), exec(), compile(), pickle — forbidden always | CRITICAL | audit_engine.py SEC-002/003 |
| C-07 | Cypher strings via sanitize_label() — no f-string injection | CRITICAL | audit_engine.py SEC-001 |
| C-08 | yaml.safe_load() only — never yaml.load() | CRITICAL | audit_engine.py SEC-007 |
| C-09 | All env vars must use L9_ prefix | HIGH | .cursorrules ENV-001 |
| C-10 | Zero hardcoded credentials — env vars via pydantic-settings only | CRITICAL | Gitleaks |
| C-11 | PacketEnvelope is immutable (frozen=True) — never mutate | CRITICAL | Pydantic runtime |
| C-12 | No Field(alias=...) in Pydantic models | HIGH | audit_engine.py |
| C-13 | chassis_contract.py and handlers.py must update together | CRITICAL | Manual (T4 gate) |
| C-14 | New ACTION_REGISTRY entry requires handler + test in same PR | HIGH | tests/ci/ |
| C-15 | Coverage >= 60% — never lower the threshold | HIGH | ci.yml test job |
| C-16 | Python 3.12+ — no backports, no 3.11-only APIs | CRITICAL | ci.yml PYTHON_VERSION |
| C-17 | No camelCase Python field names | HIGH | audit_engine.py |
| C-18 | Ruff ignore list is frozen — do not add/remove ignores | HIGH | None (INV-17 gap) |
| C-19 | GDS jobs must be spec-driven from domain YAML gds_jobs section | MEDIUM | tests/ci/ |
| C-20 | L9_META header required in all template-managed files | HIGH | verify_contracts.py |

---

## Canonical Import Patterns

Moved from CLAUDE.md — applies to ALL agents.

```python
# CORRECT — module-level imports, Pydantic v2 runtime safe
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog
from pydantic import BaseModel, Field, model_validator

from app.models.packet import PacketEnvelope
from app.models.config import L9Settings
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

| Rule ID | Pattern | Severity | Where Caught |
|---|---|---|---|
| SEC-001 | f-string Cypher without sanitize_label() | CRITICAL | audit_engine.py |
| SEC-002 | eval( anywhere | CRITICAL | audit_engine.py |
| SEC-003 | exec( anywhere | CRITICAL | audit_engine.py |
| SEC-004 | pickle.loads( | CRITICAL | audit_engine.py |
| SEC-005 | subprocess.shell=True | CRITICAL | audit_engine.py |
| SEC-006 | compile( in engine code | CRITICAL | audit_engine.py |
| SEC-007 | yaml.load( not safe_load | CRITICAL | audit_engine.py |
| ARCH-001 | from fastapi import outside allowed modules | CRITICAL | compliance.yml |
| ARCH-002 | import fastapi outside allowed modules | CRITICAL | compliance.yml |
| ARCH-003 | from engine import from app/api/ or app/main.py | HIGH | audit_engine.py |
| ERR-001 | except: bare (no exception type) | HIGH | ruff B001 |
| OBS-001 | structlog.configure( in engine/ | HIGH | audit_engine.py |
| STUB-001 | pass in a non-test function body | HIGH | audit_engine.py |
| STUB-002 | ... as a non-test function body | HIGH | audit_engine.py |
| STUB-003 | TODO / FIXME in committed code | MEDIUM | audit_engine.py |
| TYPE-001 | Optional[ anywhere | HIGH | compliance.yml |
| TYPE-002 | List[ anywhere | HIGH | compliance.yml |
| TYPE-003 | Dict[ anywhere | HIGH | compliance.yml |

---

## Prohibited Actions (from GUARDRAILS.md)

SSOT: GUARDRAILS.md SHA 13efe4f — reproduced here so agents reading only AGENT.md are protected.

Agents MUST NOT do any of the following without human review:
- Modify authentication or authorization logic
- Change the signal schema contract
- Modify .github/workflows/
- Change the synthesis threshold (0.6) or MIN_VALID constants
- Add new external API integrations
- Modify CODEOWNERS, AGENTS.md, CLAUDE.md, or GUARDRAILS.md
- Call partner.sudo().write() without documented justification
- Log API keys, partner data, or LLM responses at INFO level or above
- Modify chassis_contract.py without updating handlers.py in the same PR

---

## Agent Modes

### Code Generation
1. Determine your Tier for the files being modified (see Agent Autonomy Tiers).
2. Check forbidden patterns table before writing.
3. Use canonical import patterns above.
4. Run make agent-check before committing.
5. Every new public function needs a docstring and type annotations.

### Code Review (PR)
1. Load AI_AGENT_REVIEW_CHECKLIST.md as primary guide.
2. Check all C-01 through C-20 contracts against changed files.
3. Apply verdict matrix from AI_AGENT_REVIEW_CHECKLIST.md.
4. Comment format: `CONTRACT C-{N} VIOLATION — {rule}`.

### Refactoring
1. Confirm the change is within your Tier scope.
2. Verify all changed function signatures still match C-02.
3. Run make test-compliance and make test-contracts after refactoring.
4. If moving code across module boundaries, verify chassis isolation (C-01) is preserved.

### Question-Answering and Analysis
- T0 operation — always permitted.
- Reference specific section titles and contract IDs in answers.

### Dependency Updates
1. Update version in pyproject.toml only.
2. Verify import restriction compliance (C-01 chassis boundary still holds).
3. Run make agent-check.
4. Check dep changelog for breaking changes.

### Commit Preparation
1. Run make agent-check — all 7 gates must pass.
2. Commit message format: type(scope): description where type is one of feat, fix, refactor, test, chore, docs.
3. Reference contract IDs for contract-touching changes.
4. If PR touches T4/T5 files, add [NEEDS-2-REVIEWERS] prefix to PR title.

---

## Agent Capabilities and Limitations

### Permitted Commands
- make agent-check — full gate sequence
- make agent-fix — auto-fix lint/format
- make test, make test-unit, make test-compliance, make test-contracts
- make audit, make audit-json — informational audit
- make verify — contract verification
- python tools/audit_engine.py — direct audit invocation
- python tools/verify_contracts.py — direct verification

### Forbidden Commands
- make prod, make prod-build, make deploy — production infrastructure
- make dev-clean — destroys volumes
- docker system prune — destructive
- git push --force or git reset --hard
- alembic upgrade head in production context

---

## Cross-Reference Map

| Topic | SSOT Document | Section |
|---|---|---|
| Directory structure | REPO_MAP.md | Directory Map |
| Module boundary rules | This file (AGENT.md) | C-01 |
| All env vars | CONFIG_ENV_CONTRACT.md | Environment Variables |
| Dependency versions | DEPENDENCY_SURFACE.md | Version Table |
| CI gate details | CI_WHITELIST_REGISTER.md | Merge-Blocking Gates |
| Runtime execution flows | EXECUTION_FLOWS.md | Flows |
| File modification safety | FILE_INDEX_FOR_AGENTS.md | File Modification Rules |
| Invariant list | INVARIANTS.md | INV-1 through INV-20 |
