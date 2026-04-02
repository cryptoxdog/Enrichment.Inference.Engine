# CONFIG_ENV_CONTRACT.md

## Purpose
Codifies all environment variables, their types, defaults, and usage contracts.

## Scope
Environment variables, configuration loading, secrets management

## Source Evidence
- `.env.example` (SHA: 46e040cb56ef81bf8cf408202a122465b6c13d92)
- `.env.template`
- `.env.required`
- `.github/workflows/ci.yml`

## Environment Variables

### Core Application
**APP_ENV**
- Type: `string`
- Values: `development | staging | production`
- Default: `development`
- Required: No

**LOG_LEVEL**
- Type: `string`
- Values: `DEBUG | INFO | WARNING | ERROR | CRITICAL`
- Default: `INFO`
- Required: No

### API Authentication
**API_SECRET_KEY**
- Type: `string`
- Min length: 32 characters
- Generation: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- Required: Yes (production)
- Evidence: `.env.example` line 18

**API_KEY_HASH**
- Type: `string` (SHA-256 hex digest)
- Format: `sha256-of-client-api-key`
- Generation: `python -c "import hashlib; print(hashlib.sha256(b'YOUR_KEY').hexdigest())"`
- Required: Yes (production)
- Evidence: `.env.example` line 19

### Knowledge Base
**KB_DIR**
- Type: `path`
- Default: `/app/kb`
- Required: No
- Evidence: `.env.example` line 22

### Redis
**REDIS_URL**
- Type: `string` (Redis connection URL)
- Format: `redis://host:port/db`
- Default: `redis://redis:6379/0`
- Required: Yes
- Evidence: `.env.example` line 25

### Perplexity Sonar
**PERPLEXITY_API_KEY**
- Type: `string` (API key)
- Format: `pplx-xxxxxxxxxxxxxxxxxxxx`
- Required: Yes (for enrichment)
- Evidence: `.env.example` line 12

**PERPLEXITY_MODEL**
- Type: `string`
- Default: `sonar-reasoning`
- Required: No
- Evidence: `.env.example` line 13

### Enrichment Defaults
**DEFAULT_CONSENSUS_THRESHOLD**
- Type: `float`
- Range: 0.0 - 1.0
- Default: `0.65`
- Required: No
- Evidence: `.env.example` line 28

**DEFAULT_MAX_VARIATIONS**
- Type: `int`
- Default: `5`
- Required: No
- Evidence: `.env.example` line 29

**DEFAULT_TIMEOUT_SECONDS**
- Type: `int`
- Default: `120`
- Required: No
- Evidence: `.env.example` line 30

**MAX_CONCURRENT_VARIATIONS**
- Type: `int`
- Default: `3`
- Required: No
- Evidence: `.env.example` line 31

**MAX_ENTITIES_PER_BATCH**
- Type: `int`
- Default: `50`
- Required: No
- Evidence: `.env.example` line 32

### Circuit Breaker
**CB_FAILURE_THRESHOLD**
- Type: `int`
- Default: `5`
- Required: No
- Evidence: `.env.example` line 35

**CB_COOLDOWN_SECONDS**
- Type: `int`
- Default: `60`
- Required: No
- Evidence: `.env.example` line 36

### Odoo CRM
**ODOO_URL**
- Type: `string` (URL)
- Format: `https://your-instance.odoo.com`
- Required: No (if Odoo integration enabled)
- Evidence: `.env.example` line 39

**ODOO_DB**
- Type: `string`
- Required: No
- Evidence: `.env.example` line 40

**ODOO_USER**
- Type: `string`
- Required: No
- Evidence: `.env.example` line 41

**ODOO_PASSWORD**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 42

### Salesforce CRM
**SALESFORCE_CLIENT_ID**
- Type: `string`
- Required: No
- Evidence: `.env.example` line 45

**SALESFORCE_CLIENT_SECRET**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 46

**SALESFORCE_USERNAME**
- Type: `string`
- Required: No
- Evidence: `.env.example` line 47

**SALESFORCE_PASSWORD**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 48

**SALESFORCE_SECURITY_TOKEN**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 49

### HubSpot CRM
**HUBSPOT_ACCESS_TOKEN**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 52

### Enrichment Sources (Waterfall Providers)
**CLEARBIT_API_KEY**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 55

**ZOOMINFO_API_KEY**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 56

**APOLLO_API_KEY**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 57

**HUNTER_API_KEY**
- Type: `string` (secret)
- Required: No
- Evidence: `.env.example` line 58

### Cognitive Engine Graphs (Sibling Node)
**CEG_BASE_URL**
- Type: `string` (URL)
- Format: `http://host:port`
- Default: `http://localhost:8001`
- Required: No
- Evidence: `.env.example` line 61

## CI Environment Variables

From `.github/workflows/ci.yml`:

**PYTHON_VERSION**
- Type: `string`
- Default: `3.12`
- Source: `vars.PYTHON_VERSION` or hardcoded

**COVERAGE_THRESHOLD**
- Type: `int`
- Default: `60`
- Source: `vars.COVERAGE_THRESHOLD` or hardcoded

**TEST_DIR**
- Type: `string`
- Default: `tests/`
- Source: `vars.TEST_DIR` or hardcoded

**SOURCE_DIR**
- Type: `string`
- Default: `app`
- Source: `vars.SOURCE_DIR` or hardcoded

**DATABASE_URL** (test services)
- Type: `string`
- Format: `postgresql://user:password@host:port/database`
- Computed: `postgresql://${POSTGRES_USER}:test_password@localhost:5432/${POSTGRES_DB}`

**REDIS_URL** (test services)
- Type: `string`
- Default: `redis://localhost:6379/0`

**TESTING**
- Type: `string`
- Value: `"true"`
- Purpose: Flag for test environment detection

## Configuration Loading

### Pydantic Settings
**Loader:** `pydantic-settings>=2.6.0`
**Evidence:** `pyproject.toml` dependency

**Loading order:**
1. Environment variables (highest priority)
2. .env file (if exists)
3. Default values in Settings class

### Secret Management
**Development:** .env file (never committed)
**Production:** Environment variables or secret manager (AWS Secrets Manager referenced)

## Constraints

### Naming Convention
**Infrastructure vars:** `L9_` prefix (per INVARIANT 20)
**Engine-specific vars:** No prefix

### Required vs Optional
**Required (production):**
- `PERPLEXITY_API_KEY`
- `API_SECRET_KEY`
- `API_KEY_HASH`
- `REDIS_URL`

**Optional:** All CRM/enrichment source credentials (feature-gated)

### Validation
**Type checking:** Pydantic Settings validates types
**Format validation:** Custom validators for URLs, API keys
**Missing required:** Pydantic raises ValidationError on startup

## Known Unknowns
- `.env.required` file contents (referenced but not examined)
- Exact Pydantic Settings class structure (not in evidence)
- Secret rotation policy (not documented)
- Vault/KMS integration details (referenced but not implemented)
