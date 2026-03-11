.PHONY: help dev test lint build deploy review

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev:  ## Run locally with docker-compose
	docker compose up --build

test:  ## Run tests
	pytest tests/ -v --tb=short --cov=app

lint:  ## Lint and format check
	ruff check app/ tests/ scripts/
	ruff format --check app/ tests/ scripts/

build:  ## Build Docker image
	docker build -t enrichment-api:local .

deploy:  ## Deploy to K8s (usage: make deploy ENV=production METHOD=kustomize)
	./deploy/scripts/deploy.sh $(ENV) $(METHOD)

rollback:  ## Rollback (usage: make rollback ENV=production METHOD=kustomize)
	./deploy/scripts/rollback.sh $(ENV) $(METHOD)

validate:  ## Validate all K8s manifests
	./deploy/scripts/validate.sh

secrets:  ## Generate secrets (usage: make secrets NS=enrichment PPLX_KEY=pplx-xxx)
	./deploy/scripts/generate-secrets.sh $(NS) $(PPLX_KEY)

review:  ## AI code review on staged changes
	python scripts/ai_review.py --mode staged

review-all:  ## AI review on all Python files
	python scripts/ai_review.py --mode files --paths $$(find app/ -name '*.py')

install-hooks:  ## Install git pre-commit hook
	cp scripts/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hook installed"
