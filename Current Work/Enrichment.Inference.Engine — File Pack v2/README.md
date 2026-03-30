# L9 Enrichment.Inference.Engine — File Pack v2

## What's in this pack

This is the **continuation file pack** — files that were *not* in Pack v1.
All 12 files from the build plan are implemented here, plus supporting infrastructure.

### New Files

| Layer | Files |
|-------|-------|
| **Models** | `field_confidence.py`, `loop_schemas.py`, `provenance.py` |
| **Inference Engine** | `rule_loader.py`, `rule_engine.py`, `grade_engine.py` |
| **Convergence** | `cost_tracker.py`, `pass_telemetry.py`, `loop_state.py`, `schema_proposer.py` |
| **Services** | `crm_field_scanner.py`, `enrichment_profile.py`, `pg_store.py`, `pg_models.py`, `event_emitter.py` |
| **Infrastructure** | `packet_router.py`, `dependencies.py`, `config.py`, `auth.py` |
| **API** | `converge.py` (full endpoint suite) |
| **Persistence** | Alembic migration `001_initial_schema.py`, `pg_models.py` |
| **Score Scaffold** | `score/scorer.py` (ENRICH-derived readiness scoring) |
| **CI/CD** | `.github/workflows/ci.yml` — lint, unit tests, integration tests, security scan, Docker build |
| **Codegen Templates** | 7 Jinja2 templates unblocking all domain code generation |
| **Tests** | 5 unit test files, 2 integration test files, load test harness |
| **Domain Spec** | `domains/plasticos/spec.yaml` — canonical plasticos spec |
| **Fixtures** | `tests/fixtures/plasticos_seed.cypher` — deterministic test graph |

## CI Requirements

The CI pipeline requires these services (all provided as GitHub Actions services):
- Neo4j 5 on `localhost:7687`
- PostgreSQL 16 on `localhost:5432`
- Redis 7 on `localhost:6379`

Unit tests run without any services (fully mocked).

## Quick Start

```bash
cp .env.example .env          # Fill in your API keys
docker-compose up -d          # Start local stack (Neo4j + Postgres + Redis)
alembic upgrade head           # Run DB migrations
uvicorn app.main:app --reload  # Start API
```

## Passing CI

```bash
poetry install
poetry run pytest tests/unit/ -v         # Must pass before merge
poetry run ruff check app/ tests/        # Must pass before merge
poetry run mypy app/ --ignore-missing-imports
```
