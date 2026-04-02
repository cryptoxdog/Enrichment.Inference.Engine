# DEPENDENCY_SURFACE.md

## Purpose
Complete inventory of external dependencies, their versions, and usage constraints.

## Scope
Python packages (runtime + dev), system dependencies, external services

## Source Evidence
- `pyproject.toml` (SHA: 1d0739620a7614e5bdc48639b5bb299f7d444d4b)
- `requirements-ci.txt`
- `.github/workflows/ci.yml`

## Runtime Dependencies

### Core Framework
- `fastapi>=0.115.0` — HTTP framework (chassis only, forbidden in engine/)
- `uvicorn[standard]>=0.32.0` — ASGI server with HTTP/2 support
- `pydantic>=2.9.0` — Data validation, settings, models
- `pydantic-settings>=2.6.0` — Environment variable loading

### HTTP Client
- `httpx>=0.27.0` — Async HTTP client (forbidden in engine/ per CONTRACT 8)

### Data & Serialization
- `pyyaml>=6.0` — YAML parsing (MUST use SafeLoader per INVARIANT 13)
- `aiofiles>=23.0.0` — Async file operations

### Caching & State
- `redis>=5.0.0` — Redis client for caching

### Logging & Observability
- `structlog>=24.0.0` — Structured logging (chassis configures, engine uses)
- `opentelemetry-api>=1.27.0` — Telemetry API
- `opentelemetry-sdk>=1.27.0` — Telemetry SDK
- `opentelemetry-exporter-otlp-proto-grpc>=1.27.0` — OTLP exporter
- `opentelemetry-instrumentation-fastapi>=0.48b0` — FastAPI auto-instrumentation
- `opentelemetry-instrumentation-httpx>=0.48b0` — httpx auto-instrumentation
- `opentelemetry-instrumentation-redis>=0.48b0` — Redis auto-instrumentation

### AI/ML Services
- `perplexityai>=0.2.0` — Perplexity Sonar API client for enrichment

## Development Dependencies

### Testing
- `pytest==9.0.2` — Test framework (exact version pinned)
- `pytest-asyncio>=0.24` — Async test support
- `pytest-httpx>=0.34` — httpx mocking for tests
- `pytest-cov==7.1.0` — Coverage reporting (exact version pinned)
- `respx>=0.22` — HTTP mocking library

### Code Quality
- `ruff==0.15.8` — Fast linter + formatter (exact version pinned)
- `mypy==1.19.1` — Static type checker (exact version pinned)
- `coverage==7.13.5` — Coverage measurement (exact version pinned)

## CI-Specific Dependencies

From `requirements-ci.txt`:
- pytest ecosystem (pytest, pytest-asyncio, pytest-cov, pytest-httpx)
- ruff, mypy, coverage (same as dev)
- Additional security tools (pip-audit, safety, bandit)

## External Services (Runtime)

### Required Services
- **Neo4j** — Graph database
  - Image: `postgres:16` (variable: POSTGRES_IMAGE)
  - Connection via async driver
  - Tenant-scoped databases

- **Redis** — Cache + session store
  - Image: `redis:7-alpine` (variable: REDIS_IMAGE)
  - URL: `REDIS_URL` env var

- **PostgreSQL** — Relational database (memory substrate)
  - Image: `postgres:16`
  - Used in test services (ci.yml)
  - Connection: `DATABASE_URL` env var

### Optional Services (Enrichment Sources)
- **Perplexity Sonar** — AI research (required: PERPLEXITY_API_KEY)
- **Odoo** — CRM integration (ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
- **Salesforce** — CRM integration (SALESFORCE_* env vars)
- **HubSpot** — CRM integration (HUBSPOT_ACCESS_TOKEN)
- **Clearbit** — Enrichment (CLEARBIT_API_KEY)
- **ZoomInfo** — Enrichment (ZOOMINFO_API_KEY)
- **Apollo** — Enrichment (APOLLO_API_KEY)
- **Hunter** — Email enrichment (HUNTER_API_KEY)

## System Dependencies

### Python Runtime
- **Version:** 3.12+ (exact: 3.12 per `.python-version`)
- **Evidence:** `.python-version`, `pyproject.toml` requires-python = ">=3.11"

### Build Tools
- **setuptools>=61.0** — Build backend
- **make** — Task runner (Makefile)
- **docker** — Container runtime
- **docker-compose** — Multi-container orchestration

## Dependency Constraints

### Version Pinning Strategy
**Exact pins (==):**
- pytest==9.0.2
- pytest-cov==7.1.0
- ruff==0.15.8
- mypy==1.19.1
- coverage==7.13.5

**Reason:** Ensure reproducible CI/development environments

**Lower bounds (>=):**
- All runtime dependencies (fastapi, pydantic, redis, etc.)

**Reason:** Allow patch/minor upgrades for security fixes

### Import Restrictions
**Chassis-only imports:**
- `fastapi`, `starlette`, `uvicorn` (app/, app/main.py only)

**Engine-forbidden imports:**
- HTTP frameworks (fastapi, flask, django)
- httpx/requests direct usage (delegation protocol violation)

**Evidence:** `.cursorrules` CONTRACT 1, ARCH-001 through ARCH-003

### Dependency Update Policy
- **Dependabot:** Enabled (`.github/dependabot.yml`)
- **Schedule:** Weekly for Python dependencies
- **Auto-merge:** Security patches only
- **Manual review:** Minor/major version bumps

## Known Unknowns
- Neo4j Python driver version (not in pyproject.toml, likely imported transitively)
- Exact versions of transitive dependencies
- System package dependencies (libpq, etc.) not documented
