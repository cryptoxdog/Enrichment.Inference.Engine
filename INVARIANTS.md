# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, invariants, architecture, enforcement]
# owner: platform
# status: active
# token_estimate: 2834
# ssot_for: [invariants, architectural-rules, process-rules]
# load_when: [architectural_questions, invariant_lookup, refactor]
# references: [AGENTS.md, CI_WHITELIST_REGISTER.md]
# --- /L9_META ---

# INVARIANTS.md — Immutable Architectural Rules

**VERSION**: 2.1.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-11

> These 20 rules must hold across ALL repository states.
> Violation of any CRITICAL invariant is grounds for immediate PR rejection.
> Gate sequence definition: see [AGENTS.md](AGENTS.md) (SSOT — `make agent-check`).

---

## Contract to Invariant Cross-Reference

| AGENT.md Contract | Invariant | Status |
|---|---|---|
| C-01 (Chassis isolation) | INV-2 | COVERED |
| C-03 (Tenant scoping) | INV-3 | GAP — no automated check |
| C-04 (structlog only) | INV-4 | PARTIAL |
| C-07 (Cypher injection) | INV-6 | PARTIAL |
| C-09 (L9_ prefix) | INV-20 | PARTIAL |
| C-10 (no hardcoded creds) | INV-12 | COVERED (Gitleaks) |
| C-11 (transport immutability) | INV-15 | PARTIAL (runtime only) |
| C-15 (coverage >= 60%) | INV-9 | COVERED |
| C-16 (Python 3.12+) | INV-11 | COVERED |
| C-18 (frozen ruff ignores) | INV-17 | GAP — no automated check |
| C-20 (L9_META header) | INV-10 | PARTIAL |

---

## Part A — Architectural Invariants (INV-1 through INV-15)

### INV-1: HTTP Surface Governance
**Severity**: CRITICAL | **Enforcement**: GAP — human review + static scans (no exhaustive route inventory in CI)
**Rule**: The governed FastAPI surface is assembled in `app/main.py` (included routers plus top-level routes). Documented entrypoints include enrichment (`POST /api/v1/enrich`, `POST /api/v1/enrich/batch`, `GET /api/v1/health`), Constellation transport (`POST /v1/execute`, `POST /v1/outcomes` per module docstring), and routers mounted from `app/api/v1/*` and `app/score/score_api.py`. **New routes** or new public routers require architecture/API review; ad-hoc endpoints must not bypass chassis patterns in [AGENTS.md](AGENTS.md) C-01/C-02.
Automation opportunity: CI step or audit script that diffs OpenAPI route table against an allowlist. Track: docs-gap-inv1.

### INV-2: Chassis-Engine Import Boundary
**Severity**: CRITICAL | **Enforcement**: COVERED — compliance.yml Chassis Isolation step
**Rule**: Engine modules under engine/ and app/engines/ MUST NOT import fastapi.
Only app/api/, app/main.py, and handlers.py may import FastAPI.
See: AGENT.md C-01, REPO_MAP.md Module Boundaries.

### INV-3: Tenant Scoping Completeness
**Severity**: CRITICAL | **Enforcement**: GAP — human review only
**Rule**: Every Neo4j query that reads or writes domain data MUST include WHERE n.tenant_id = $tenant.
No cross-tenant data leakage is acceptable under any condition.
Automation opportunity: Semgrep rule matching Cypher strings without tenant selector. Track: docs-gap-inv3.

### INV-4: Observability Config Locality
**Severity**: HIGH | **Enforcement**: PARTIAL — audit_engine.py OBS-001/002
**Rule**: structlog.configure() MUST NOT be called from within engine/. Configuration is the chassis responsibility.

### INV-5: Infrastructure Immutability
**Severity**: HIGH | **Enforcement**: GAP — .github/CODEOWNERS provides required-review protection
**Rule**: Dockerfile, docker-compose.yml, docker-compose.prod.yml, and deployment scripts MUST NOT be modified without T3+ review.

### INV-6: Cypher Injection Prevention
**Severity**: CRITICAL | **Enforcement**: PARTIAL — audit_engine.py SEC-001
**Rule**: All dynamically constructed Cypher strings MUST pass through sanitize_label() from engine/utils/security.py.

### INV-7: Domain Spec Validation
**Severity**: HIGH | **Enforcement**: PARTIAL — DomainPackLoader Pydantic validation
**Rule**: All domain spec YAML files must be loadable by DomainPackLoader without ValidationError. Invalid specs must fail at load time, not at runtime.

### INV-8: Gate-Then-Score Architecture
**Severity**: CRITICAL | **Enforcement**: PARTIAL — unit tests
**Rule**: Entity enrichment MUST execute gate compilation before scoring. Gates produce Cypher WHERE; scores produce ORDER BY. These stages must not be merged or reversed.

### INV-9: Coverage Threshold >= 60%
**Severity**: HIGH | **Enforcement**: COVERED — `pytest.ini` / `pyproject.toml` (`fail_under` / `--cov-fail-under`) and CI pytest step
**Rule**: Test coverage for `app/` must never drop below 60%. The threshold may only increase, never decrease.

