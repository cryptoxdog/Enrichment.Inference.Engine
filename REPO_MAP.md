# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, repo-map, structure, ownership]
# owner: platform
# status: active
# token_estimate: 1217
# ssot_for: [directory-structure, module-boundaries, codeowners-map]
# load_when: [new_file, directory_question, ownership_question]
# references: [AGENT.md, .github/CODEOWNERS, AGENTS.md]
# --- /L9_META ---

# REPO_MAP.md — Repository Structure Map

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> SSOT for directory structure and module ownership.
> Module boundary rules (chassis/engine separation): see AGENT.md C-01.
> Execution flows for entry points: see EXECUTION_FLOWS.md.

---

## Module Boundary (SSOT — All Other Docs Reference Here)

CHASSIS (FastAPI layer): app/main.py, app/api/, app/engines/handlers.py
  May import: fastapi, engine.*, app.models.*

ENGINE (Business logic — chassis-agnostic): engine/, app/engines/ (excl. handlers.py), app/score/, app/health/, app/services/
  MUST NOT import: fastapi

MODELS (Schema — frozen Pydantic v2): app/models/
  Imported by both chassis and engine

---

## Directory Map

| Directory | Purpose | Owner | Agent Tier | CODEOWNERS |
|---|---|---|---|---|
| app/ | FastAPI application root | Platform | T2+ | @cryptoxdog |
| app/api/ | HTTP route handlers | API team | T3+ | @cryptoxdog |
| app/engines/ | Core enrichment engine modules | Engine team | T3+ | @cryptoxdog |
| app/engines/chassis_contract.py | Dispatch contract | Platform | T4 | @cryptoxdog |
| app/engines/handlers.py | Request handlers | Platform | T4 | @cryptoxdog |
| app/engines/graph_sync_client.py | Graph protocol | Platform | T4 | @cryptoxdog |
| app/models/ | Pydantic v2 schemas (frozen) | Schema team | T5 | @cryptoxdog |
| app/score/ | Scoring engine | Score team | T3+ | @cryptoxdog |
| app/health/ | Health check logic | Health team | T3+ | @cryptoxdog |
| app/services/ | External service clients | Services team | T3+ | @cryptoxdog |
| engine/ | Chassis-agnostic engine utilities | Engine team | T3+ | @cryptoxdog |
| engine/utils/security.py | sanitize_label(), auth utils | Platform | T4 | @cryptoxdog |
| kb/ | Knowledge base YAML rule files | Knowledge team | T5 | @cryptoxdog |
| tests/ | All test suites | Any | T2+ | — |
| tests/unit/ | Unit tests (no external deps) | Any | T2+ | — |
| tests/integration/ | Integration tests | Any | T2+ | — |
| tests/compliance/ | Architecture compliance tests | Platform | T2+ | @cryptoxdog |
| tests/ci/ | CI contract enforcement tests | Platform | T2+ | @cryptoxdog |
| tools/ | Audit + verification scripts | Platform | T2+ | @cryptoxdog |
| tools/audit_engine.py | 27-rule audit engine | Platform | T2+ | @cryptoxdog |
| tools/verify_contracts.py | L9_META contract verification | Platform | T2+ | @cryptoxdog |
| docs/ | Documentation and audits | Any | T1+ | — |
| chassis/ | Chassis abstraction layer | Platform | T3+ | @cryptoxdog |
| codegen/ | Code generation templates | Platform | T2+ | @cryptoxdog |
| config/ | Application config modules | Platform | T3+ | @cryptoxdog |
| domains/ | Domain spec YAML files | Domain teams | T3+ | @cryptoxdog |
| infra/ | Infrastructure-as-code | Platform | T3+ | @cryptoxdog |
| migrations/ | Alembic DB migrations | Platform | T3+ | @cryptoxdog |
| monitoring/ | Observability config | Platform | T2+ | @cryptoxdog |
| odoo_modules/ | Odoo ERP integration modules | Odoo team | T3+ | @cryptoxdog |
| reports/ | Generated audit/scan reports | Auto-generated | READ-ONLY | — |
| scripts/ | Deployment and utility scripts | Platform | T3+ | @cryptoxdog |
| templates/ | L9 template source files | Platform | T3+ | @cryptoxdog |
| readme/ | README assets | Any | T1+ | — |
| .github/ | CI workflows, CODEOWNERS, templates | Platform | T2+ | @cryptoxdog |
| .semgrep/ | Semgrep policy rules | Platform | T3+ | @cryptoxdog |

---

## Key Files

| File | Purpose | Agent Relevance |
|---|---|---|
| app/main.py | FastAPI app entrypoint | Entry point for all HTTP traffic |
| app/engines/chassis_contract.py | T4 — dispatch contract | Do not modify without T4 gate |
| app/engines/handlers.py | T4 — request handlers | Sync with chassis_contract.py always |
| app/models/packet.py | PacketEnvelope (frozen) | Do not mutate instances |
| engine/utils/security.py | sanitize_label() | Always use for Cypher strings |
| tools/audit_engine.py | 27-rule audit engine | Run via make audit |
| tools/verify_contracts.py | L9_META verifier (SHA: 2d30a79) | Run via make verify — confirmed present |
| .cursorrules | 20 contracts for Cursor | Always loaded by Cursor |
| pyproject.toml | Build + tool config | SSOT for ruff/mypy/pytest config |
| .github/CODEOWNERS | Required reviewer map | Route T4/T5 PRs accordingly |

---

## Test File Naming Convention

| Test Type | Path Pattern | Marker |
|---|---|---|
| Unit | tests/unit/test_*.py | @pytest.mark.unit |
| Integration | tests/integration/test_*.py | @pytest.mark.integration |
| Compliance | tests/compliance/test_*.py | (no extra marker) |
| CI contracts | tests/ci/test_*.py | (no extra marker) |
| Slow/convergence | Any | @pytest.mark.slow |

---

## Entry Points to Execution Flows

| Entry Point | Command | Flow |
|---|---|---|
| HTTP API | uvicorn app.main:app --host 0.0.0.0 --port 8000 | See EXECUTION_FLOWS.md HTTP Request Flow |
| Dev server | make dev (docker compose) | See EXECUTION_FLOWS.md Initialization Sequence |
| Audit | make audit | tools/audit_engine.py — standalone |
| Contract verify | make verify | tools/verify_contracts.py — standalone |
