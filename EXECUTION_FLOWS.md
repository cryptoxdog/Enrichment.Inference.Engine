# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, execution, flows, runtime]
# owner: platform
# status: active
# token_estimate: 825
# ssot_for: [runtime-flows, initialization-sequence, failure-flows]
# load_when: [control_flow_change, runtime_question, error_flow_question]
# references: [AGENT.md, CONFIG_ENV_CONTRACT.md, REPO_MAP.md]
# --- /L9_META ---

# EXECUTION_FLOWS.md — Runtime Execution Paths

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

Entry points cross-reference REPO_MAP.md. Tenant resolution: AGENT.md C-03. Circuit breaker env vars: CONFIG_ENV_CONTRACT.md.

## Initialization Sequence (8 Steps)

| Step | Action | Failure Behavior |
|---|---|---|
| 1 | pydantic-settings loads L9Settings from env | Raises ValidationError — lists all missing required fields — app does NOT start |
| 2 | structlog configured (chassis only) | Fatal — app does NOT start |
| 3 | Redis connection pool created | Logs CRITICAL + exits if REDIS_URL unreachable |
| 4 | Neo4j driver initialized (neo4j.AsyncDriver) | Logs CRITICAL + exits if L9_NEO4J_URI unreachable |
| 5 | PostgreSQL connection established | Logs CRITICAL + exits if DATABASE_URL unreachable |
| 6 | Domain packs loaded (DomainPackLoader) | Logs ERROR per invalid spec; continues with valid packs |
| 7 | FastAPI app registers routes (app/api/) | Fatal on route conflict |
| 8 | Uvicorn binds to 0.0.0.0:{L9_API_PORT} | Fatal if port in use |

Health check readiness: All 8 steps must complete before GET /v1/health returns healthy.

## Tenant Resolution Waterfall (5 Levels)

Resolved in order — first match wins:

1. HTTP header X-Tenant-ID
2. Subdomain extraction (tenant.api.domain.com)
3. API key prefix mapping (keys prefixed with tenant slug)
4. PacketEnvelope.tenant field (from request body)
5. Default tenant fallback (L9_DEFAULT_TENANT env var)

If no level resolves: returns HTTP 400 {"error": "tenant_resolution_failed"}.

## Failure Flows

### Neo4j Unreachable
1. Circuit breaker checks CB_FAILURE_THRESHOLD (default: 5 consecutive failures).
2. After threshold: opens circuit, returns HTTP 503 with retry_after = CB_COOLDOWN_SECONDS.
3. After CB_COOLDOWN_SECONDS (default: 60): circuit half-opens, next request probes.
4. If probe succeeds: circuit closes, normal operation resumes.

### Redis Timeout
1. Redis operations have socket_timeout from L9_REDIS_TIMEOUT_SECONDS.
2. On timeout: logs structlog.error(event="redis_timeout") and proceeds without cache.
3. No circuit breaker on Redis — graceful degradation (cache miss means re-query).

### Perplexity API Failure
1. Retry: 3 attempts with exponential backoff + jitter.
2. Concurrency: semaphore caps at 3 simultaneous requests (L9_PERPLEXITY_MAX_CONCURRENT).
3. After 3 failures: logs structlog.error(event="perplexity_exhausted"), returns HTTP 502.

### Startup Validation Failure (Missing Required Env Var)

Agent interpretation: missing env var — do NOT treat as code bug. Fix: add var to .env.
Example ValidationError will list all missing L9Settings fields by name.

## GDS Scheduler Flow

The GDS scheduler is spec-driven. No Python execution logic exists outside the scheduler.
The scheduler reads gds_jobs section from domain YAML and delegates to Neo4j GDS procedures.

Flow:
  DomainPackLoader reads gds_jobs[] from domain YAML
  -> GdsScheduler.schedule(job_spec)
  -> Validates spec (Pydantic)
  -> Executes Neo4j GDS procedure call
  -> Records result to PostgreSQL job_runs table
  -> Logs completion via structlog

## Known Documentation Gaps

| Flow | Status | Tracking |
|---|---|---|
| Neo4j internal query patterns | Unknown — no source access | Issue label: docs-gap |
| PostgreSQL access layer | Unknown | Issue label: docs-gap |
| KGE training flow | Unknown — implementation thin | Issue label: docs-gap |

Agents encountering an unknown flow: log structlog.warning(event="known_unknown", target="<flow>"), skip, annotate PR. See AGENT_BOOTSTRAP.md Known-Unknown Protocol.