### INV-10: L9_META Presence
**Severity**: MEDIUM | **Enforcement**: PARTIAL — tools/verify_contracts.py (confirmed present SHA 2d30a79)
**Rule**: All files managed by L9 templates MUST contain a valid L9_META header block.

### INV-11: Python Version 3.12+
**Severity**: CRITICAL | **Enforcement**: COVERED — ci.yml PYTHON_VERSION: 3.12
**Rule**: The codebase targets Python 3.12. No Python 3.11-only APIs or backport shims permitted.

### INV-12: Forbidden eval/exec/pickle
**Severity**: CRITICAL | **Enforcement**: PARTIAL — audit_engine.py SEC-002/003/004
**Rule**: eval(), exec(), compile(), and pickle.loads() are forbidden everywhere in app/ and engine/.

### INV-13: YAML SafeLoader
**Severity**: CRITICAL | **Enforcement**: PARTIAL — audit_engine.py SEC-007
**Rule**: All YAML loading must use yaml.safe_load(). yaml.load() without Loader is forbidden.

### INV-14: Zero-Stub Protocol
**Severity**: HIGH | **Enforcement**: PARTIAL — audit_engine.py STUB-001/002/003
**Rule**: No pass, ..., or TODO may exist in committed production code outside test files and protocol definitions.

### INV-15: Transport Immutability
**Severity**: CRITICAL | **Enforcement**: PARTIAL — SDK + code review
**Rule**: `TransportPacket` and other constellation transport types MUST NOT be mutated after construction. Chassis wire dicts produced by `chassis/envelope.py` must not be mutated in place across service boundaries — derive new dicts/packets for changes.

---

## Part B — Process Invariants (INV-16 through INV-20)

### INV-16: Directory Structure Stability
**Severity**: HIGH | **Enforcement**: GAP — human review only (docs-consistency.yml provides warning)
**Rule**: Top-level directories may not be added or renamed without architecture team approval.
Canonical set: app/, engine/, tools/, tests/, kb/, docs/, chassis/, codegen/, config/, domains/, infra/, migrations/, monitoring/, odoo_modules/, reports/, scripts/, templates/, readme/.

### INV-17: Ruff Ignore List Immutability
**Severity**: HIGH | **Enforcement**: GAP — docs-consistency.yml provides warning on change
**Rule**: The ruff ignore list in pyproject.toml [tool.ruff.lint] ignore is frozen.

Current frozen list with rationale:

| Ignore | Rule | Why Suppressed |
|---|---|---|
| E501 | Line too long | ruff format manages line length |
| TC001 | Typing-only first-party import | Pydantic v2 requires runtime imports |
| TC002 | Typing-only third-party import | Same Pydantic v2 runtime requirement |
| TC003 | Typing-only stdlib import | Same Pydantic v2 runtime requirement |
| SIM105 | contextlib.suppress | Explicit try/except clearer in async+structlog code |
| TRY003 | Long exception messages | Acceptable in domain-specific code |
| TRY400 | logging.error vs exception | Both acceptable in this codebase |
| ARG001 | Unused function arg | Handler interface compliance (tenant, payload always present) |
| ARG002 | Unused method arg | Handler interface compliance |
| ARG003 | Unused classmethod arg | Handler interface compliance |
| B007 | Unused loop variable | Use _ prefix convention instead |
| B008 | Function call in default arg | FastAPI Depends() pattern is intentional |

### INV-18: Test Marker Completeness
**Severity**: MEDIUM | **Enforcement**: PARTIAL — pytest config validates markers
**Rule**: Every test must have at least one of: @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.slow.

### INV-19: Agent Check Gate Sequence
**Severity**: HIGH | **Enforcement**: COVERED — Makefile + pre-commit
**Rule**: The 7-gate `make agent-check` sequence is the mandatory pre-commit verification. See [AGENTS.md](AGENTS.md) (SSOT). No commits while any gate is failing.

### INV-20: Environment Variable L9_ Prefix Convention
**Severity**: MEDIUM | **Enforcement**: PARTIAL — .cursorrules ENV-001
**Rule**: All application-level environment variables must use L9_ prefix. Exceptions: DATABASE_URL, REDIS_URL, TESTING (infrastructure-standard names).

---

## Invariant Addition Protocol

1. Create a GitHub issue with label arch-review.
2. Assign to CODEOWNERS (see .github/CODEOWNERS).
3. Issue must include: rule statement, severity, enforcement mechanism, affected contracts.
4. Only architecture team review can merge a new invariant.
5. New invariants must update this file AND add or align a corresponding contract in [AGENTS.md](AGENTS.md) (and `.cursor/rules/` where repo policy mirrors contracts).

---

## Enforcement Coverage Summary

| Status | Count | Invariants |
|---|---|---|
| COVERED (full CI) | 4 | INV-2, INV-9, INV-11, INV-19 |
| PARTIAL (semi-auto) | 11 | INV-4, INV-6, INV-7, INV-8, INV-10, INV-12, INV-13, INV-14, INV-15, INV-18, INV-20 |
| GAP (human only) | 5 | INV-1, INV-3, INV-5, INV-16, INV-17 |

Weighted enforcement score: 48% (target after Phase 5: 75%+)
