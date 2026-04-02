# REPO_MAP.md

## Purpose
Complete inventory of repository structure, file purposes, and module boundaries.

## Scope
Root-level directories, key configuration files, test organization

## Source Evidence
Repository scan at SHA 358d15dadc0d2426858c538e76ee5c1f967b835c

## Root Structure

```
├── .github/              → GitHub workflows, CODEOWNERS, PR templates
│   ├── workflows/        → CI/CD workflows (12 files)
│   ├── CODEOWNERS        → Code ownership rules
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml    → Dependency updates
├── app/                  → FastAPI application (chassis)
│   ├── agents/           → AI agent integrations
│   ├── api/              → HTTP routes (FastAPI allowed here)
│   ├── core/             → Core application logic
│   ├── engines/          → Enrichment engines
│   ├── health/           → Health check endpoints
│   ├── middleware/       → HTTP middleware
│   ├── models/           → Pydantic models
│   ├── score/            → Scoring logic
│   ├── services/         → Business services
│   └── main.py           → FastAPI app factory (entrypoint)
├── chassis/              → Thin chassis adapter
├── codegen/              → Code generation tools
├── config/               → Configuration management
├── domains/              → Domain-specific YAML configs
├── engine/               → Core matching engine (chassis-agnostic)
├── infra/                → Infrastructure configs
├── kb/                   → Knowledge base YAML rules
├── migrations/           → Database migrations (Alembic)
├── monitoring/           → Monitoring configs (Prometheus, Grafana)
├── odoo_modules/         → Odoo integration modules
├── readme/               → README assets
├── reports/              → Generated reports
├── scripts/              → Deployment/utility scripts
├── templates/            → Jinja2 templates
├── tests/                → Test suite
│   ├── ci/               → CI-specific tests
│   ├── compliance/       → Architecture compliance tests
│   ├── fixtures/         → Test fixtures
│   ├── integration/      → Integration tests
│   └── unit/             → Unit tests
└── tools/                → Development tools

## Key Configuration Files

### Python Configuration
- `pyproject.toml` → Build system, dependencies, ruff/mypy/pytest config
- `.python-version` → Python 3.12
- `requirements-ci.txt` → CI dependencies

### Docker
- `Dockerfile` → Development image
- `Dockerfile.prod` → Production image
- `docker-compose.yml` → Local development stack
- `docker-compose.prod.yml` → Production stack
- `.dockerignore` → Build exclusions

### Environment
- `.env.example` → Environment variable template
- `.env.template` → Alternative template
- `.env.required` → Required variables list

### Code Quality
- `.cursorrules` → AI agent contracts (26KB, 20 contracts)
- `.editorconfig` → Editor settings
- `.pre-commit-config.yaml` → Pre-commit hooks
- `.coveragerc` → Coverage configuration
- `pytest.ini` → Pytest configuration

### Security
- `.gitleaks.toml` → Secret scanning config
- `.semgrep/` → Semgrep policy rules

### Documentation
- `AGENTS.md` → AI agent guidance
- `ARCHITECTURE.md` → Architecture overview
- `CLAUDE.md` → Claude-specific guidance
- `GUARDRAILS.md` → Safety guardrails
- `TESTING.md` → Test requirements
- `SECURITY.md` → Security policy
- `CHANGELOG.md` → Version history

## Module Boundaries

### Chassis (app/)
**Purpose:** HTTP surface, tenant resolution, observability
**Imports allowed:** FastAPI, Starlette, Uvicorn, HTTP libraries
**Exports:** HTTP endpoints, middleware
**Entry point:** `app/main.py`

### Engine (engine/)
**Purpose:** Domain-agnostic matching logic, chassis-independent
**Imports forbidden:** FastAPI, Starlette, HTTP frameworks
**Imports allowed:** Neo4j driver, Redis client, Pydantic, structlog
**Entry point:** `engine/handlers.py` (chassis bridge)

### Tests (tests/)
**Structure:**
- `unit/` → Fast, isolated, no external services
- `integration/` → Requires Redis, PostgreSQL, Neo4j
- `compliance/` → Architecture contract verification
- `ci/` → Repository contract enforcement
- `conftest.py` → Shared pytest fixtures

## Test File Patterns

**Test file naming:** `test_*.py`
**Test class naming:** `class Test*`
**Test function naming:** `def test_*`
**Fixtures:** `tests/conftest.py`, `tests/fixtures/`

## Entry Points

### HTTP Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Development
```bash
make dev              # docker-compose up
make setup            # pip install + pre-commit hooks
```

### Testing
```bash
make test             # pytest tests/ -v
make test-unit        # pytest tests/unit/
make test-integration # pytest tests/integration/ -m integration
make agent-check      # Full 7-gate validation
```

### Quality
```bash
make lint             # ruff + mypy
make lint-fix         # Auto-fix issues
```
