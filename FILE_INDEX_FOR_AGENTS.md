# FILE_INDEX_FOR_AGENTS.md

## Purpose
Fast lookup index for AI agents to find relevant files by category/function.

## Scope
Quick reference for file locations, no detailed content

## File Categories

### Agent Guidance (AI-Specific)
- `AGENT.md` — Universal AI agent contracts (this pack)
- `CLAUDE.md` — Claude-specific guidance (this pack)
- `.cursorrules` — 20 architectural contracts (26KB)
- `AGENTS.md` — Existing agent guidance (2.8KB)

### Architecture & Invariants
- `ARCHITECTURE.md` — System architecture overview (5.3KB, existing)
- `INVARIANTS.md` — Immutable architectural rules (this pack)
- `GUARDRAILS.md` — Safety guardrails (2.4KB)

### Configuration
- `pyproject.toml` — Python dependencies, ruff/mypy/pytest config
- `.env.example` — Environment variable template with documentation
- `.env.template` — Alternative env template
- `.env.required` — Required variables (30 bytes, minimal)

### CI/CD
- `.github/workflows/ci.yml` — Main CI pipeline (17.2KB, 7 jobs)
- `.github/workflows/compliance.yml` — Architecture compliance (7.4KB)
- `.github/workflows/codeql.yml` — CodeQL security scanning
- `.github/workflows/docker-build.yml` — Docker image build
- `.github/workflows/supply-chain.yml` — Supply chain security
- `.pre-commit-config.yaml` — Pre-commit hooks (5.7KB)

### Documentation (This Pack)
- `REPO_MAP.md` — Repository structure map
- `EXECUTION_FLOWS.md` — Runtime execution paths
- `DEPENDENCY_SURFACE.md` — External dependencies inventory
- `CONFIG_ENV_CONTRACT.md` — Environment variables contract
- `CI_WHITELIST_REGISTER.md` — CI waivers and non-blocking checks
- `AI_AGENT_REVIEW_CHECKLIST.md` — PR review checklist
- `FILE_INDEX_FOR_AGENTS.md` — This file
- `ADR-001-ci-mypy-warnings-non-blocking.md` — ADR for mypy waiver

### Tests
- `tests/conftest.py` — Shared pytest fixtures (4.0KB)
- `tests/unit/` — Unit tests (fast, isolated)
- `tests/integration/` — Integration tests (requires services)
- `tests/compliance/` — Architecture compliance tests
- `tests/ci/` — Repository contract enforcement tests

### Application Code
- `app/main.py` — FastAPI entrypoint (5.4KB)
- `app/api/` — HTTP routes (FastAPI allowed here)
- `app/core/` — Core application logic
- `app/engines/` — Enrichment engines
- `app/models/` — Pydantic models

### Engine Code (Chassis-Agnostic)
- `engine/handlers.py` — ONLY chassis bridge file
- `engine/config/loader.py` — Domain spec loader
- `engine/config/schema.py` — Domain spec Pydantic schemas
- `engine/gates/compiler.py` — Gate compilation to Cypher
- `engine/utils/security.py` — sanitize_label() and security utils

### Build & Deployment
- `Dockerfile` — Development Docker image
- `Dockerfile.prod` — Production Docker image
- `docker-compose.yml` — Local development stack
- `docker-compose.prod.yml` — Production stack
- `Makefile` — Task runner with agent-check command

## Quick Lookups

### "Where do I find...?"

**...environment variables?**
→ `.env.example` (template), `CONFIG_ENV_CONTRACT.md` (documentation)

**...CI configuration?**
→ `.github/workflows/ci.yml` (main), `.github/workflows/compliance.yml` (architecture)

**...architectural contracts?**
→ `.cursorrules` (20 contracts), `INVARIANTS.md` (20 invariants)

**...agent rules?**
→ `AGENT.md` (universal), `CLAUDE.md` (Claude-specific), `.cursorrules`

**...dependency list?**
→ `pyproject.toml` (Python deps), `DEPENDENCY_SURFACE.md` (documentation)

**...test structure?**
→ `tests/` (all tests), `TESTING.md` (requirements), `tests/conftest.py` (fixtures)

**...Makefile commands?**
→ `Makefile` (all commands), `AGENT.md` (agent-check details)

**...HTTP endpoints?**
→ `app/main.py` (FastAPI app), `app/api/` (route modules)

**...handler signature?**
→ `.cursorrules` CONTRACT 2, `engine/handlers.py` (examples)

**...Cypher safety?**
→ `engine/utils/security.py` (sanitize_label), `.cursorrules` CONTRACT 9

**...domain specs?**
→ `domains/` (YAML files), `engine/config/schema.py` (Pydantic schemas)

### "What file enforces...?"

**...contract compliance?**
→ `.github/workflows/compliance.yml` (Terminology Guard, Chassis Isolation, KB Schema)

**...banned patterns?**
→ `.cursorrules` (contract scanner rules), `tools/contract_scanner.py` (implementation, if exists)

**...test coverage threshold?**
→ `.github/workflows/ci.yml` (COVERAGE_THRESHOLD=60), `pyproject.toml` ([tool.coverage.report] fail_under=60)

**...type checking?**
→ `.github/workflows/ci.yml` (mypy app), `pyproject.toml` ([tool.mypy])

**...code formatting?**
→ `.github/workflows/ci.yml` (ruff format --check), `pyproject.toml` ([tool.ruff])

**...pre-commit hooks?**
→ `.pre-commit-config.yaml`

### "How do I...?"

**...run full validation?**
→ `make agent-check` (7 gates)

**...auto-fix lint issues?**
→ `make agent-fix` (ruff check --fix + ruff format)

**...run unit tests?**
→ `make test-unit` or `pytest tests/unit/ -v`

**...run integration tests?**
→ `make test-integration` or `pytest tests/integration/ -m integration`

**...generate coverage report?**
→ `make test-all` (includes coverage with HTML report)

**...start dev environment?**
→ `make dev` (docker-compose up)

**...add L9_META header?**
→ `python tools/l9_meta_injector.py` (tool may not exist, manual annotation required)

## File Modification Rules

**NEVER modify:**
- `Dockerfile`, `Dockerfile.prod` (l9-template managed)
- `docker-compose.yml`, `docker-compose.prod.yml` (l9-template managed)
- `.github/workflows/*.yml` (l9-template managed, except for engine-specific vars)

**ALWAYS modify with care:**
- `pyproject.toml` (affects all developers, CI)
- `.cursorrules` (affects AI agents, contracts)
- `Makefile` (affects developer workflow)

**Safe to modify:**
- `app/` (application code)
- `engine/` (engine code, respect chassis boundary)
- `tests/` (test code)
- `docs/` (documentation)
- `.env.example` (environment variable template)
