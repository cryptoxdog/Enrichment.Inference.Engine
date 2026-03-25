# Enrichment.Inference.Engine — Gap Analysis

## Current Repository State

The [Enrichment.Inference.Engine](https://github.com/cryptoxdog/Enrichment.Inference.Engine) repository contains **~55 files** across a well-structured directory layout implementing the Layer 2 ENRICH service . The codebase covers the core convergence loop, enrichment orchestration, domain KB injection, and initial deployment infrastructure. Here is what exists today:

| Layer | Directory | Files | Covers |
|-------|-----------|-------|--------|
| API Surface | `app/api/v1/` | `converge.py` | Convergence loop endpoints only  |
| Core Config | `app/core/` | `auth.py`, `config.py`, `logging_config.py` | API key auth, settings, structlog  |
| Engines | `app/engines/` | 8 files + `convergence/` (9 files) | Convergence controller, schema discovery, inference bridge, graph sync, meta-prompt planner, chassis contract  |
| Health | `app/health/` | 5 files | Health assessor, field analyzer, triggers, models, API  |
| Models | `app/models/` | 3 files | Field confidence, loop schemas, API schemas  |
| Services | `app/services/` | 7 files | Consensus engine, circuit breaker, KB resolver, Perplexity client, prompt builder, uncertainty engine, validation engine  |
| Middleware | `app/middleware/` | `rate_limiter.py` | Simple rate limiting  |
| Domain KB | `kb/` | `plastics_recycling.yaml` | Single vertical KB  |
| Deploy | `deploy/` | Helm chart, ArgoCD app, Kustomize, scripts | K8s deployment pipeline  |
| Tests | `tests/` | `test_api.py` | Single API test file  |
| Entrypoint | `app/main.py` | FastAPI v2.2 app | `/enrich`, `/enrich/batch`, `/health`  |

***

## What's Built and Working

### Core Enrichment Loop (Layer 2)
The multi-pass convergence loop is implemented across `convergence_controller.py`, `loop_state.py`, and the convergence sub-package . This includes:

- **Schema Discovery** → `schema_discovery.py` + `schema_proposer.py` — discovers fields the customer didn't know they needed
- **Multi-Variation LLM Consensus** → `consensus_engine.py` with confidence scoring
- **Domain KB Injection** → `kb_resolver.py` + `domain_yaml_reader.py` + plastics recycling YAML
- **Inference Bridge** → Deterministic YAML rules firing in dependency order with topological sort, producing `material_grade`, `facility_tier`, etc.
- **Cost Tracking** → `cost_tracker.py` tracks tokens/cost per pass
- **Graph Sync** → `graph_sync_client.py` pushes enriched entities to Neo4j

### Chassis Contract (PacketEnvelope)
`chassis_contract.py` implements `inflate_ingress`, `deflate_egress`, and `delegate_to_node` — the full PacketEnvelope protocol with content_hash verification, hop_trace, delegation_chain, lineage tracking, and governance fields .

### Health Monitoring
Full health subsystem with `health_assessor.py` (20KB), `health_field_analyzer.py`, `health_triggers.py`, and API surface .

***

## Gap Analysis: What's Missing

### CRITICAL — Downstream Services Not Yet Implemented

These are the Layer 3 and downstream constellation nodes that consume ENRICH + GRAPH outputs. None exist in this repo yet:

| Service | Purpose | Depends On | Status |
|---------|---------|------------|--------|
| **SCORE** | Multi-dimensional scoring (fit, intent, engagement, readiness, graph_affinity) | ENRICH field data + GRAPH affinity | ❌ Not started |
| **ROUTE** | Lead/deal routing to reps based on scores + territory + capacity | SCORE outputs + CRM | ❌ Not started |
| **FORECAST** | Pipeline/revenue forecasting from enriched + scored data | SCORE + HEALTH time series | ❌ Not started |
| **SIGNAL** | Engagement/intent signal detection and aggregation | CRM events + web activity → feeds SCORE | ❌ Not started |
| **HANDOFF** | Orchestrates automated handoff sequences when thresholds hit | SCORE tier transitions + ROUTE | ❌ Not started |

### HIGH — Missing Application Code Within ENRICH

| Gap | File(s) Needed | Why |
|-----|---------------|-----|
| **PostgreSQL/pgvector persistence layer** | `app/services/pg_store.py`, `app/services/pg_models.py` | No database persistence exists — enrichment results, convergence state, field confidence history all need PostgreSQL + pgvector for embedding storage. The arch spec says "PostgreSQL/pgvector as memory substrate." |
| **Enrichment result store** | `app/services/result_store.py` | No durable storage for completed enrichment records. Everything is in-memory or returned via API response. Batch re-enrichment, decay, and SCORE integration all need historical records. |
| **Multi-provider LLM client** | `app/services/openai_client.py`, `app/services/anthropic_client.py` | Only `perplexity_client.py` exists . Multi-variation consensus requires multiple LLM providers to avoid single-provider bias. |
| **Field provenance chain** | `app/models/provenance.py` | The confidence model exists (`field_confidence.py` ) but there's no explicit provenance chain model tracking which enrichment pass / which LLM / which KB rule produced each field value. |
| **Webhook / event emitter** | `app/services/event_emitter.py` | No mechanism to emit events when enrichment completes, scores change, or tiers transition. Downstream services (SIGNAL, SCORE, ROUTE) need this. |
| **Async task queue** | `app/services/task_queue.py` | Batch enrichment runs synchronously in `enrichment_orchestrator.py` . Production needs Celery/ARQ/Redis Streams for async processing. |
| **PacketEnvelope router** | `app/engines/packet_router.py` | `chassis_contract.py` builds envelopes but there's no routing logic to dispatch them to other constellation nodes . `delegate_to_node` creates the packet but doesn't send it. |

### HIGH — Missing API Endpoints

| Endpoint | Purpose | Current State |
|----------|---------|---------------|
| `POST /api/v1/discover` | Trigger schema discovery independently | Not exposed — `schema_discovery.py` exists but has no API route  |
| `POST /api/v1/infer` | Run inference rules independently | `inference_bridge.py` exists but no API route  |
| `GET /api/v1/profile/{domain}` | Get/set enrichment profiles per domain | `enrichment_profile.py` exists but no API route  |
| `GET /api/v1/convergence/{run_id}` | Get convergence run status/history | `loop_state.py` exists but no API route  |
| `POST /api/v1/rescore` | Trigger re-scoring after enrichment | No SCORE service exists |
| `GET /api/v1/fields/{entity_id}` | Get field-level confidence + provenance | Data model exists but no read API |

### MEDIUM — Testing Gaps

| Gap | Details |
|-----|---------|
| **Only 1 test file** | `test_api.py` at 6.4KB covers API endpoints only  |
| **No engine tests** | Zero tests for `convergence_controller.py`, `inference_bridge.py`, `schema_discovery.py`, `consensus_engine.py` |
| **No integration tests** | No end-to-end tests running the full convergence loop |
| **No KB validation tests** | No tests verifying YAML rule loading and firing |
| **No conftest.py** | No shared fixtures, mock factories, or test utilities |

Files needed:
- `tests/conftest.py` — shared fixtures
- `tests/test_convergence_controller.py`
- `tests/test_inference_bridge.py`
- `tests/test_consensus_engine.py`
- `tests/test_schema_discovery.py`
- `tests/test_kb_resolver.py`
- `tests/test_chassis_contract.py`
- `tests/test_health.py`
- `tests/integration/test_convergence_loop.py`

### MEDIUM — Infrastructure Gaps

| Gap | Details |
|-----|---------|
| **No CI/CD pipeline** | No `.github/workflows/` directory — no automated testing, linting, or deployment |
| **No Terraform** | Arch spec says "Terraform for IaC" but no `terraform/` directory exists |
| **No database migrations** | No Alembic/migration files for PostgreSQL schema |
| **No observability config** | `logging_config.py` exists  but no OpenTelemetry traces, Prometheus metrics export, or Grafana dashboards |
| **No README.md** | Repository has no README explaining setup, architecture, or development workflow |
| **Missing Kustomize content** | `deploy/kustomize/base/` and `deploy/kustomize/overlays/` directories exist but contents not verified  |

### LOW — Domain KB Expansion

| Gap | Details |
|-----|---------|
| **Single domain KB** | Only `plastics_recycling.yaml` exists . No mechanism for customers to add their own domain KBs via API or config. |
| **No KB versioning** | YAML files have no version tracking or migration strategy |
| **No KB validation schema** | No JSON Schema or Pydantic model validating KB YAML structure before loading |

***

## Build Priority Matrix

### Phase 1 — Foundation (Blocks Everything Else)
1. `app/services/pg_store.py` — PostgreSQL persistence layer
2. `app/services/result_store.py` — Durable enrichment record storage
3. `app/services/event_emitter.py` — Event bus for downstream services
4. `app/services/task_queue.py` — Async enrichment processing
5. `app/engines/packet_router.py` — PacketEnvelope dispatch to constellation nodes
6. `tests/conftest.py` + engine unit tests
7. `.github/workflows/ci.yml` — CI pipeline

### Phase 2 — SCORE Service (Next Constellation Node)
8. `score_models.py` — Multi-dimensional scoring types
9. `score_engine.py` — 5-dimension scoring engine with ICP matching
10. `score_decay.py` — Temporal decay with per-dimension half-lives
11. `score_explainer.py` — Human-readable score explanations
12. `score_api.py` — FastAPI endpoints for score/explain/decay
13. `score_icp_plastics.py` — Plastics recycling domain ICP

### Phase 3 — Signal + Route
14. SIGNAL service — engagement/intent signal detection
15. ROUTE service — territory-aware routing from scores

### Phase 4 — Forecast + Handoff
16. FORECAST service — pipeline forecasting from scored data
17. HANDOFF service — automated handoff orchestration

***

## File Count Summary

| Category | Existing | Missing (Estimated) |
|----------|----------|-------------------|
| Core ENRICH application | ~40 files | ~10 files |
| SCORE service | 0 files | ~6 files |
| SIGNAL service | 0 files | ~5 files |
| ROUTE service | 0 files | ~5 files |
| FORECAST service | 0 files | ~5 files |
| HANDOFF service | 0 files | ~4 files |
| Tests | 1 file | ~12 files |
| Infrastructure (CI/CD, Terraform, migrations) | 0 files | ~8 files |
| Documentation | 0 files | ~3 files (README, CONTRIBUTING, API docs) |
| **Total** | **~55 files** | **~58 files** |

The repo is roughly 50% complete for the full ENRICH service in isolation, and about 25% complete for the full ENRICH + downstream constellation stack. The critical path runs through PostgreSQL persistence → event emitter → SCORE service, since everything downstream of ENRICH depends on durable enrichment records with provenance chains.
