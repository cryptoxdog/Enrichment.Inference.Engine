# CLAUDE.md

## Purpose
Claude AI specific guidance for code review and generation tasks in Enrichment.Inference.Engine.

## Scope
Applies to: Claude AI assistant when reviewing PRs, generating code, or answering questions
Context: PlasticOS ecosystem, L9 Platform Architecture, Graph Cognitive Engine

## Source Evidence
- `.cursorrules` (SHA: 4c2d06a8f3823eb8b4f8cce80cf920337ae13f95)
- `ARCHITECTURE.md` (SHA: 9ea05a1414534b45143cb17308e5511ae5b33185)
- `AGENTS.md` (SHA: c4272ba65818a9790ad7592130aec2b72a2ed291)
- `.github/workflows/compliance.yml` (SHA: ab57ddb48a57ea1908ca535370441dd9fb787a5a)

## Facts

### Repository Context
- **Name:** Enrichment.Inference.Engine
- **Purpose:** Universal domain-aware entity enrichment API for Salesforce + Odoo
- **Primary Language:** Python 3.12+
- **Framework:** FastAPI (chassis only), Neo4j (graph storage), Redis (caching)
- **Architecture Pattern:** Chassis-Engine separation (L9 Platform Architecture)

### Core Components
1. **Chassis** (`app/api/`, `app/main.py`): HTTP surface, tenant resolution, observability
2. **Engine** (`engine/`): Domain-agnostic matching logic, gate compilation, scoring
3. **Domain Specs** (`domains/`): YAML configuration per vertical (plasticos, etc.)
4. **Knowledge Base** (`kb/`): YAML rule files for enrichment logic

### Key Dependencies (from pyproject.toml)
- `fastapi>=0.115.0` (chassis only)
- `pydantic>=2.9.0` (all data models)
- `structlog>=24.0.0` (logging)
- `redis>=5.0.0` (caching)
- `perplexityai>=0.2.0` (enrichment source)
- `httpx>=0.27.0` (HTTP client)

## Invariants

### Architectural Contracts (Summary from .cursorrules)
1. **Single HTTP Ingress:** POST /v1/execute, GET /v1/health only
2. **Handler Interface:** `async def handle_<action>(tenant: str, payload: dict) -> dict`
3. **Tenant Isolation:** Chassis resolves tenant (5-level waterfall), engine receives string
4. **Observability:** Chassis configures structlog, engine uses `structlog.get_logger(__name__)`
5. **PacketEnvelope Protocol:** All inter-service payloads frozen, immutable, content-hashed
6. **Cypher Injection Prevention:** All labels sanitized, values parameterized
7. **Domain Spec Source of Truth:** All matching behavior from YAML → DomainConfig Pydantic

### Code Quality Gates (from Makefile)
```
make agent-check runs 7 sequential gates:
1. ruff check .
2. ruff format --check .
3. mypy app
4. pytest tests/unit/ tests/compliance/ -v --tb=short -x
5. pytest tests/ci/ -v --tb=short -x
6. python tools/audit_engine.py --strict
7. python tools/verify_contracts.py
```

### Banned Patterns (from .cursorrules)
**Merge-blocking violations:**
- f-string Cypher without `sanitize_label()`
- `eval()`, `exec()`, `pickle.load()`
- `yaml.load()` without SafeLoader
- `from fastapi import` in engine/ (except app/api/, app/main.py, handlers.py)
- `httpx.post/get` in engine/ (delegation protocol violation)
- `raise NotImplementedError` outside tests/ (zero-stub protocol)

## Constraints

### File Modification Rules
1. **NEVER modify:** Dockerfile, docker-compose.yml, CI workflows (l9-template managed)
2. **ALWAYS add:** L9_META header via `tools/l9_meta_injector.py`
3. **ALWAYS use:** Type hints on all function signatures
4. **ALWAYS use:** `structlog.get_logger(__name__)` for logging (never print())
5. **ALWAYS use:** Pydantic v2 BaseModel for structured data

### Import Patterns (Canonical)
```python
# ONLY in engine/handlers.py:
from chassis.router import register_handler

# Domain specs:
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec, GateSpec, ScoringDimension

# Gate compilation:
from engine.gates.compiler import GateCompiler
from engine.gates.types import RangeGate, ThresholdGate, BooleanGate

# Packet protocol:
from engine.packet.chassis_contract import inflate_ingress, deflate_egress
from engine.packet.packet_envelope import PacketEnvelope, PacketMetadata
```

