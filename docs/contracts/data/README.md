# Data Contracts

> PostgreSQL ORM models and Neo4j graph schema for the Enrichment Inference Engine.

## Storage Overview

| System | Purpose | Connection Env Var |
|--------|---------|-------------------|
| PostgreSQL | Enrichment results, convergence runs, field history, schema proposals | `DATABASE_URL` |
| Neo4j | Knowledge graph, entity relationships, KGE embeddings | `NEO4J_URI` |
| Redis | Idempotency keys, event streams (`enrich:events:{tenant}`) | `REDIS_URL` |

## Contracts Index

| Model | Table | Source |
|-------|-------|--------|
| `EnrichmentResult` | `enrichment_results` | `app/services/pg_models.py:43` |
| `ConvergenceRun` | `convergence_runs` | `app/services/pg_models.py:93` |
| `FieldConfidenceHistory` | `field_confidence_history` | `app/services/pg_models.py:137` |
| `SchemaProposalRecord` | `schema_proposals` | `app/services/pg_models.py:165` |

## Entity Relationships

```
convergence_runs (1) ──── (0..1) enrichment_results
enrichment_results (1) ── (0..*) field_confidence_history
```

