# EXECUTION_FLOWS.md

## Purpose
Documents runtime execution paths, entrypoints, and control flow through the system.

## Scope
HTTP request flows, background jobs, initialization sequences

## Source Evidence
- `app/main.py`
- `Makefile`
- `.github/workflows/ci.yml`
- `.cursorrules` CONTRACT 1, 2

## HTTP Request Flow

### 1. Request Ingress
```
Client → FastAPI (app/main.py) → Middleware → Router
```

**Entrypoint:** `POST /v1/execute` or `GET /v1/health`

### 2. Tenant Resolution (5-Level Waterfall)
```
1. X-Tenant-ID header
2. Subdomain (tenant.example.com)
3. API key prefix (tenant_...)
4. PacketEnvelope.tenant field
5. Default tenant (fallback)
```

**Implementation:** Chassis middleware (`.cursorrules` CONTRACT 3)

### 3. Handler Dispatch
```
Router → engine/handlers.py → handle_<action>(tenant: str, payload: dict)
```

**Handler signature:** `async def handle_<action>(tenant: str, payload: dict) -> dict`

### 4. PacketEnvelope Inflation
```
inflate_ingress(raw_payload) → PacketEnvelope (frozen Pydantic model)
```

**Evidence:** `.cursorrules` CONTRACT 6

### 5. Engine Execution
```
handle_<action> → Domain logic → Neo4j queries → Redis caching
```

### 6. PacketEnvelope Deflation
```
PacketEnvelope → deflate_egress() → JSON response
```

### 7. Response Egress
```
FastAPI → Middleware → Client
```

## Background Job Flows

### GDS Scheduler (Graph Data Science)
**Trigger:** Cron schedule or manual invocation
**Flow:**
```
APScheduler → engine/gds/scheduler.py → GDS algorithm → Neo4j write
```

**Configuration:** Domain spec `gds_jobs` section
**Evidence:** `.cursorrules` CONTRACT 19

## Initialization Sequences

### Application Startup
```
1. Load environment variables (.env)
2. Configure structlog (chassis only)
3. Initialize FastAPI app (app/main.py)
4. Register middleware
5. Register routes (app/api/)
6. Initialize handlers (engine/handlers.py)
7. Connect to Neo4j, Redis, PostgreSQL
8. Start uvicorn server
```

### Domain Spec Loading
```
1. Read {domain_id}_domain_spec.yaml from domains/
2. Parse YAML → Python dict
3. Validate with DomainPackLoader
4. Convert to DomainConfig (Pydantic model)
5. Compile gates → Cypher WHERE clauses
6. Compile scoring → Cypher WITH/ORDER BY
```

**Evidence:** `.cursorrules` CONTRACT 12

## Command Execution Flows

### make agent-check
```
1. ruff check .
2. ruff format --check .
3. mypy app
4. pytest tests/unit/ tests/compliance/ -v --tb=short -x
5. pytest tests/ci/ -v --tb=short -x
6. python tools/audit_engine.py --strict
7. python tools/verify_contracts.py
```

**Evidence:** `Makefile` agent-check target

### CI Pipeline (ci.yml)
```
1. Checkout repository
2. Setup Python 3.12
3. validate job (syntax, YAML validation)
4. lint job (ruff, mypy)
5. semgrep job (policy check)
6. test job (pytest with coverage, PostgreSQL + Redis services)
7. security job (Gitleaks, pip-audit, Safety, Bandit)
8. sbom job (Anchore SBOM generation)
9. scorecard job (OpenSSF Scorecard)
10. ci-gate job (fan-in, blocks merge if required jobs fail)
```

**Evidence:** `.github/workflows/ci.yml`

## Unknown Flows
- Neo4j query execution details (driver usage patterns unknown)
- Memory substrate PostgreSQL access patterns (referenced but not documented)
- KGE CompoundE3D training/inference flow (mentioned but not implemented)
