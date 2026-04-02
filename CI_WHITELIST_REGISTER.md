# CI_WHITELIST_REGISTER.md

## Purpose
Registry of all CI waivers, allowed failures, and non-blocking checks with justifications.

## Scope
GitHub Actions workflows, security scans, quality gates

## Source Evidence
- `.github/workflows/ci.yml` (SHA: 028e64cfd5c584ba850cd6330c528c2b8a09b44e)
- `.github/workflows/compliance.yml` (SHA: ab57ddb48a57ea1908ca535370441dd9fb787a5a)

## CI Waivers

### WAIVER-001: Mypy Type Check Warnings
**Workflow:** ci.yml
**Job:** lint
**Step:** Run Mypy Type Checker
**Behavior:** `|| echo "⚠️  Type check warnings (non-blocking)"`
**Justification:** Type hints are aspirational; warnings inform but don't block
**Evidence:** `.github/workflows/ci.yml` line 210
**Merge-blocking:** No

### WAIVER-002: pip-audit Vulnerabilities
**Workflow:** ci.yml
**Job:** security
**Step:** Run pip-audit (Dependency Vulnerabilities)
**Behavior:** `|| echo "⚠️  Vulnerabilities found (non-blocking)"`
**Justification:** Transitive dependency vulnerabilities may not have patches available
**Evidence:** `.github/workflows/ci.yml` line 364
**Merge-blocking:** No

### WAIVER-003: Safety Check
**Workflow:** ci.yml
**Job:** security
**Step:** Run Safety Check
**Behavior:** `|| echo "⚠️  Safety check warnings (non-blocking)"`
**Justification:** Safety database may have false positives or unpatchable issues
**Evidence:** `.github/workflows/ci.yml` line 370
**Merge-blocking:** No

### WAIVER-004: Bandit SAST
**Workflow:** ci.yml
**Job:** security
**Step:** Run Bandit (SAST)
**Behavior:** `|| echo "⚠️  Security warnings found (non-blocking)"`
**Justification:** Static analysis may flag false positives; manual review required
**Evidence:** `.github/workflows/ci.yml` line 381
**Merge-blocking:** No

### WAIVER-005: Codecov Upload Failure
**Workflow:** ci.yml
**Job:** test
**Step:** Upload Coverage to Codecov
**Behavior:** `fail_ci_if_error: false`
**Justification:** External service availability should not block CI
**Evidence:** `.github/workflows/ci.yml` line 318
**Merge-blocking:** No

### WAIVER-006: L9 Contract Audit
**Workflow:** compliance.yml
**Job:** architecture-compliance
**Step:** L9 Contract Audit (if available)
**Behavior:** `|| echo "Contract audit warnings (non-blocking)"`
**Justification:** Audit tool may not exist yet; warnings inform but don't block
**Evidence:** `.github/workflows/compliance.yml` line 118
**Merge-blocking:** No

### WAIVER-007: L9 Contract Verification
**Workflow:** compliance.yml
**Job:** architecture-compliance
**Step:** L9 Contract Verification (if available)
**Behavior:** `|| echo "Contract verification warnings (non-blocking)"`
**Justification:** Verification tool may not exist yet; warnings inform but don't block
**Evidence:** `.github/workflows/compliance.yml` line 125
**Merge-blocking:** No

## Non-Blocking Jobs

### JOB-001: SBOM Generation
**Workflow:** ci.yml
**Job:** sbom
**Purpose:** Generate Software Bill of Materials
**Blocking:** No (informational only)
**Evidence:** ci-gate job does NOT depend on sbom
**Merge-blocking:** No

### JOB-002: OpenSSF Scorecard
**Workflow:** ci.yml
**Job:** scorecard
**Purpose:** Security posture scoring
**Blocking:** No (informational only)
**Evidence:** ci-gate job does NOT depend on scorecard
**Merge-blocking:** No

## Merge-Blocking Gates

### GATE-001: Validation
**Workflow:** ci.yml
**Job:** validate
**Checks:**
- Python syntax (py_compile)
- YAML workflow validation
- KB YAML validation
**Merge-blocking:** Yes (ci-gate depends on validate)

### GATE-002: Lint
**Workflow:** ci.yml
**Job:** lint
**Checks:**
- ruff check (linting)
- ruff format --check (formatting)
- mypy (type checking, warnings non-blocking)
**Merge-blocking:** Yes (ci-gate depends on lint)

### GATE-003: Semgrep
**Workflow:** ci.yml
**Job:** semgrep
**Checks:** Semgrep policy rules (.semgrep/ directory)
**Merge-blocking:** Yes (ci-gate depends on semgrep)

### GATE-004: Test Suite
**Workflow:** ci.yml
**Job:** test
**Checks:**
- pytest with coverage ≥60%
- PostgreSQL + Redis integration
**Merge-blocking:** Yes (ci-gate depends on test)

### GATE-005: Terminology Guard
**Workflow:** compliance.yml
**Job:** architecture-compliance
**Step:** Terminology Guard
**Checks:** Bans `\bprint\(`, `\bOptional\[`, `\bList\[`, `\bDict\[`
**Merge-blocking:** Yes (compliance workflow fails if violations found)

### GATE-006: Chassis Isolation
**Workflow:** compliance.yml
**Job:** architecture-compliance
**Step:** Chassis Isolation Check
**Checks:** FastAPI imports outside allowed modules
**Merge-blocking:** Yes (compliance workflow fails if violations found)

### GATE-007: KB YAML Schema
**Workflow:** compliance.yml
**Job:** architecture-compliance
**Step:** KB YAML Schema Validation
**Checks:** Required keys (field, conditions/when) in rule files
**Merge-blocking:** Yes (compliance workflow fails if violations found)

## CI Failure Protocol

### When Non-Blocking Check Fails
1. Check logs in GitHub Actions UI
2. Assess risk (security vulnerability severity, etc.)
3. Create tracking issue if needed
4. Merge proceeds (informational only)

### When Merge-Blocking Gate Fails
1. CI blocks merge (branch protection)
2. Developer must fix violation
3. Push new commit
4. CI re-runs automatically
5. All gates must pass before merge

## ADR References

### ADR-001: Mypy Warnings Non-Blocking
**Decision:** Allow mypy warnings to pass CI
**Rationale:** Type hints are gradual; strict mode would block too much valid code
**File:** See WAIVER-001

### ADR-002: Security Scan Warnings Non-Blocking
**Decision:** Allow pip-audit, Safety, Bandit warnings to pass CI
**Rationale:** False positives common; manual security review required anyway
**Files:** See WAIVER-002, WAIVER-003, WAIVER-004

## Known Unknowns
- Gitleaks behavior (no explicit non-blocking marker, assumed blocking)
- Dependency Review Action behavior (only runs on PRs, fail-on-severity: high)
- Exact Semgrep rule count (.semgrep/ directory not examined)
