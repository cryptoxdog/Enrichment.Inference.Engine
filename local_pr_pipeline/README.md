# Local PR Pipeline (isolated tooling)

Everything in **`local_pr_pipeline/`** is **developer-only** automation: run the same checks as GitHub Actions locally (`make pr`). It is **not** application runtime code, not imported by `app/`, and not part of the production deploy surface.

## GitHub ↔ Local Parity

| Local Command | GitHub Workflow | Description |
|---------------|-----------------|-------------|
| `make pr` | `.github/workflows/pr-pipeline.yml` | Full 8-phase gate |
| `make pr-quick` | Manual dispatch with skip flags | Minimal checks |

The **`pr-pipeline.yml`** workflow runs the same scripts from this folder in GitHub Actions, ensuring complete parity between local and CI environments.

## Artifacts

| File | Role |
|------|------|
| `pr_pipeline.sh` | Orchestrates validate → lint → semgrep → test → security → compliance → L9 → docs |
| `docker-compose.pr.yml` | Ephemeral Postgres + Redis for the test phase |
| `check_compliance_terminology.py` | Portable terminology guard (used by both local and GitHub) |
| `compliance_kb_validate.py` | KB YAML checks (aligned with `compliance.yml`) |
| `docs_consistency_local.sh` | Docs-consistency steps |
| `docs_link_check_local.py` | Markdown link check |
| `run_pr_select_gates.py` | Runs commands from L9 `select-gates` JSON |
| `contract_bound_local.py` | Optional contract-bound diff check |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PR_SKIP_INTEGRATION` | unset | Skip pytest with Postgres/Redis |
| `PR_SKIP_SEMGREP` | unset | Skip Semgrep policy checks |
| `PR_SKIP_L9` | unset | Skip L9 constitution/contract checks |
| `PR_L9_MINIMAL` | unset | Minimal L9 (no select-gates runner) |
| `PR_MYPY_STRICT` | unset | Fail on mypy errors (non-blocking by default) |
| `PR_SECURITY_STRICT` | unset | Fail on security warnings |
| `PR_SKIP_GITLEAKS` | unset | Skip Gitleaks secret detection |
| `ORDER` | `gate` | Phase execution order (`gate` or `failfast`) |
| `COVERAGE_THRESHOLD` | `60` | Minimum test coverage percentage |

## Usage

```bash
# Full pipeline (requires Docker for test phase, gitleaks for security)
make pr

# Quick pipeline (skip integration tests and full L9)
make pr-quick

# Individual phases
make pr-validate
make pr-lint
make pr-semgrep
make pr-test
make pr-security
make pr-compliance
make pr-l9
make pr-docs
```

Repo scripts such as `scripts/verify_node_constitution.py` and `scripts/l9_contract_control.py` remain under `scripts/`; this folder only holds the **local pipeline bundle**.

Entry point: **`make pr`** / **`make pr-quick`** (see [`readme/CICD_PIPELINE.md`](../readme/CICD_PIPELINE.md)).
