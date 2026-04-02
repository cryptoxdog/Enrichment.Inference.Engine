# INVARIANTS.md

## Purpose
Codifies immutable architectural rules that MUST hold across all repository states. Violations are caught at CI time and block merge.

## Scope
Applies to: all code, configurations, workflows, tests
Enforcement: compliance.yml workflow, contract scanner, pre-commit hooks

## Source Evidence
- `.cursorrules` (20 contracts)
- `.github/workflows/compliance.yml` (architecture gates)
- `.github/workflows/ci.yml` (quality gates)
- `pyproject.toml` (tool configuration)

## Facts

### INVARIANT 1: HTTP Surface Constraint
**Rule:** Repository exposes EXACTLY TWO HTTP endpoints
**Endpoints:**
- `POST /v1/execute`
- `GET /v1/health`

**Evidence:** `.cursorrules` CONTRACT 1
**Enforcement:** Architecture review, no automated check (human verification required)

### INVARIANT 2: Chassis-Engine Import Boundary
**Rule:** Engine code NEVER imports HTTP/web frameworks
**Allowed imports in engine/:**
- Python stdlib
- pydantic
- structlog
- Domain-specific libraries (Neo4j driver, etc.)

**Forbidden imports in engine/:**
- `from fastapi import`
- `from starlette import`
- `import uvicorn`
- `from flask import`
- `from django import`

**Exceptions:**
- `app/api/` (allowed: FastAPI)
- `app/main.py` (allowed: FastAPI, uvicorn)
- `engine/handlers.py` (allowed: chassis.router only)

**Evidence:** `.cursorrules` CONTRACT 1
**Enforcement:** `.github/workflows/compliance.yml` Chassis Isolation Check
**Scanner Rule:** ARCH-001, ARCH-002, ARCH-003

### INVARIANT 3: Tenant Scoping Completeness
**Rule:** Every database query MUST scope to tenant
**Implementation:** All Neo4j queries include tenant database selector
**Exception:** Admin queries on system database (must be explicit)

**Evidence:** `.cursorrules` CONTRACT 3
**Enforcement:** Code review (no automated check for Neo4j queries)

### INVARIANT 4: Observability Configuration Locality
**Rule:** Engine code NEVER configures logging/metrics infrastructure
**Allowed in chassis only:**
- `structlog.configure()`
- `logging.basicConfig()`
- Prometheus registry setup

**Allowed in engine:**
- `structlog.get_logger(__name__)`
- `logger.bind(tenant=..., trace_id=...)`

**Evidence:** `.cursorrules` CONTRACT 4
**Enforcement:** `.cursorrules` scanner rules OBS-001, OBS-002

### INVARIANT 5: Infrastructure Immutability
**Rule:** Engine NEVER creates Dockerfile, docker-compose, CI workflows, Terraform
**Rationale:** All infrastructure from l9-template (single source of truth)
**Allowed modifications:**
- `.env.template` (engine-specific variables only)
- `README.md` (engine-specific documentation)

**Evidence:** `.cursorrules` CONTRACT 5
**Enforcement:** Manual review (files tracked in .gitignore or l9-template)

### INVARIANT 6: Cypher Injection Prevention
**Rule:** All Cypher labels/types pass `sanitize_label()` before interpolation
**Regex:** `^[A-Za-z_][A-Za-z0-9_]*$`
**Values:** ALWAYS use parameterized queries (`$batch`, `$query`)

**Example FORBIDDEN:**
```python
cypher = f"MATCH (n:{user_input}) RETURN n"
```

**Example REQUIRED:**
```python
from engine.utils.security import sanitize_label
label = sanitize_label(user_input)
cypher = f"MATCH (n:{label}) WHERE n.id = $id"
params = {"id": entity_id}
```

**Evidence:** `.cursorrules` CONTRACT 9
**Enforcement:** `.cursorrules` scanner rule SEC-001

### INVARIANT 7: Domain Spec Validation
**Rule:** All domain specs MUST pass `DomainPackLoader` validation
**Schema:** Pydantic `DomainConfig` in `engine/config/schema.py`
**Untrusted Input:** Domain specs uploaded via admin endpoints → strict validation

**Evidence:** `.cursorrules` CONTRACT 12
**Enforcement:** `engine/config/loader.py` Pydantic validation

