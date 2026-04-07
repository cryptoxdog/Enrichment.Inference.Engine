# Local PR pipeline (isolated tooling)

Everything in **`local_pr_pipeline/`** is **developer-only** automation: run the same kinds of checks as GitHub Actions locally (`make pr`). It is **not** application runtime code, not imported by `app/`, and not part of the production deploy surface.

| Artifact | Role |
|----------|------|
| `pr_pipeline.sh` | Orchestrates validate → lint → … → docs |
| `docker-compose.pr.yml` | Ephemeral Postgres + Redis for the test phase |
| `check_compliance_terminology.py` | Portable terminology guard |
| `compliance_kb_validate.py` | KB YAML checks (aligned with `compliance.yml`) |
| `docs_consistency_local.sh` | Docs-consistency steps |
| `docs_link_check_local.py` | Markdown link check |
| `run_pr_select_gates.py` | Runs commands from L9 `select-gates` JSON |
| `contract_bound_local.py` | Optional contract-bound diff check |

Repo scripts such as `scripts/verify_node_constitution.py` and `scripts/l9_contract_control.py` remain under `scripts/`; this folder only holds the **local pipeline bundle**.

Entry point: **`make pr`** / **`make pr-quick`** (see [`readme/CICD_PIPELINE.md`](../readme/CICD_PIPELINE.md)).
