# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, config, env-vars, contract]
# owner: platform
# status: active
# token_estimate: 1556
# ssot_for: [environment-variables, loading-order, minimum-dev-env]
# load_when: [env_var_change, config_question, startup_failure]
# references: [AGENT.md, INVARIANTS.md INV-20, .github/env.template]
# --- /L9_META ---

# CONFIG_ENV_CONTRACT.md — Environment Variables Contract

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> All env var names follow L9_ prefix convention (INVARIANT 20) unless noted as infrastructure-standard.
> Loading order: OS environment > .env file > pydantic-settings defaults.
> On missing required variable: pydantic-settings raises ValidationError listing ALL missing fields before app starts.

---

## Minimum .env for `make dev`

```bash
# Minimum required for local development
PERPLEXITY_API_KEY=pplx-your-key-here
REDIS_URL=redis://localhost:6379/0
API_SECRET_KEY=your-32-plus-char-secret-here
API_KEY_HASH=sha256-of-your-api-key-here
L9_NEO4J_URI=bolt://localhost:7687
L9_NEO4J_USER=neo4j
L9_NEO4J_PASSWORD=your-neo4j-password
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/enrichment
```

Copy from `.env.example` and fill in values. Never commit `.env` (gitignored).

---

## Environment Variables

### Required — Application Will NOT Start Without These

| Variable | Type | Description | L9_ Prefix |
|---|---|---|---|
| `PERPLEXITY_API_KEY` | str | Perplexity API key | No (external service) |
| `API_SECRET_KEY` | str (32+ chars) | HMAC signing key for API auth | No (standard) |
| `API_KEY_HASH` | str | SHA-256 hash of the API key | No (standard) |
| `L9_NEO4J_URI` | str | Neo4j bolt URI | Yes |
| `L9_NEO4J_USER` | str | Neo4j username | Yes |
| `L9_NEO4J_PASSWORD` | str | Neo4j password | Yes |
| `DATABASE_URL` | str | SQLAlchemy async DB URL | No (SQLAlchemy standard) |
| `REDIS_URL` | str | Redis connection URL | No (Redis standard) |

### Optional — Have Defaults

| Variable | Type | Default | Description | L9_ Prefix |
|---|---|---|---|---|
| `L9_API_PORT` | int | 8000 | Uvicorn bind port | Yes |
| `L9_LOG_LEVEL` | str | INFO | structlog level | Yes |
| `L9_DEFAULT_TENANT` | str | default | Fallback tenant ID (level 5 waterfall) | Yes |
| `L9_PERPLEXITY_MAX_CONCURRENT` | int | 3 | Semaphore for concurrent Perplexity requests | Yes |
| `L9_REDIS_TIMEOUT_SECONDS` | int | 5 | Redis socket timeout | Yes |
| `CB_FAILURE_THRESHOLD` | int | 5 | Circuit breaker failure count before open | No (infra-standard) |
| `CB_COOLDOWN_SECONDS` | int | 60 | Circuit breaker cooldown before half-open probe | No (infra-standard) |
| `MIN_VALID` | int | 2 | Minimum valid Perplexity responses before synthesis | No |
| `TESTING` | bool | False | Disables external calls in test mode | No (pytest standard) |

### CI Environment Variables (Not for Local Dev)

| Variable | Set By | Purpose |
|---|---|---|
| `CODECOV_TOKEN` | GitHub Actions secret | Coverage upload |
| `GITHUB_TOKEN` | GitHub Actions auto | Release drafter |
| `SEMGREP_APP_TOKEN` | GitHub Actions secret | Semgrep cloud rules |

---

## AWS Secrets Manager

**STATUS: ASPIRATIONAL — NOT IMPLEMENTED.**
AWS Secrets Manager is referenced in the architecture roadmap but is NOT currently implemented
in any code path. Do NOT add AWS SDK calls expecting this infrastructure to exist.
Track: GitHub issue label `infra-roadmap`.

---

## Circuit Breaker Configuration

`CB_FAILURE_THRESHOLD` and `CB_COOLDOWN_SECONDS` govern Neo4j circuit breaker behavior.
See EXECUTION_FLOWS.md §Neo4j Unreachable for the full failure flow.

---

## Startup Failure Interpretation

When app fails to start with `ValidationError`:
- The error lists ALL missing `L9Settings` fields by name.
- Do NOT treat this as a code bug.
- Fix: add missing variables to `.env` using `.env.example` as template.
- The `.env.example` is the source of truth for all variable names and placeholder formats.
