# Migration Policy

> Naming conventions and procedures for Alembic database migrations.

## Tool

Alembic via `alembic.ini`. Async engine via `migrations/env.py`.

## Naming Convention

```
{sequence:03d}_{description_snake_case}.py
```

Examples:
- `001_initial_schema.py` — baseline tables
- `002_add_domain_to_enrichment_results.py`
- `003_add_graph_coverage_index.py`

## Current Migration Baseline

| Revision | Description | Tables Created |
|----------|-------------|---------------|
| `001` | Initial schema | `convergence_runs`, `enrichment_results`, `field_confidence_history`, `schema_proposals` |

Source: `migrations/versions/001_initial_schema.py`

## Procedures

### Adding a Column
1. Create new migration: `alembic revision -m "add_field_name_to_table"`
2. Implement `upgrade()` with `op.add_column()`
3. Implement `downgrade()` with `op.drop_column()`
4. Update the corresponding JSON Schema in `docs/contracts/data/models/`
5. Update the Pydantic ORM model in `app/services/pg_models.py`

### Running Migrations
```bash
# Apply all pending
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current revision
alembic current
```

### Contract Update Protocol
Any migration that adds/removes/renames a column MUST:
1. Update the corresponding `data/models/*.schema.json`
2. Increment the `version` in the schema file header
3. Add a CHANGELOG entry

