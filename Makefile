.PHONY: setup dev dev-build dev-down dev-clean test test-unit test-integration test-compliance test-all test-watch lint audit agent-check agent-fix build prod prod-build prod-down prod-logs deploy

IMAGE_NAME ?= enrichment-api
SERVICE_NAME ?= enrichment-api
COMPOSE_FILE ?= docker-compose.prod.yml

# ============================================================
# SETUP
# ============================================================
setup:
	pip install -e ".[dev]"
	pre-commit install

# ============================================================
# TESTING
# ============================================================
test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short -m integration

test-compliance:
	pytest tests/compliance/ -v --tb=short

test-all:
	ruff check .
	ruff format --check .
	mypy app
	pytest tests/ -v --tb=short

test-watch:
	pytest-watch tests/unit/ -- -v --tb=short

# ============================================================
# QUALITY
# ============================================================
lint:
	ruff check .
	ruff format --check .
	mypy app

audit:
	ruff check .
	mypy app

# ============================================================
# AGENT WORKFLOW
# ============================================================
agent-check:  ## THE universal gate. Agents run this before every commit.
	@echo "=== LINT ===" && ruff check .
	@echo "=== FORMAT ===" && ruff format --check .
	@echo "=== TYPES ===" && mypy app
	@echo "=== TESTS ===" && pytest tests/ -v --tb=short
	@echo "=== ALL CHECKS PASSED ==="

agent-fix:
	ruff check . --fix
	ruff format .

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
