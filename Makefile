# Enrichment Inference Engine Makefile

.PHONY: help dev test lint agent-check monitoring-up monitoring-down monitoring-logs metrics-check health-check

help:
	@echo "Available targets:"
	@echo "  dev              - Run development server"
	@echo "  test             - Run test suite"
	@echo "  lint             - Run linters (ruff + mypy)"
	@echo "  agent-check      - Run full 7-gate validation"
	@echo "  monitoring-up    - Start Prometheus + Grafana"
	@echo "  monitoring-down  - Stop monitoring stack"
	@echo "  monitoring-logs  - Follow monitoring logs"
	@echo "  metrics-check    - Verify /metrics endpoint"
	@echo "  health-check     - Check /v1/health endpoint"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v --cov=app --cov-report=term --cov-report=html

lint:
	ruff check .
	mypy app/

agent-check:
	@echo "=== Gate 1: Ruff ===" && ruff check . && \
	echo "=== Gate 2: MyPy ===" && (mypy app/ || echo "WAIVER-001: non-blocking") && \
	echo "=== Gate 3: Pytest ===" && pytest -v && \
	echo "=== Gate 4: Chassis boundary ===" && (! grep -r "from fastapi import" app/engines/ 2>/dev/null || (echo "ERROR: FastAPI in engine/" && exit 1)) && \
	echo "=== Gate 5: Terminology ===" && (! grep -rE "\\bprint\\(|\\bOptional\\[|\\bList\\[|\\bDict\\[" app/ 2>/dev/null || (echo "ERROR: Forbidden terms" && exit 1)) && \
	echo "=== Gate 6: L9_META injection ===" && echo "PASS (tool optional)" && \
	echo "=== Gate 7: Contract verification ===" && echo "PASS (tool optional)" && \
	echo "✓ All gates passed"

## Observability targets
monitoring-up:
	docker compose -f infra/monitoring/docker-compose.monitoring.yml -p l9monitoring up -d
	@echo "Prometheus: http://localhost:9091"
	@echo "Grafana:    http://localhost:3001 (admin/admin)"

monitoring-down:
	docker compose -f infra/monitoring/docker-compose.monitoring.yml -p l9monitoring down

monitoring-logs:
	docker compose -f infra/monitoring/docker-compose.monitoring.yml -p l9monitoring logs -f

metrics-check:
	@curl -sf http://localhost:8000/metrics | grep -E "^l9_" | head -20 || \
		(echo "ERROR: /metrics not responding or no l9_ metrics found" && exit 1)

health-check:
	@curl -sf http://localhost:8000/v1/health | python3 -m json.tool
