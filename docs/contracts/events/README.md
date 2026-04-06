# Event Contracts

> All events emitted by the Enrichment Inference Engine.

## Backend

**Redis Streams** (default): `XADD enrich:events:{tenant_id} MAXLEN ~ 10000`

**NATS** (optional, requires `nats-py`): subject `enrich.events.{tenant_id}.{event_type}`

## Event Types

| Event | Trigger | Source |
|-------|---------|--------|
| `enrichment_completed` | After successful enrichment | `emit_enrichment_completed()` |
| `enrichment_failed` | When enrichment state=failed | `EventType.ENRICHMENT_FAILED` |
| `convergence_completed` | After convergence loop ends | `emit_convergence_completed()` |
| `schema_proposed` | When SchemaProposer runs | `emit_schema_proposed()` |
| `score_invalidated` | When enrichment invalidates score | `EventType.SCORE_INVALIDATED` |
| `entity_updated` | After CRM writeback | `EventType.ENTITY_UPDATED` |

## Consuming Events

```python
import redis.asyncio as aioredis

client = aioredis.from_url("redis://localhost:6379", decode_responses=True)

# Read new events
messages = await client.xread(
    {"enrich:events:acme-corp": "$"},
    block=5000
)
```

