.PHONY: setup dev dev-build dev-down dev-clean test test-unit test-integration test-compliance test-ci test-contracts test-all test-watch lint lint-fix audit audit-strict audit-json verify agent-check agent-fix agent-full build prod prod-build prod-down prod-logs deploy clean pr pr-validate pr-lint pr-semgrep pr-test pr-security pr-compliance pr-l9 pr-docs pr-quick pr-services-up pr-services-down

IMAGE_NAME ?= enrichment-api
SERVICE_NAME ?= enrichment-api
COMPOSE_FILE ?= docker-compose.prod.yml
COVERAGE_MIN ?= 60

# ============================================================
# SETUP
# ============================================================
setup:
	pip install -e ".[dev]"
	pre-commit install

# ============================================================
# TESTING — TIERED
# ============================================================
test:  ## Quick: unit tests only
	pytest tests/ -v --tb=short -x

test-unit:  ## Unit tests only
	pytest tests/unit/ -v --tb=short

test-integration:  ## Integration tests (requires services)
	pytest tests/integration/ -v --tb=short -m integration

test-compliance:  ## Architecture compliance tests
	pytest tests/compliance/ -v --tb=short

test-ci:  ## CI-level tests (contract enforcement, loader tests)
	pytest tests/ci/ -v --tb=short

test-contracts:  ## Repository contract call enforcement only
	pytest tests/ci/test_repository_contract_calls.py -v --tb=short

test-all:  ## Full test suite with coverage
	ruff check .
	ruff format --check .
	mypy app
	pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=$(COVERAGE_MIN)

test-watch:  ## Watch mode for unit tests
	pytest-watch tests/unit/ -- -v --tb=short

# ============================================================
# QUALITY — LINT + TYPE CHECK
# ============================================================
lint:  ## Lint + format check + type check
	ruff check .
	ruff format --check .
	mypy app

lint-fix:  ## Auto-fix lint and format issues
	ruff check . --fix
	ruff format .

# ============================================================
# AUDIT — 27-RULE ENGINE
# ============================================================
audit:  ## Run 27-rule audit engine (informational)
	python tools/audit_engine.py

audit-strict:  ## Run 27-rule audit engine (fail on CRITICAL/HIGH)
	python tools/audit_engine.py --strict

audit-json:  ## Run 27-rule audit engine (JSON output)
	python tools/audit_engine.py --json

# ============================================================
# CONTRACT VERIFICATION
# ============================================================
verify:  ## Verify contract manifest integrity
	python tools/verify_contracts.py

# ============================================================
# AGENT WORKFLOW — THE UNIVERSAL GATES
# ============================================================
agent-check:  ## THE universal gate. Agents run this before every commit.
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  L9 Agent Check — Enrichment.Inference.Engine ║"
	@echo "╚══════════════════════════════════════════════╝"
	@echo ""
	@echo "=== [1/7] LINT ===" && ruff check .
	@echo "=== [2/7] FORMAT ===" && ruff format --check .
	@echo "=== [3/7] TYPES ===" && mypy app
	@echo "=== [4/7] UNIT TESTS ===" && pytest tests/unit/ tests/compliance/ -v --tb=short -x
	@echo "=== [5/7] CI TESTS ===" && pytest tests/ci/ -v --tb=short -x
	@echo "=== [6/7] AUDIT ===" && python tools/audit_engine.py --strict
	@echo "=== [7/7] CONTRACTS ===" && python tools/verify_contracts.py
	@echo ""
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  ALL 7 GATES PASSED ✓                         ║"
	@echo "╚══════════════════════════════════════════════╝"

agent-fix:  ## Auto-fix what can be fixed
	ruff check . --fix
	ruff format .

agent-full:  ## Full agent workflow: fix → check → coverage
	$(MAKE) agent-fix
	$(MAKE) agent-check
	pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

# ============================================================
# PR PIPELINE — local parity with GitHub CI + L9 + docs
# See: readme/CICD_PIPELINE.md, local_pr_pipeline/pr_pipeline.sh
# Env: ORDER=gate|failfast, COVERAGE_THRESHOLD, PR_MYPY_STRICT, PR_SKIP_SEMGREP,
#      PR_SKIP_INTEGRATION, PR_L9_MINIMAL, PR_SKIP_L9, PR_SKIP_GITLEAKS, PR_SECURITY_STRICT
# PYTHON: override to pin interpreter (default: .venv/bin/python if present, else python3)
# ============================================================
PR_PYTHON ?= $(shell if [ -x "$(CURDIR)/.venv/bin/python" ]; then printf '%s' "$(CURDIR)/.venv/bin/python"; else command -v python3; fi)

pr:  ## Full local PR gate (validate → … → docs). Requires Docker for test phase; gitleaks for security.
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh all

pr-validate:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh validate

pr-lint:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh lint

pr-semgrep:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh semgrep

pr-test:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh test

pr-security:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh security

pr-compliance:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh compliance

pr-l9:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh l9

pr-docs:
	PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh docs

pr-quick:  ## Skips Docker test + select-gates runner; still runs lint through docs phases in gate order
	PR_SKIP_INTEGRATION=1 PR_L9_MINIMAL=1 PYTHON=$(PR_PYTHON) bash local_pr_pipeline/pr_pipeline.sh all

pr-services-up:
	docker compose -f local_pr_pipeline/docker-compose.pr.yml -p enrich_pr up -d

pr-services-down:
	docker compose -f local_pr_pipeline/docker-compose.pr.yml -p enrich_pr down -v

# ============================================================
# BUILD / DEPLOY
# ============================================================
build:
	docker build -t $(IMAGE_NAME):latest .

# ============================================================
# DOCKER — LOCAL & PRODUCTION
# ============================================================
dev:
	docker compose up -d

dev-build:
	docker compose up -d --build

dev-down:
	docker compose down

dev-clean:
	docker compose down -v --remove-orphans

prod:
	docker compose -f $(COMPOSE_FILE) up -d

prod-build:
	docker compose -f $(COMPOSE_FILE) up -d --build

prod-down:
	docker compose -f $(COMPOSE_FILE) down

prod-logs:
	docker compose -f $(COMPOSE_FILE) logs -f $(SERVICE_NAME)

deploy:
	./scripts/deploy.sh $(ENV)

# ============================================================
# CLEANUP
# ============================================================
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/
