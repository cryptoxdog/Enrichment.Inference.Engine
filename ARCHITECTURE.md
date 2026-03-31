# Architecture — Enrichment.Inference.Engine

## System Purpose
Enrich CRM entity records (Odoo + Salesforce) with structured intelligence
extracted from external sources via LLM inference, then normalize and inject
that intelligence into PlasticOS material and facility profiles for high-accuracy buyer matching.

## Component Map

```
External Sources
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  API Layer  (app/api/v1/)                           │
│  intake.py │ converge.py │ chassis_endpoint.py      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Enrichment Orchestrator  (app/engines/)            │
│  enrichment_orchestrator.py                         │
│    ├── convergence_controller.py                    │
│    │     ├── confidence_tracker.py                  │
│    │     ├── cost_tracker.py                        │
│    │     └── loop_state.py                          │
│    ├── inference_bridge.py / _v2.py                 │
│    └── meta_prompt_planner.py                       │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌─────────────────┐     ┌─────────────────────────┐
│  Inference      │     │  External Services      │
│  (app/engines/  │     │  tools/pplx_research.py │
│   inference/)   │     │  (Perplexity sonar)     │
│  grade_engine   │     └─────────────────────────┘
│  rule_engine    │
│  nary_inference │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  Odoo Module  (odoo_modules/                        │
│               plasticos_research_enrichment/)       │
│  PerplexityClient │ EntropyEngine │ SynthesisEngine │
│  ExtractionEngine │ KBInjector    │ InferenceBridge │
│  AsyncRunner (orchestrates full per-partner run)    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Storage                                            │
│  Redis (hot cache) │ Graphiti (knowledge graph)     │
│  Odoo PostgreSQL   │ Neo4j (graph traversal)        │
└─────────────────────────────────────────────────────┘
```

## Data Flow — Enrichment Run

```
1. API receives enrichment request (partner_id)
2. EntropyEngine scores data completeness (1–5)
3. KBInjector adds domain-relevant KB context to prompts
4. AsyncRunner fans out 3–5 concurrent Perplexity queries
5. ExtractionEngine validates each response against signal schema
6. SynthesisEngine aggregates valid responses (threshold: 0.6)
7. InferenceBridge writes grade/tier/confidence to partner record
8. Graphiti sync captures enrichment event for knowledge graph
```

## Key Contracts

| Contract | Location | Enforced By |
|----------|----------|-------------|
| Signal schema | `odoo_modules/.../signal_schema.py` | `ExtractionEngine.validate()` |
| Synthesis threshold | `synthesis_engine.py` THRESHOLD=0.6 | `SynthesisEngine.synthesize()` |
| Concurrency limit | `async_runner.py` MAX_CONCURRENCY=3 | `asyncio.Semaphore` |
| Min valid responses | `async_runner.py` MIN_VALID=2 | `process_run()` |
| Field allowlist | `inference_bridge.py` | `partner.write({...})` |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI 0.115+ |
| LLM inference | Perplexity sonar-reasoning |
| Knowledge graph | Graphiti + Neo4j 5.x |
| Hot cache | Redis 7 |
| CRM | Odoo 19 (PlasticOS) + Salesforce |
| Observability | OpenTelemetry (OTLP/gRPC) |
| Config | pydantic-settings v2 |

## Boundary Rules

- No business logic in `app/api/` — routes delegate to engines only
- No direct DB writes from API layer — always through service layer
- No LLM calls outside `PerplexityClient` — single point of control
- No partner field writes without prior `ExtractionEngine.validate()`
