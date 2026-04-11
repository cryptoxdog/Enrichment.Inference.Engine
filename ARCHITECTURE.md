# Architecture — Enrichment.Inference.Engine

## System Purpose

Universal domain-aware entity enrichment API for the L9 Constellation.
Enriches CRM entity records (Odoo + Salesforce) with structured intelligence extracted from external sources via LLM inference, normalizes data, and syncs to Neo4j for graph-based matching.

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.12+ |
| API Framework | FastAPI 0.115+ (chassis layer only) |
| LLM Inference | Perplexity sonar-reasoning |
| Knowledge Graph | Neo4j 5.x |
| Cache | Redis 7 |
| State Store | PostgreSQL 16 |
| CRM Integration | Odoo 19 (PlasticOS) + Salesforce |
| Observability | structlog + OpenTelemetry |
| Config | pydantic-settings v2 |

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│  API Layer (app/api/)                                           │
│  FastAPI chassis — routes delegate to engines only              │
│  intake.py │ converge.py │ chassis_endpoint.py                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Transport chassis (chassis/envelope.py + router + SDK /v1/execute)              │
│  Wire envelope dispatch → handler registry → app/engines/handlers.py            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Engine Layer (app/engines/)                                    │
│  ├── handlers.py              (action handlers)                 │
│  ├── enrichment_orchestrator.py                                 │
│  ├── convergence_controller.py                                  │
│  │     ├── confidence_tracker.py                                │
│  │     ├── cost_tracker.py                                      │
│  │     └── loop_state.py                                        │
│  ├── inference_bridge_v2.py   (DAG-based inference)             │
│  ├── meta_prompt_planner.py                                     │
│  └── graph_sync_client.py     (Neo4j sync)                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────────┐
│  Inference Engine       │       │  External Services          │
│  (app/engines/inference)│       │  tools/pplx_research.py     │
│  grade_engine.py        │       │  (Perplexity sonar)         │
│  rule_engine.py         │       └─────────────────────────────┘
│  nary_inference.py      │
└─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Storage Layer                                                  │
│  PostgreSQL (state) │ Neo4j (graph) │ Redis (cache)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow — Enrichment Run

```
1. API receives enrichment request (REST schemas) or `/v1/execute` TransportPacket (SDK)
2. Chassis / SDK dispatches to handler via registry
3. EntropyEngine scores data completeness (1–5)
4. KBInjector adds domain-relevant KB context to prompts
5. Convergence loop runs multi-pass enrichment:
   a. Meta-prompt planner selects fields to enrich
   b. Perplexity queries execute (concurrent, rate-limited)
   c. Inference bridge fires deterministic rules
   d. Confidence tracker updates per-field scores
6. Graph sync pushes enriched entity to Neo4j
7. Response packet returned with enrichment summary
```

---

## Key Contracts

| Contract | Location | Enforced By |
|----------|----------|-------------|
| Chassis dispatch | `chassis/envelope.py`, `chassis/router.py`, SDK runtime | Handler registry |
| Handler signature | `handlers.py` | C-02 contract |
| Tenant isolation | All Neo4j queries | `WHERE n.tenant_id = $tenant` |
| Synthesis threshold | `convergence_controller.py` | THRESHOLD=0.6 |
| Coverage minimum | CI pipeline | 60% coverage gate |

---

## Boundary Rules

1. **No FastAPI in engine/** — chassis isolation (C-01)
2. **No business logic in app/api/** — routes delegate to engines only
3. **No direct DB writes from API layer** — always through service/engine layer
4. **No LLM calls outside designated clients** — single point of control
5. **No bare dicts across service boundaries** — use `TransportPacket`, chassis wire contracts, or Pydantic models

---

## Module Ownership

| Directory | Owner | Tier |
|-----------|-------|------|
| `app/api/` | API team | T3 |
| `app/engines/` | Engine team | T3 |
| `app/engines/chassis_contract.py` | Platform | T4 |
| `app/engines/handlers.py` | Platform | T4 |
| `app/engines/graph_sync_client.py` | Platform | T4 |
| `app/models/` | Schema team | T5 |
| `kb/` | Knowledge team | T5 |

---

## Related Documents

- `AGENTS.md` — Agent operating model and contracts
- `CI_WHITELIST_REGISTER.md` — CI gates and waivers
- `.cursorrules` — Full contract definitions