### Ruff Configuration (from pyproject.toml)
```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM", "TCH"]
ignore = [
    "E501",     # formatter handles line length
    "TC001",    # typing-only first-party import (Pydantic v2 runtime)
    "SIM105",   # contextlib.suppress (explicit try/except preferred)
    "TRY003",   # long exception messages acceptable
    "ARG001",   # unused function args (handler interface compliance)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["PLR2004", "PT011", "E741", "SIM102", "F841", "F821"]
"engine/config/**" = ["PLR2004"]
"tools/**" = ["PLC0415", "E741", "SIM102"]
```

### MyPy Configuration (from pyproject.toml)
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
check_untyped_defs = true
follow_imports = "silent"
exclude = ["app/engines/field_classifier\.py", "app/engines/inference_bridge_v2\.py"]
```

## Known Unknowns
- Specific Neo4j database schema (referenced but not documented)
- GDS algorithm runtime execution details (spec-driven, implementation opaque)
- Memory substrate PostgreSQL schema (mentioned in contracts, DDL unknown)
- Production deployment configuration (Railway/ArgoCD referenced, configs unknown)

## Agent Guidance

### When Reviewing Code
1. **Check Contracts First:** Does it violate any of the 20 contracts in .cursorrules?
2. **Check Banned Patterns:** Scan for SEC-001 through ENV-001 violations
3. **Check Imports:** Engine code importing FastAPI? Instant reject
4. **Check Type Hints:** Missing type hints on function signatures? Request addition
5. **Check Tests:** New logic without tests? Request unit/compliance tests
6. **Check L9_META:** Missing header on new files? Request injection

### When Generating Code
1. **Use Existing Patterns:** Copy structure from similar existing files
2. **Follow Directory Structure:** Never create new top-level directories
3. **Add Type Hints:** Every signature, every class attribute
4. **Use Structlog:** `structlog.get_logger(__name__)`, never `print()`
5. **Add Tests:** Unit tests in `tests/unit/`, compliance in `tests/compliance/`
6. **Run Agent Check:** Include `make agent-check` in PR description

### When Answering Questions
1. **Cite Source Files:** Reference specific SHA hashes from repository
2. **Quote Exact Paths:** Use verbatim file paths from repository
3. **Quote Exact Commands:** Copy commands from Makefile exactly
4. **Admit Unknowns:** If information not in repository → state "Unknown"
5. **Reference Contracts:** Cite specific contract numbers (1-20) from .cursorrules

### Terminology Corrections
- **NEVER say:** "best practices", "as needed", "etc", "where appropriate"
- **ALWAYS say:** Specific contract names, exact file paths, explicit rules
- **NEVER invent:** Environment variables, secret names, config keys
- **ALWAYS quote:** Exact names from `.env.example`, `pyproject.toml`, workflows

### CI Pipeline Awareness (from ci.yml)
**Workflow name:** "CI Pipeline"
**Triggers:** push (main, develop), pull_request (main, develop), workflow_dispatch
**Jobs:**
1. `validate` (10min) — Python syntax, YAML validation, KB YAML validation
2. `lint` (10min) — ruff check, ruff format --check, mypy
3. `semgrep` (10min) — Semgrep policy check (.semgrep/ directory)
4. `test` (30min) — Full pytest with coverage ≥60%, PostgreSQL + Redis services
5. `security` (15min) — Gitleaks, pip-audit, Safety, Bandit (non-blocking warnings)
6. `sbom` (10min) — Anchore SBOM generation (spdx-json)
7. `scorecard` (15min) — OpenSSF Scorecard
8. `ci-gate` (5min) — Fan-in gate, blocks merge if validate/lint/semgrep/test fail

**Non-blocking steps:**
- Mypy warnings (step continues with echo)
- pip-audit vulnerabilities (echo "⚠️ Vulnerabilities found (non-blocking)")
- Safety check warnings (echo "⚠️ Safety check warnings (non-blocking)")
- Bandit warnings (echo "⚠️ Security warnings found (non-blocking)")

**Merge-blocking failures:**
- validate, lint, semgrep, test (any failure blocks ci-gate)

### Compliance Workflow Awareness (from compliance.yml)
**Workflow name:** "Architecture Compliance"
**Triggers:** pull_request, push (main), workflow_dispatch
**Checks:**
1. **Terminology Guard:** Scans for `\bprint\(`, `\bOptional\[`, `\bList\[`, `\bDict\[`
2. **Chassis Isolation:** Rejects FastAPI imports outside app/api/, app/main.py, handlers.py
3. **KB YAML Schema:** Validates rules[].field, rules[].conditions/when blocks
4. **L9 Contract Audit:** Runs `tools/audit_engine.py --strict` (if available)
5. **L9 Contract Verification:** Runs `tools/verify_contracts.py` (if available)

**All checks blocking:** Any failure prevents merge
