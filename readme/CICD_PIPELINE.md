# CI/CD Pipeline — Enrichment.Inference.Engine

**Version:** 1.1.0
**Date:** 2026-03-30
**Status:** Active
**Sibling Parity:** Cognitive.Engine.Graphs

---

## Overview

This document describes the production-grade CI/CD pipeline for the Enrichment.Inference.Engine. The pipeline enforces code quality, security, architecture compliance, and deployment automation as a unified governance layer. It is designed for **sibling uniformity** with the Cognitive.Engine.Graphs pipeline so that all L9 constellation nodes share identical engineering standards.

---

## Pipeline Architecture

### Workflow Summary

| Workflow | Trigger | Purpose | Blocking |
|----------|---------|---------|----------|
| `ci.yml` | Push, PR | Main pipeline (validate, lint, semgrep, test, security, SBOM, scorecard) | Yes |
| `compliance.yml` | PR (Python changes) | Architecture compliance (terminology, chassis isolation, KB schema, L9 contracts) | Yes |
| `supply-chain.yml` | PR, push, weekly | License compliance, dependency review | Partial |
| `codeql.yml` | PR, push, weekly | GitHub CodeQL semantic analysis | No |
| `docker-build.yml` | Push to main, tags | Build, scan, sign Docker images | No |
| `k8s-deploy.yml` | Manual dispatch | Helm-based K8s deployment with auto-rollback | No |
| `pr-review-enforcement.yml` | PR opened/sync | PR size limits and review policy | Yes (>1000 lines) |
| `refactoring-validation.yml` | refactor/* branches | Hard gate for refactoring PRs | Yes |
| `release-drafter.yml` | Push to main | Auto-draft release notes | No |
| `docs-sync.yml` | Docs changes | Validate documentation links | No |
| `coderabbit-notify.yml` | PR review | CodeRabbit review notifications | No |

### CI Pipeline Phases (ci.yml)

```
validate → lint → semgrep → test → security → sbom → scorecard → ci-gate
    │         │       │        │        │        │        │          │
    │         │       │        │        │        │        │          └─ Fan-in: PASS/FAIL
    │         │       │        │        │        │        └─ OpenSSF Scorecard
    │         │       │        │        │        └─ SPDX SBOM generation
    │         │       │        │        └─ Gitleaks + pip-audit + Safety + Bandit
    │         │       │        └─ pytest with coverage (Postgres + Redis services)
    │         │       └─ Semgrep policy rules (.semgrep/)
    │         └─ Ruff lint + format + MyPy type check
    └─ Python syntax + YAML validation + KB schema
```

**Note:** `ci-quality.yml` and `test.yml` were consolidated into `ci.yml` to eliminate redundant test runs.

---

## Pre-Commit Hooks

Local enforcement runs before code reaches the remote pipeline:

| Hook | Stage | Purpose |
|------|-------|---------|
| `ruff` | commit | Auto-fix lint issues |
| `ruff-format` | commit | Auto-format code |
| `gitleaks` | commit | Block committed secrets |
| `mypy` | commit | Type checking on `app/` |
| `pytest-unit` | commit | Fast unit test subset |
| `block-fastapi-in-engine` | commit | Chassis isolation enforcement |
| `l9-contract-audit` | commit | L9 contract compliance |
| `l9-contract-verify` | push | L9 contract file verification |
| `terminology-guard` | commit | Canonical term enforcement |
| `check-yaml` | commit | YAML validation |
| `end-of-file-fixer` | commit | POSIX compliance |
| `trailing-whitespace` | commit | Clean whitespace |
| `check-added-large-files` | commit | Block files >1MB |

### Installation

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

---

## Configuration

All workflows use **zero-config defaults** that work immediately. Customize via GitHub Repository Variables (Settings → Variables → Actions). See `.github/env.template` for the full list.

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHON_VERSION` | `3.12` | Python version for CI |
| `SOURCE_DIR` | `app` | Source directory for coverage and type checks |
| `COVERAGE_THRESHOLD` | `60` | Minimum test coverage percentage |
| `PR_WARN_LINES` | `300` | PR size warning threshold |
| `PR_BLOCK_LINES` | `1000` | PR size blocking threshold |

### Required Secrets

| Secret | Required For |
|--------|-------------|
| `KUBECONFIG` | K8s deployment |
| `SLACK_WEBHOOK_URL` | Deployment notifications |
| `CODECOV_TOKEN` | Coverage upload |

---

## Sibling Parity

This pipeline is structurally identical to `Cognitive.Engine.Graphs` with engine-specific adaptations:

| Aspect | Graph Engine | Enrichment Engine |
|--------|-------------|-------------------|
| Source directory | `engine/` | `app/` |
| Compliance checks | Cypher injection guard | Chassis isolation guard |
| KB validation | N/A | YAML rule schema validation |
| L9_META engine tag | `graph` | `enrichment` |
| Tool versions | Shared via `requirements-ci.txt` | Same pinned versions |

---

## Deployment

### Kubernetes (Production)

```bash
# Trigger via GitHub Actions UI
# Workflow: Kubernetes Deployment
# Select environment: staging or production
```

### Docker Build

Docker images are automatically built on push to `main` and tagged releases. Images are pushed to `ghcr.io` with multi-tag strategy (branch, SHA, semver, latest).

---

## Troubleshooting

**CI Gate fails on lint:** Run `ruff check . --fix && ruff format .` locally before pushing.

**Coverage below threshold:** Add tests for uncovered modules. Check `pytest --cov=app --cov-report=term-missing` locally.

**Pre-commit hooks fail:** Run `pre-commit run --all-files` to see all issues. Fix and re-commit.

**Architecture compliance fails:** Check for FastAPI imports outside `app/api/` and `app/main.py`. Engine modules must remain chassis-agnostic.
