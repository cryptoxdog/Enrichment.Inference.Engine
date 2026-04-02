# AGENT.md

## Purpose
AI Agent instruction manual for Enrichment.Inference.Engine. Codifies coding rules, architectural contracts, and repository laws that all AI agents must follow when modifying this codebase.

## Scope
Applies to: all AI coding agents (Cursor, GitHub Copilot, Claude, CodeRabbit, Qodo)
Enforcement: pre-commit hooks, CI pipeline, contract scanner

## Source Evidence
- `.cursorrules` (SHA: 4c2d06a8f3823eb8b4f8cce80cf920337ae13f95)
- `.github/workflows/ci.yml` (SHA: 028e64cfd5c584ba850cd6330c528c2b8a09b44e)
- `.github/workflows/compliance.yml` (SHA: ab57ddb48a57ea1908ca535370441dd9fb787a5a)
- `Makefile` (SHA: ed1fe7c23acfff6de7ace9eb531e82e29e7338a4)

## Facts

### Mandatory Pre-Commit Command
```bash
make agent-check
```

**Gates (7 sequential checks):**
1. `ruff check .` — Linting
2. `ruff format --check .` — Format verification
3. `mypy app` — Type checking
4. `pytest tests/unit/ tests/compliance/ -v --tb=short -x` — Unit + compliance tests
5. `pytest tests/ci/ -v --tb=short -x` — CI contract tests
6. `python tools/audit_engine.py --strict` — 27-rule audit engine
7. `python tools/verify_contracts.py` — Contract manifest verification

**Failure protocol:** If any gate fails → revert changes → fix → retry

### Auto-Fix Command
```bash
make agent-fix
```
Runs: `ruff check . --fix` + `ruff format .`

### Full Agent Workflow
```bash
make agent-full
```
Runs: `agent-fix` → `agent-check` → full coverage report

## Invariants

### CONTRACT 1: CHASSIS BOUNDARY
- **RULE:** Engine code NEVER imports FastAPI, Starlette, or any HTTP library
- **EXCEPTION:** Only `app/api/`, `app/main.py`, and `handlers.py` may import FastAPI
- **RATIONALE:** Maintains separation between HTTP chassis and domain engine
- **ENFORCEMENT:** `.github/workflows/compliance.yml` Chassis Isolation Check

### CONTRACT 2: HANDLER INTERFACE
- **RULE:** Engine exposes action handlers only via signature:
  ```python
  async def handle_<action>(tenant: str, payload: dict) -> dict
  ```
- **REGISTRATION:** In `engine/handlers.py`:
  ```python
  chassis.router.register_handler("match", handle_match)
  ```
- **ENFORCEMENT:** `tools/verify_contracts.py` + CI tests

### CONTRACT 3: TENANT ISOLATION
- **RULE:** Tenant resolved BY chassis (5-level: header → subdomain → key prefix → envelope → default)
- **ENGINE RECEIVES:** `tenant` as string argument
- **ENGINE NEVER:** Resolves tenant itself
- **DATABASE SCOPING:** Every Neo4j query scopes to tenant database
- **ENFORCEMENT:** Architecture compliance tests

### CONTRACT 6: PACKETENVELOPE PROTOCOL
- **RULE:** All inter-service payloads are `PacketEnvelope`
- **BOUNDARY OPERATIONS:**
  - Entry: `inflate_ingress()`
  - Exit: `deflate_egress()`
- **INTERNAL:** Typed dicts/Pydantic models between boundaries

### CONTRACT 7: IMMUTABILITY + CONTENT HASH
- **RULE:** `PacketEnvelope` is frozen (`Pydantic frozen=True`)
- **MUTATIONS:** Create new packets via `.derive()`
- **CONTENT HASH:** SHA-256 of canonical payload, unique DB constraint
- **IDEMPOTENCY:** Duplicate `content_hash` silently rejected

### CONTRACT 9: CYPHER INJECTION PREVENTION
- **RULE:** All Neo4j labels/relationship types MUST pass `sanitize_label()` before interpolation
- **REGEX:** `^[A-Za-z_][A-Za-z0-9_]*$`
- **PARAMETERIZATION:** Cypher VALUES use `$batch`, `$query` parameters
- **ENFORCEMENT:** Banned pattern SEC-001 in contract scanner

### CONTRACT 12: DOMAIN SPEC IS SOURCE OF TRUTH
- **RULE:** All matching behavior from `{domain_id}_domain_spec.yaml`
- **LOADER:** `DomainPackLoader` (engine/config/loader.py) reads YAML → `DomainConfig` (Pydantic)
- **VALIDATION:** Domain specs are untrusted input → validate everything

