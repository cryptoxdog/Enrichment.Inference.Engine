# CI_WHITELIST_REGISTER.md — CI Gates & Waivers

## Merge-Blocking Gates

All gates must pass to merge. No exceptions.

| Gate | CI Job | What It Checks |
|------|--------|----------------|
| 1 | `validate` | Python syntax, YAML validation |
| 2 | `lint-ruff` | `ruff check .` — lint errors |
| 3 | `lint-format` | `ruff format --check .` — formatting |
| 4 | `test` | pytest (coverage >= 60%) |
| 5 | `compliance-chassis` | FastAPI import isolation (C-01) |
| 6 | `compliance-terminology` | No `print()`, `Optional[]`, `List[]`, `Dict[]` |
| 7 | `semgrep` | `.semgrep/` security rules |
| 8 | `contracts` | `verify_contracts.py` — L9_META headers |

---

## Non-Blocking Jobs (Waivers)

These jobs run but failures do not block merge.

| Job | Waiver ID | Reason |
|-----|-----------|--------|
| `lint-mypy` | WAIVER-001 | Progressive type annotation rollout |
| `security-pip-audit` | WAIVER-002 | Requires human triage for CVEs |
| `security-safety-check` | WAIVER-003 | Secondary to pip-audit |
| `security-bandit` | WAIVER-004 | Many acceptable B1xx findings |
| `coverage-codecov-upload` | WAIVER-005 | Network/token issue, not code quality |

---

## Agent Response to CI Failures

| Failed Job | Action |
|------------|--------|
| `validate` | Fix Python syntax or YAML first |
| `lint-ruff` | Run `make agent-fix`, re-push |
| `lint-format` | Run `make agent-fix`, re-push |
| `lint-mypy` | Log warning, do not block (WAIVER-001) |
| `test` | Fix failing tests, ensure coverage >= 60% |
| `compliance-chassis` | Remove FastAPI import from `engine/` |
| `compliance-terminology` | Replace banned patterns with compliant equivalents |
| `semgrep` | Read `.semgrep/` rules, fix violation |
| `security-*` | Log warning, do not block (waivers apply) |
| `contracts` | Fix L9_META header, run `make verify` |

---

## Quick Fix Commands

```bash
# Auto-fix lint and format issues
make agent-fix

# Run full gate sequence locally
make agent-check

# Verify contracts
make verify
```

---

## CI Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push, PR | Main pipeline (lint, test, compliance) |
| `compliance.yml` | PR | Chassis isolation, terminology |
| `l9-constitution-gate.yml` | PR | L9 contract verification |
| `l9-contract-control.yml` | PR | Select-gates based on diff |
| `pr-pipeline.yml` | PR | Full PR validation |
| `supply-chain.yml` | push | Dependency security (SBOM, Scorecard) |
| `codeql.yml` | push, schedule | CodeQL security analysis |
| `gitguardian.yml` | push | Secret detection |

---

## Coverage Requirements

- **Minimum**: 60% (enforced by `test` job)
- **Target**: 80%+ for engine modules
- **Exclusions**: None — all code counts

---

## Related Documents

- `AGENTS.md` — Full contract list (C-01 to C-20)
- `.github/workflows/` — CI workflow definitions
- `local_pr_pipeline/` — Local CI parity tooling