### INVARIANT 8: Gate-Then-Score Architecture
**Rule:** All matching is two-phase: gates (filter) → scoring (rank)
**Gates compile to:** Cypher WHERE clauses (no post-filtering in Python)
**Scoring compiles to:** Single WITH/ORDER BY clause (no iterative Python scoring)

**Gate Types (10):**
range, threshold, boolean, composite, enum_map, exclusion, self_range, freshness, temporal_range, traversal

**Scoring Computations (9):**
geo_decay, log_normalized, community_match, inverse_linear, candidate_property, weighted_rate, price_alignment, temporal_proximity, custom_cypher

**Evidence:** `.cursorrules` CONTRACT 13
**Enforcement:** Unit tests in `tests/unit/`, integration tests verify no Python filtering

### INVARIANT 9: Test Coverage Threshold
**Rule:** Code coverage MUST be ≥60%
**Measurement:** pytest-cov on `app/` directory
**CI Enforcement:** `.github/workflows/ci.yml` test job with `--cov-fail-under=60`

**Evidence:**
- `pyproject.toml` `[tool.coverage.report] fail_under = 60`
- `.github/workflows/ci.yml` COVERAGE_THRESHOLD = 60

**Enforcement:** CI test job fails if coverage <60%

### INVARIANT 10: L9_META Presence
**Rule:** All tracked files MUST have L9_META header (schema version 1)
**Required Fields:**
- `l9_schema: 1`
- `origin: l9-template` or `origin: engine`
- `engine: enrichment`
- `layer: [list]`
- `tags: [list]`
- `owner: string`
- `status: active|deprecated|experimental`

**Injection Tool:** `tools/l9_meta_injector.py`

**Evidence:** `.cursorrules` CONTRACT 18
**Enforcement:** `tools/verify_contracts.py` (if available)

### INVARIANT 11: Python Version Constraint
**Rule:** Code MUST run on Python 3.12+
**Syntax:** Use 3.12+ features (type union `|`, match statements, etc.)
**Type hints:** Use `list[T]`, `dict[K,V]` (not `List[T]`, `Dict[K,V]`)

**Evidence:**
- `.python-version`: `3.12`
- `pyproject.toml`: `requires-python = ">=3.11"`, `target-version = "py312"`

**Enforcement:** CI uses Python 3.12 (`.github/workflows/ci.yml` PYTHON_VERSION = 3.12)

### INVARIANT 12: Forbidden Eval/Exec
**Rule:** NEVER use `eval()`, `exec()`, `pickle.load()` anywhere in codebase
**Exceptions:** NONE (no legitimate use case in this repository)

**Evidence:** `.cursorrules` banned patterns SEC-002, SEC-003, SEC-006
**Enforcement:** `.cursorrules` contract scanner (merge-blocking)

### INVARIANT 13: Yaml SafeLoader Requirement
**Rule:** All YAML loading MUST use `yaml.safe_load()` or `yaml.SafeLoader`
**Forbidden:** `yaml.load()` without SafeLoader argument

**Evidence:** `.cursorrules` banned pattern SEC-007
**Enforcement:** `.cursorrules` contract scanner (merge-blocking)

### INVARIANT 14: Zero-Stub Protocol
**Rule:** No `raise NotImplementedError` outside tests/, no TODO/PLACEHOLDER comments
**Rationale:** Ship code or defer to DEFERRED.md
**Exceptions:** `tests/` directory only

**Evidence:** `.cursorrules` banned patterns STUB-001, STUB-002, STUB-003
**Enforcement:** `.cursorrules` contract scanner (merge-blocking)

### INVARIANT 15: PacketEnvelope Immutability
**Rule:** `PacketEnvelope` is frozen (Pydantic `frozen=True`)
**Mutations:** ONLY via `.derive()` method (creates new instance)
**Content Hash:** SHA-256 of canonical payload, unique constraint in DB

**Evidence:** `.cursorrules` CONTRACT 7
**Enforcement:** Pydantic model validation, database constraint

### INVARIANT 16: Directory Structure Stability
**Rule:** Top-level directories are FIXED (no new directories without approval)
**Existing directories:**
```
app/          → FastAPI application (chassis)
engine/       → Core matching engine (domain-agnostic)
domains/      → Domain-specific YAML configs
kb/           → Knowledge base YAML rules
tests/        → Test suite
tools/        → Development tools
chassis/      → Chassis adapter
config/       → Configuration files
docs/         → Documentation
scripts/      → Deployment scripts
```

