# feat: replace static web extraction with Perplexity Sonar in simulation bridge

## What changed

| File | Type | Change |
|------|------|--------|
| `app/services/simulation_bridge.py` | Modified | Sonar-powered entity generator replaces static random generator |
| `app/engines/handlers.py` | Modified | Adds `handle_simulate` handler; wires `sonar_api_key` into `simulate()` |

**No other files changed.** No CEG changes. No `perplexity_client.py`, `prompt_builder.py`, `waterfall_engine.py`, or `enrichment_orchestrator.py` changes.

---

## What this PR does

### `simulation_bridge.py`

Adds 5 new functions alongside the preserved `generate_synthetic_entities()` fallback:

| Function | Role |
|----------|------|
| `_build_simulation_schema()` | Builds `target_schema` dict from CRM field names + domain YAML type hints |
| `_sonar_entity_for_name()` | Async: fires one Sonar call per company name via existing `query_perplexity` + `build_prompt` |
| `_map_sonar_result_to_crm()` | Maps Sonar field dict onto customer CRM field name keys |
| `_static_entity_fallback()` | Per-slot static fallback when Sonar returns empty data (preserves original logic) |
| `_generate_sonar_entities_async()` | Async core: semaphore-bounded concurrent Sonar calls, per-slot fallback |
| `generate_sonar_entities()` | Drop-in sync wrapper: returns `list[dict[str, Any]]` identical to `generate_synthetic_entities()` |

`simulate()` gets three new optional parameters:
- `use_sonar: bool = True` — feature flag; `False` reverts to static mode (CI / offline)
- `sonar_api_key: str | None = None` — explicit key override; falls back to `settings.perplexity_api_key`
- `company_names: list[str] | None = None` — override the entity name list for Sonar research

### `handlers.py`

Adds `handle_simulate` handler registered as `"simulate"` action:

```json
{
  "crm_field_names": ["polymers_handled", "certifications", "annual_capacity_tons"],
  "domain_id": "plastics",
  "customer_name": "Acme Corp",
  "entity_count": 20,
  "use_sonar": true
}
```

Returns the full `ExecutiveBrief` serialized via `brief_to_dict()`.

---

## Design invariants preserved

1. **Drop-in contract**: `generate_sonar_entities()` returns identical `list[dict[str, Any]]` shape with `_entity_id` + `_entity_name`. `_simulate_entities()` unchanged.
2. **Zero fabrication**: Sonar returns web-sourced facts. Static fallback fires per-slot for entities with no web presence — representing honest data sparsity.
3. **Graceful degradation**: `use_sonar=False` → original behavior. No API key → falls back entirely to static generator. Individual Sonar failure → that slot gets static fallback.
4. **No circular imports**: New code imports only from `..services.perplexity_client` and `..services.prompt_builder` — same level as existing bridge.
5. **Convergence loop integrity**: Inference rules fire on top of Sonar-enriched data. Sonar fills searchable fields; `run_inference()` derives computed fields from them.
6. **Model selection**: Uses `sonar` (base model, ~$0.0004/call) — not `sonar-reasoning` or `sonar-deep-research`. Simulation is demo-grade, not production enrichment.
7. **PacketEnvelope safe**: `handle_simulate` follows identical handler contract. Chassis wraps response in envelope.

---

## Cost at simulation grade

| Entities | Model | Est. cost |
|----------|-------|-----------|
| 20 | sonar | ~$0.008 |
| 50 | sonar | ~$0.020 |
| 100 | sonar | ~$0.040 |

---

## File tree

```
app/
├── engines/
│   └── handlers.py                   ← MODIFIED (adds handle_simulate)
└── services/
    └── simulation_bridge.py          ← MODIFIED (Sonar entity generator)
```

## Testing checklist

- [ ] `use_sonar=False` returns identical output to old `generate_synthetic_entities()` for same seed
- [ ] `PERPLEXITY_API_KEY` unset → static fallback fires, no exception raised
- [ ] Individual Sonar 429/500 → that slot falls back to static, rest succeed
- [ ] `handle_simulate` callable via chassis with minimal payload `{crm_field_names, domain_id}`
- [ ] Semaphore prevents >5 concurrent Sonar calls at any time
- [ ] `_entity_id` and `_entity_name` sentinels present on every returned entity
