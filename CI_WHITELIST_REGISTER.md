# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, ci, waivers, enforcement]
# owner: platform
# status: active
# token_estimate: 1485
# ssot_for: [ci-waivers, merge-blocking-gates, non-blocking-jobs, ci-agent-response]
# load_when: [ci_failure, pr_review, ci_question]
# references: [AGENT.md, docs/adr/]
# --- /L9_META ---

# CI_WHITELIST_REGISTER.md — CI Waivers & Non-Blocking Checks

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> Agent CI response protocol: see §Agent Response to CI Failures below.
> Gate sequence definition: see AGENT.md §Mandatory Pre-Commit Command (SSOT).

---

## Merge-Blocking Gates (ALL must pass to merge)

| Gate | CI Step Name | Fail = Block? | Enforcement |
|---|---|---|---|
| 1 | `validate` | YES | Python syntax + YAML validation |
| 2 | `lint-ruff` | YES | ruff check (auto-fixable with make agent-fix) |
| 3 | `lint-format` | YES | ruff format --check |
| 4 | `test` | YES | pytest unit + compliance + ci (coverage >= 60%) |
| 5 | `compliance-chassis` | YES | FastAPI import isolation check |
| 6 | `compliance-terminology` | YES | print(), Optional[], List[], Dict[] pattern scan |
| 7 | `semgrep` | YES | .semgrep/ custom security rules |
| 8 | `contracts` | YES | verify_contracts.py L9_META check |

---

## Non-Blocking Jobs (Failures allowed — informational only)

| Job | Waiver | ADR | Review Cadence |
|---|---|---|---|
| `lint-mypy` | WAIVER-001 | ADR-001 | Quarterly |
| `security-pip-audit` | WAIVER-002 | ADR-002 | Monthly |
| `security-safety-check` | WAIVER-003 | ADR-003 | Monthly |
| `security-bandit` | WAIVER-004 | ADR-004 | Quarterly |
| `coverage-codecov-upload` | WAIVER-005 | ADR-005 | As needed |
| `audit-l9-audit-tool` | WAIVER-006 | ADR-006 | Until tool stabilized |
| `verify-l9-verify-tool` | WAIVER-007 | ADR-007 | Until tool stabilized |

---

## Waiver Registry

### WAIVER-001 — MyPy Non-Blocking
- **Job**: `lint-mypy`
- **Reason**: Progressive type annotation rollout — mypy failures do not indicate functional regressions.
- **Policy**: Mypy errors are logged; PRs may merge. Reducing mypy errors is encouraged.
- **ADR**: `docs/adr/ADR-001-mypy-non-blocking.md`
- **Expires**: When type annotation coverage reaches 80%

### WAIVER-002 — pip-audit Non-Blocking
- **Job**: `security-pip-audit`
- **Reason**: Audit advisories require human triage; automated block would produce false-positive merge blocks.
- **Policy**: CVE reports reviewed weekly by platform team. Critical CVEs trigger expedited manual merge block.
- **ADR**: `docs/adr/ADR-002-ci-pip-audit-non-blocking.md`
- **Expires**: Never (policy decision)

### WAIVER-003 — safety check Non-Blocking
- **Job**: `security-safety-check`
- **Reason**: Overlaps with pip-audit; secondary safety net only.
- **ADR**: `docs/adr/ADR-003-ci-safety-check-non-blocking.md`
- **Expires**: Never (policy decision)

### WAIVER-004 — Bandit Non-Blocking
- **Job**: `security-bandit`
- **Reason**: Many B1xx findings are acceptable in this codebase; blanket blocking creates noise.
- **Policy**: HIGH severity bandit findings trigger manual review flag.
- **ADR**: `docs/adr/ADR-004-ci-bandit-non-blocking.md`
- **Expires**: When bandit rule set is tuned to zero false-positives

### WAIVER-005 — Codecov Upload Non-Blocking
- **Job**: `coverage-codecov-upload`
- **Reason**: Upload failure is a network/token issue, not a code quality issue. Coverage gate (60%) is enforced in the blocking `test` job.
- **ADR**: `docs/adr/ADR-005-ci-codecov-upload-non-blocking.md`
- **Expires**: Never (policy decision)

### WAIVER-006 — L9 Audit Tool Non-Blocking
- **Job**: `audit-l9-audit-tool`
- **Reason**: tools/audit_engine.py is under active development; CLI interface may not be stable.
- **Status**: TODO — this waiver is temporary, not permanent policy. Target: remove by milestone 2.0.
- **ADR**: `docs/adr/ADR-006-ci-l9-audit-tool-non-blocking.md`
- **Expires**: Milestone 2.0 (convert to blocking when tool stabilizes)

### WAIVER-007 — L9 Verify Tool Non-Blocking
- **Job**: `verify-l9-verify-tool`
- **Reason**: tools/verify_contracts.py is under active development.
- **Status**: TODO — temporary waiver. Target: remove by milestone 2.0.
- **ADR**: `docs/adr/ADR-007-ci-l9-verify-tool-non-blocking.md`
- **Expires**: Milestone 2.0

---

## Agent Response to CI Failures

| Failed Step | Blocking? | Agent Action |
|---|---|---|
| `validate` | YES | Fix Python syntax or YAML before any other work |
| `lint-ruff` | YES | Run `make agent-fix` then re-push |
| `lint-format` | YES | Run `make agent-fix` then re-push |
| `lint-mypy` | NO | Log warning; do not block (WAIVER-001) |
| `test` | YES | Add tests until coverage >=60%; fix failing assertions |
| `compliance-chassis` | YES | Remove FastAPI import from engine/; verify handler boundary (C-01) |
| `compliance-terminology` | YES | Replace print(), Optional[], List[], Dict[] with compliant equivalents |
| `semgrep` | YES | Read .semgrep/ rules, fix violation; escalate to platform team if rule is unclear |
| `security-pip-audit` | NO | Log warning; do not block (WAIVER-002) |
| `security-safety-check` | NO | Log warning; do not block (WAIVER-003) |
| `security-bandit` | NO | Note HIGH findings; do not block (WAIVER-004) |
| `coverage-codecov-upload` | NO | Network/token issue; do not block (WAIVER-005) |
| `audit-l9-audit-tool` | NO | Log; do not block (WAIVER-006) |
| `verify-l9-verify-tool` | NO | Log; do not block (WAIVER-007) |
| `contracts` | YES | Fix L9_META header in flagged files; run make verify |

---

## Known Unknowns

| Item | Status | Risk Level |
|---|---|---|
| Gitleaks rule count and exact patterns | Undocumented | LOW — upstream maintained |
| Semgrep cloud rules (vs local .semgrep/) | Undocumented | MEDIUM — scope unclear |
| Scorecard-action minimum passing score | Undocumented | LOW — informational only |