### CONTRACT 18: L9_META ON EVERY FILE
- **RULE:** Every tracked file carries L9_META header (schema version 1)
- **FIELDS:** `l9_schema`, `origin`, `engine`, `layer`, `tags`, `owner`, `status`
- **INJECTION:** Via `tools/l9_meta_injector.py` (not manual)

## Constraints

### Python Version
**Required:** 3.12+
**Evidence:** `.python-version` (3.12), `pyproject.toml` (target-version = "py312")

### Code Style Rules
1. **Formatting:** ruff format (Black-compatible, 88-char line length)
2. **Linting:** ruff check + mypy --strict engine/
3. **Type Hints:** Every function signature, class attribute, ambiguous variable
4. **Models:** Pydantic v2 BaseModel (frozen where appropriate)
5. **Logging:** `structlog.get_logger(__name__)` with tenant, trace_id, action in context
6. **Naming:** snake_case everywhere, no Pydantic Field(alias=...)

### Forbidden Patterns (Contract Scanner Rules)

**CRITICAL (merge blocked):**
- `SEC-001`: f-string Cypher MATCH without sanitize_label()
- `SEC-002`: eval()
- `SEC-003`: exec()
- `SEC-006`: pickle.load(s)
- `SEC-007`: yaml.load() without SafeLoader
- `ARCH-001`: from fastapi import (in engine/)
- `ARCH-002`: from starlette import (in engine/)
- `DEL-001`: httpx.post/get/etc (in engine/)
- `STUB-001`: raise NotImplementedError (outside tests/)

**HIGH (merge blocked):**
- `ERR-001`: bare except:
- `ERR-002`: except + pass (swallowed exception)
- `OBS-001`: structlog.configure() (in engine/)
- `OBS-002`: logging.basicConfig() (in engine/)

### Directory Structure (Fixed)
```
engine/handlers.py          → ONLY chassis bridge
engine/config/              → Domain spec schema + loader + settings
engine/gates/               → Gate compiler + null semantics + registry
engine/scoring/             → Scoring assembler
engine/traversal/           → Traversal assembler + resolver
engine/sync/                → Sync generator
engine/gds/                 → GDS scheduler
engine/graph/               → Neo4j async driver wrapper
engine/compliance/          → Prohibited factors + PII + audit
engine/packet/              → PacketEnvelope bridge
engine/utils/               → safe_eval, security (sanitize_label)
chassis/                    → Thin chassis adapter
domains/                    → {domain_id}_domain_spec.yaml per vertical
```
**RULE:** Do NOT create new top-level directories without architectural approval

### Test Requirements
- **Unit tests:** Gate compilation, scoring math, parameter resolution, null semantics
- **Integration tests:** testcontainers-neo4j (do NOT mock Neo4j driver)
- **Compliance tests:** Verify prohibited factors blocked at compile time
- **Performance:** <200ms p95 match latency
- **Coverage:** Minimum 60% (enforced in CI)

## Known Unknowns
- GDS job actual implementation details (declarative spec found, runtime execution unknown)
- KGE CompoundE3D model training pipeline (referenced in contracts, implementation unknown)
- Memory substrate access patterns (mentioned in contracts, specific queries unknown)

## Agent Guidance

### Before Every Commit
1. Run `make agent-fix` to auto-fix linting/formatting
2. Run `make agent-check` — all 7 gates MUST pass
3. If gate fails → read error → fix → retry
4. NEVER commit with failing gates

### When Adding New Code
1. Check if it violates any CONTRACT (1-20) listed above
2. Add L9_META header via `tools/l9_meta_injector.py`
3. Add type hints to all signatures
4. Use `structlog.get_logger(__name__)` for logging
5. Add unit tests in `tests/unit/` or `tests/compliance/`
6. Run `make agent-check` before committing

### When Modifying Cypher Queries
1. ALWAYS use `sanitize_label()` for labels/relationship types
2. ALWAYS use parameterized queries (`$batch`, `$query`) for values
3. NEVER interpolate user input directly into Cypher strings
4. Test with `make cypher-lint` (if available)

### When Working with Domain Specs
1. Treat as untrusted input — validate everything
2. Use `DomainPackLoader` to read YAML → `DomainConfig`
3. Never access raw YAML dicts directly
4. All matching logic MUST compile to Cypher WHERE clauses
5. No post-filtering in Python

### CI Pipeline Behavior
- **Triggers:** Push to main/develop, PRs to main/develop
- **Required checks:** validate, lint, semgrep, test, security
- **Optional checks:** sbom, scorecard (non-blocking)
- **Merge gate:** All required checks MUST pass
- **Coverage threshold:** 60% minimum

### Review Process
1. Pre-commit hooks run automatically
2. CI pipeline runs on push
3. CodeRabbit + Qodo + Claude review (contract-aware)
4. All 5 enforcement layers MUST pass before merge
5. No bypass allowed (branch protection enabled)