**Evidence:** `.cursorrules` CONTRACT 16
**Enforcement:** Manual review during PR

### INVARIANT 17: Ruff Ignore List Immutability
**Rule:** Global ruff ignores are FIXED (no additions without architectural review)
**Current ignores:**
```toml
ignore = [
    "E501",     # formatter handles line length
    "TC001",    # typing-only first-party import
    "TC002",    # typing-only third-party import
    "TC003",    # typing-only stdlib import
    "SIM105",   # contextlib.suppress
    "TRY003",   # long exception messages
    "TRY400",   # logging.error vs logging.exception
    "ARG001",   # unused function args
    "ARG002",   # unused method args
    "ARG003",   # unused classmethod args
    "B007",     # unused loop variable
    "B008",     # function-call-in-default-argument
]
```

**Evidence:** `pyproject.toml` `[tool.ruff.lint]`
**Enforcement:** Manual review during PR

### INVARIANT 18: Test Marker Completeness
**Rule:** All tests MUST have exactly one marker: `unit`, `integration`, or `slow`
**Markers:**
- `@pytest.mark.unit` — Fast, no external deps
- `@pytest.mark.integration` — Requires services (Redis, PostgreSQL, Neo4j)
- `@pytest.mark.slow` — Long-running (enrichment, convergence)

**Evidence:** `pyproject.toml` `[tool.pytest.ini_options]`
**Enforcement:** pytest configuration, CI runs by marker

### INVARIANT 19: Agent Check Gate Sequence
**Rule:** `make agent-check` runs EXACTLY 7 gates in EXACT order (no reordering)
**Sequence:**
1. ruff check .
2. ruff format --check .
3. mypy app
4. pytest tests/unit/ tests/compliance/ -v --tb=short -x
5. pytest tests/ci/ -v --tb=short -x
6. python tools/audit_engine.py --strict
7. python tools/verify_contracts.py

**Evidence:** `Makefile` agent-check target
**Enforcement:** Pre-commit hook, CI pipeline

### INVARIANT 20: Environment Variable Naming
**Rule:** Infrastructure env vars MUST use `L9_` prefix
**Examples:** `L9_NEO4J_URI`, `L9_REDIS_URL`, `L9_LOG_LEVEL`
**Engine-specific vars:** No prefix (e.g., `PERPLEXITY_API_KEY`, `ODOO_URL`)

**Evidence:** `.cursorrules` banned pattern ENV-001
**Enforcement:** `.cursorrules` contract scanner

## Constraints

### Invariant Violation Protocol
1. **Detection:** Pre-commit hook, CI pipeline, contract scanner
2. **Reporting:** CI job failure, comment on PR
3. **Resolution:** Revert changes, fix violation, re-run checks
4. **Escalation:** If invariant is blocking valid work → architectural review required

### Invariant Addition Protocol
1. **Proposal:** Submit PR with new invariant in INVARIANTS.md
2. **Review:** Architecture team review
3. **Implementation:** Update scanner rules, CI checks
4. **Documentation:** Update AGENT.md, CLAUDE.md
5. **Enforcement:** Add to pre-commit hooks, compliance.yml

## Known Unknowns
- Some invariants have no automated enforcement (human review required)
- Neo4j query tenant scoping verification (no static analysis tool exists)
- PacketEnvelope database constraint enforcement (DDL not in repository)

## Agent Guidance

### When Modifying Code
1. **Check this file first** — Does your change violate any invariant?
2. **If invariant violated** → Change approach or propose invariant modification
3. **If uncertain** → Run `make agent-check` to detect violations

### When Reviewing PRs
1. **Scan for invariant violations** — Check each INVARIANT 1-20
2. **Check automated enforcement** — Did CI catch it?
3. **Check manual enforcement** — Human-verified invariants (1, 3, 5, 16)
4. **Request fixes** — Cite specific invariant number in review comment

### When Proposing New Invariants
1. **Justify necessity** — Why is this invariant critical?
2. **Propose enforcement** — How will it be automated?
3. **Update documentation** — AGENT.md, CLAUDE.md, this file
4. **Implement checks** — Scanner rule, CI job, pre-commit hook
