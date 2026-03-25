## /inspect Report: Deployment-pack

### Classification

| Attribute | Value |
|-----------|-------|
| **Type** | Standalone Microservice Deployment Kit |
| **Name** | Domain Enrichment API v2.2.0 |
| **Purpose** | Entity enrichment via Perplexity AI with KB context, consensus, and uncertainty |
| **Tier** | INFRA_TIER + UX_TIER (deployment manifests + FastAPI app) |
| **Status** | **EXTERNAL CODE** — Not part of L9 Engine |

---

### What You Have

This is a **complete, production-ready deployment package** for a standalone "Domain Enrichment API" microservice. It is **NOT** part of the Graph Cognitive Engine — it's a separate service that uses Perplexity AI for entity enrichment.

#### Structure (47 files)

```
Deployment-pack/
├── app/                          # FastAPI application
│   ├── main.py                   # Entrypoint: /api/v1/health, /api/v1/enrich
│   ├── pipeline.py               # Orchestrator: KB → prompts → Perplexity → consensus
│   └── __init__.py
├── tests/                        # pytest test suite
│   ├── conftest.py               # Fixtures (client, api_key)
│   ├── test_auth.py              # Auth tests
│   ├── test_health.py            # Health endpoint tests
│   ├── test_pipeline.py          # Pipeline tests with mocked Perplexity
│   └── fixtures/kb/              # KB test fixtures
├── scripts/
│   ├── ai_review.py              # AI code review via Perplexity (pre-commit/CI)
│   └── pre-commit                # Git hook
├── deploy/
│   ├── helm/enrichment-api/      # Helm chart (full)
│   │   ├── Chart.yaml            # v2.2.0
│   │   ├── values.yaml           # Production defaults
│   │   ├── values-dev.yaml       # Dev overrides
│   │   ├── values-staging.yaml   # Staging overrides
│   │   └── templates/            # K8s manifests (deployment, service, ingress, hpa, pdb, rbac, redis)
│   ├── kustomize/                # Kustomize alternative
│   │   ├── base/                 # Base manifests
│   │   └── overlays/             # dev, staging, production
│   ├── argocd/                   # ArgoCD Application manifest
│   └── scripts/                  # deploy.sh, rollback.sh, validate.sh, generate-secrets.sh
├── .github/workflows/
│   ├── ci.yml                    # Lint → Test → Build → Push to GHCR
│   └── ai-review.yml             # AI code review on PRs
├── Makefile                      # dev, test, lint, build, deploy, rollback, review
├── .env.example                  # Environment template
└── .dockerignore                 # Docker build exclusions
```

---

### Architecture Summary

| Component | Description |
|-----------|-------------|
| **FastAPI App** | `/api/v1/health` (health check), `/api/v1/enrich` (main endpoint) |
| **Pipeline** | KB resolve → prompt variations → fan-out to Perplexity → validate → consensus → uncertainty |
| **Circuit Breaker** | Protects Perplexity calls from cascading failures |
| **KB Resolver** | Loads domain knowledge base for context injection |
| **Consensus Engine** | Synthesizes multiple Perplexity responses |
| **Uncertainty Engine** | Applies confidence thresholds and flags |

---

### Deployment Options

| Method | Files | Command |
|--------|-------|---------|
| **Helm** | `deploy/helm/enrichment-api/` | `make deploy ENV=production METHOD=helm` |
| **Kustomize** | `deploy/kustomize/` | `make deploy ENV=production METHOD=kustomize` |
| **ArgoCD** | `deploy/argocd/enrichment-api-app.yaml` | Apply ArgoCD Application |
| **Local** | `docker-compose.yml` (missing) | `make dev` |

---

### Missing Files (Detected)

The pack references files that aren't present:

| Missing | Expected Location |
|---------|-------------------|
| `app/config.py` | Settings, `get_settings()` |
| `app/logging_config.py` | `setup_logging()` |
| `app/auth.py` | `verify_api_key` |
| `app/circuit_breaker.py` | `CircuitBreaker` class |
| `app/kb_resolver.py` | `KBResolver` class |
| `app/perplexity_client.py` | `query_perplexity()`, `SonarResponse` |
| `app/prompt_builder.py` | `build_variation_prompts()` |
| `app/validation_engine.py` | `validate_response()` |
| `app/consensus_engine.py` | `synthesize()` |
| `app/uncertainty_engine.py` | `apply_uncertainty()` |
| `app/schemas.py` | Pydantic models |
| `Dockerfile` | Container build |
| `pyproject.toml` or `requirements.txt` | Dependencies |
| `docker-compose.yml` | Local dev stack |

---

### Compliance Check (L9 Context)

| Check | Status | Notes |
|-------|--------|-------|
| **L9 Engine Integration** | ❌ N/A | This is a standalone service, not an L9 engine |
| **Chassis Contract** | ❌ Violates | Uses FastAPI directly (but this is intentional — it's not an L9 engine) |
| **structlog** | ✅ Pass | Uses `structlog.get_logger()` |
| **Async patterns** | ✅ Pass | Proper `async`/`await`, semaphores for concurrency |
| **Error handling** | ✅ Pass | Global exception handler, circuit breaker |
| **K8s best practices** | ✅ Pass | HPA, PDB, probes, RBAC, network policies |

---

### Verdict

| Decision | Recommendation |
|----------|----------------|
| **Import to L9?** | ❌ **NO** — This is a separate microservice, not an L9 engine component |
| **Use as-is?** | ⚠️ **INCOMPLETE** — Missing ~12 core Python files |
| **Next Action** | If you want to use this, you need the missing `app/*.py` files |

---

### Routing

| If you want to... | Do this |
|-------------------|---------|
| Complete this service | Find/create the missing `app/*.py` files |
| Deploy to K8s | Complete the app, then `make deploy ENV=staging` |
| Integrate with L9 | This would be a **separate service** that L9 could call via HTTP, not an engine module |
| Review the AI review script | The `scripts/ai_review.py` is self-contained and could be extracted for use elsewhere |

---

**Summary:** You have a well-structured but **incomplete** deployment kit for a standalone Perplexity-powered enrichment API. The infrastructure (Helm, Kustomize, CI/CD, ArgoCD) is production-ready, but the core application code (`app/*.py`) is missing ~12 files. This is **not** part of the Graph Cognitive Engine — it's a separate microservice.
=======


## Missing Python Files (12 total)

Based on the imports in `main.py` and `pipeline.py`:

| # | Missing File | Imported As | Purpose |
|---|--------------|-------------|---------|
| 1 | `app/config.py` | `from .config import get_settings, Settings` | Pydantic settings, env vars |
| 2 | `app/logging_config.py` | `from .logging_config import setup_logging` | structlog configuration |
| 3 | `app/auth.py` | `from .auth import verify_api_key` | API key verification dependency |
| 4 | `app/circuit_breaker.py` | `from .circuit_breaker import CircuitBreaker` | Failure threshold + cooldown |
| 5 | `app/kb_resolver.py` | `from .kb_resolver import KBResolver` | Knowledge base context injection |
| 6 | `app/perplexity_client.py` | `from .perplexity_client import query_perplexity` | Perplexity API wrapper |
| 7 | `app/prompt_builder.py` | `from .prompt_builder import build_variation_prompts` | Prompt variation generator |
| 8 | `app/validation_engine.py` | `from .validation_engine import validate_response` | Response validation |
| 9 | `app/consensus_engine.py` | `from .consensus_engine import synthesize` | Multi-response consensus |
| 10 | `app/uncertainty_engine.py` | `from .uncertainty_engine import apply_uncertainty` | Confidence thresholds + flags |
| 11 | `app/schemas.py` | `from .schemas import EnrichmentRequest, EnrichmentResponse, HealthResponse` | Pydantic models |
| 12 | `Dockerfile` | (build) | Container image |

Plus infrastructure:
- `pyproject.toml` or `requirements.txt` — dependencies
- `docker-compose.yml` — local dev stack

---

## Integration Architecture: Enrichment ↔ Graph Engine

The current code **violates L9 architecture** because it:
1. Creates its own FastAPI app (Contract 1 violation)
2. Doesn't use PacketEnvelope (Contract 6-8 violation)
3. Has no chassis integration

### Correct Architecture

The enrichment service should be an **L9 engine node** that:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           L9 CHASSIS (shared)                               │
│  POST /v1/execute → action routing → tenant resolution → observability      │
└─────────────────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────────┐            ┌─────────────────────────┐
│  GRAPH ENGINE       │            │  ENRICHMENT ENGINE      │
│  (this repo)        │◄──────────►│  (enrichment service)   │
│                     │  Packet    │                         │
│  handle_match()     │  Envelope  │  handle_enrich()        │
│  handle_sync()      │            │  handle_kb_resolve()    │
│  handle_admin()     │            │                         │
└─────────────────────┘            └─────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SHARED MEMORY SUBSTRATE                              │
│  PostgreSQL (PacketStore) + Neo4j (Graph) + pgvector (Embeddings)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Required Changes to Enrichment Service

**1. Convert to Handler Interface (Contract 2)**

Instead of FastAPI routes, expose action handlers:

```python
# enrichment_engine/handlers.py

from chassis.router import register_handler
from engine.packet.chassis_contract import inflate_ingress, deflate_egress

async def handle_enrich(tenant: str, payload: dict) -> dict:
    """
    Action: enrich
    Payload: {entity: {...}, kb_context: str, max_variations: int, ...}
    Returns: {fields: {...}, confidence: float, flags: [...], ...}
    """
    # Inflate incoming packet
    packet = inflate_ingress(payload)

    # Execute enrichment pipeline
    result = await enrich_pipeline(
        request=packet.payload,
        tenant=tenant,
        ...
    )

    # Wrap result in PacketEnvelope for lineage
    response_packet = packet.derive(
        kind="enrichment_result",
        payload=result,
    )

    return deflate_egress(response_packet)


async def handle_kb_resolve(tenant: str, payload: dict) -> dict:
    """Resolve KB context for a domain/entity."""
    ...


def register_all(router):
    """Called by chassis at startup."""
    router.register_handler("enrich", handle_enrich)
    router.register_handler("kb_resolve", handle_kb_resolve)
```

**2. Use PacketEnvelope for All Data (Contracts 6-8)**

```python
# enrichment_engine/packet/models.py

from engine.packet.packet_envelope import PacketEnvelope, PacketMetadata

# Enrichment request arrives as PacketEnvelope
# Enrichment result returns as PacketEnvelope.derive()
# All intermediate steps (Perplexity calls, consensus) logged as packets
```

**3. Inter-Engine Communication**

Graph Engine can call Enrichment Engine via delegation:

```python
# In graph engine, when a match needs enrichment:

from engine.packet.chassis_contract import delegate_to_node

async def handle_match_with_enrichment(tenant: str, payload: dict) -> dict:
    # 1. Execute graph match
    match_result = await execute_match(tenant, payload)

    # 2. Delegate to enrichment engine for top candidates
    for candidate in match_result["candidates"][:5]:
        enrichment_packet = PacketEnvelope.create(
            kind="enrichment_request",
            payload={"entity": candidate, "kb_context": payload.get("domain")},
            parent_id=match_result["packet_id"],  # Lineage!
        )

        enriched = await delegate_to_node(
            target_node="enrichment-engine",
            action="enrich",
            packet=enrichment_packet,
            tenant=tenant,
        )

        candidate["enrichment"] = enriched.payload

    return match_result
```

---

## Revised File Structure for L9-Compliant Enrichment Engine

```
enrichment-engine/                    # Separate repo or subdirectory
├── engine/
│   ├── handlers.py                   # register_all(), handle_enrich(), handle_kb_resolve()
│   ├── config/
│   │   ├── schema.py                 # EnrichmentConfig Pydantic model
│   │   ├── loader.py                 # Load enrichment domain specs
│   │   └── settings.py               # Environment settings
│   ├── pipeline/
│   │   ├── orchestrator.py           # Main pipeline (was pipeline.py)
│   │   ├── perplexity_client.py      # Perplexity API wrapper
│   │   ├── prompt_builder.py         # Variation prompts
│   │   ├── validation.py             # Response validation
│   │   ├── consensus.py              # Multi-response synthesis
│   │   └── uncertainty.py            # Confidence + flags
│   ├── kb/
│   │   ├── resolver.py               # KB context resolution
│   │   └── index.py                  # KB indexing
│   ├── resilience/
│   │   └── circuit_breaker.py        # Circuit breaker
│   ├── packet/
│   │   └── chassis_contract.py       # inflate_ingress, deflate_egress (shared)
│   └── compliance/
│       └── pii.py                    # PII handling for enriched data
├── domains/
│   └── plasticos_enrichment_spec.yaml  # Domain-specific enrichment config
├── tests/
│   ├── unit/
│   ├── integration/
│   └── compliance/
└── chassis/                          # Thin adapter (shared with graph engine)
    └── actions.py
```

---

## Communication Patterns

### Pattern 1: Graph Engine Delegates to Enrichment

```
User Request → Chassis → Graph Engine (handle_match)
                              │
                              ├─► Execute graph match
                              │
                              ├─► delegate_to_node("enrichment-engine", "enrich", packet)
                              │         │
                              │         ▼
                              │   Enrichment Engine (handle_enrich)
                              │         │
                              │         ├─► KB resolve
                              │         ├─► Perplexity fan-out
                              │         ├─► Consensus
                              │         └─► Return enriched PacketEnvelope
                              │
                              └─► Merge enrichment into match results
                              │
                              ▼
                         Return to User
```

### Pattern 2: Enrichment Writes to Shared Graph

```
Enrichment Engine (handle_enrich)
         │
         ├─► Get enrichment result
         │
         ├─► Write enriched properties to Neo4j via Graph Engine
         │         │
         │         ▼
         │   delegate_to_node("graph-engine", "sync", {
         │       entity_type: "EnrichedEntity",
         │       batch: [{id: entity_id, properties: enriched_fields}]
         │   })
         │
         └─► Return result with graph_synced: true
```

### Pattern 3: Shared Memory Substrate

Both engines read/write to the same PacketStore:

```python
# Both engines use the same memory substrate
from memory.substrate_service import MemorySubstrateService

# Enrichment results persisted with lineage
await memory.ingest_packet(enrichment_result_packet)

# Graph engine can query enrichment history
history = await memory.search(
    query=f"enrichment results for entity {entity_id}",
    kind="enrichment_result",
)
```

---

## Summary: What Needs to Happen

| Task | Description |
|------|-------------|
| **1. Create missing files** | The 12 Python files listed above |
| **2. Refactor to handler interface** | Remove FastAPI, expose `handle_enrich()` |
| **3. Add PacketEnvelope wrapping** | All inputs/outputs use `inflate_ingress()`/`deflate_egress()` |
| **4. Wire delegation protocol** | Graph ↔ Enrichment communication via `delegate_to_node()` |
| **5. Share memory substrate** | Both engines write to same PostgreSQL/Neo4j |
| **6. Update K8s manifests** | Deploy as separate service but same namespace, shared secrets |

Do you want me to generate the missing files with proper L9 integration, or do you have the original source files somewhere that we should adapt?
