# Workflow State — Enrichment.Inference.Engine

**Last Updated:** 2026-04-11
**Current Phase:** PHASE 4 — Validation (Transport SDK Cutover)

---

## Context Summary

The Enrichment.Inference.Engine is the Layer 2 ENRICH service in the L9 constellation. It provides:

- Multi-pass convergence loop for AI-powered entity enrichment
- Consensus-based multi-variation LLM synthesis
- Domain KB injection for vertical-specific context
- Inference bridge for deterministic rule firing
- Graph sync for pushing enriched entities to Neo4j

**Recent Major Milestone:** Transport SDK cutover completed for the live node runtime — SDK now owns `/v1/execute`, handlers register through the SDK registry, and Gate-only egress replaces direct peer transport in the active runtime path.

---

## Current State

### What's Built and Working

| Component | Status | Files |
| --------- | ------ | ----- |
| Core Enrichment Pipeline | ✅ Production-ready | `waterfall_engine.py`, `enrichment_orchestrator.py` |
| Consensus Engine | ✅ Enhanced | `consensus.py` with `synthesize()`, `merge_with_priority()` |
| Uncertainty Engine | ✅ Enhanced | `uncertainty.py` with `apply_uncertainty()`, risk levels |
| KB Resolver | ✅ Enhanced | `kb_resolver.py` with `KBContext`, domain fragments |
| Prompt Variations | ✅ New | `build_variation_prompts()` in `prompt_builder.py` |
| Consensus Handler | ✅ New | `handle_enrich_consensus` in `handlers.py` |
| HEALTH Service | ✅ Complete | 5 files in `app/health/` |
| SCORE Service | ✅ Complete | 6 files in `app/score/` |
| CI/CD Pipelines | ✅ Complete | 13 workflow files in `.github/workflows/` |
| Test Coverage | ✅ Expanded | 54 test files (was 1) |
| SDK Node Runtime | ✅ Active | `app/main.py`, `app/engines/orchestration_layer.py`, `app/api/v1/chassis_endpoint.py` |

### Gap Analysis Status (from Core Gap Analysis documents)

| Category | Total Gaps | Closed | Remaining |
| -------- | ---------- | ------ | --------- |
| ENRICH Engine Internal | 8 | 5 | 3 |
| Convergence Loop Structural | 4 | 2 | 2 |
| GRAPH Engine Service | 5 | 1 | 4 |
| ENRICH ↔ GRAPH Integration | 5 | 1 | 4 |
| Downstream Services | 6 | 2 | 4 |
| Infrastructure | 6 | 2 | 4 |
| Testing | 4 | 2 | 2 |
| **TOTAL** | **38** | **15** | **23** |

**Overall Progress:** ~40% of identified gaps closed

### Transport SDK Cutover Status (2026-04-11)

**Status:** ✅ LIVE RUNTIME CUTOVER COMPLETE

The repo now runs on the `constellation-node-sdk` transport surface:

- `app/main.py` creates the SDK node runtime via `create_node_app(...)`
- `/v1/execute` is SDK-owned; `app/api/v1/chassis_endpoint.py` keeps only app-specific supplemental routes
- runtime actions register through `constellation_node_sdk.runtime.handlers.register_handler`
- Gate-only egress is active in `app/engines/graph_sync_client.py`, `app/engines/packet_router.py`, and `app/services/graph_sync_hooks.py`
- local `chassis/` transport files and `app/engines/chassis_contract.py` were removed from the active codebase
- TransportPacket tests replaced the old app-local packet runtime slice

---

## Decision Log

| Date | Decision | Rationale |
| ---- | -------- | --------- |
| 2026-03-30 | Merge Enrichment-Deployment-pack into WaterfallEngine | L9 architecture compliance — single chassis ingress |
| 2026-03-30 | Add consensus-mode enrichment via `handle_enrich_consensus` | Enables multi-variation LLM synthesis with field-level voting |
| 2026-03-30 | Create `KBContext` dataclass for KB resolution | Structured context injection for domain-specific prompts |

---

## Open Questions

1. **PostgreSQL persistence strategy** — Use SQLAlchemy async or raw asyncpg?
2. **Event bus choice** — Redis Streams vs NATS for inter-service events?
3. **Multi-provider LLM priority** — OpenAI first or Anthropic for consensus diversity?

---

## Test Status

```text
Transport slice:  30 passing
Broader slice:   126 passing
Legacy gap file:   8 failing
```

Last run: 2026-04-11

Targeted SDK cutover validation:

- `tests/unit/test_orchestration_layer.py`
- `tests/test_pr21_packet_router.py`
- `tests/services/test_graph_return_channel.py`
- `tests/unit/test_chassis_contract.py`
- `tests/contracts/test_packet_envelope_contract.py`

Result: `30 passed`

Broader validation follow-up:

- `tests/services/test_contract_enforcement.py`
- `tests/contracts/test_config_env_contract.py`
- `tests/compliance/test_architecture.py`
- `tests/contracts/tier2/test_enforcement_packet_runtime.py`

Result: `126 passed`

Remaining failures after adding the broader companion file:

- `tests/integration/test_gap_fixes.py` still has 8 failures tied to older convergence/result-store/config assumptions, not the Transport SDK runtime path.

---

## Next Steps

See `TODO.md` for prioritized task list.

**Immediate priorities:**

1. Decide whether to rewrite or retire `tests/integration/test_gap_fixes.py` now that the transport/runtime architecture has moved on.
2. Remove or deprecate legacy direct-peer config fields once downstream services no longer rely on them.
3. Finish any remaining governance/docs language cleanup (TransportPacket / chassis vs legacy packet naming in docs).

---

## Recent Sessions (7-day window)

- 2026-04-11: Transport SDK cutover — SDK runtime adopted in `app/main.py`, Gate-only egress wired, local `chassis/` files removed, targeted transport slice green, broader transport-adjacent slice at 126 passing with 8 legacy `test_gap_fixes` failures remaining
- 2026-04-07: Gap analysis of `gap-fixes/` vs `app/` — 10 gap fixes identified as NOT integrated, blocked on SDK chassis
- 2026-03-30: GMP-ENRICH-001 — Consensus-mode enrichment merge (14 TODOs completed)
- 2026-03-30: Gap analysis audit — 4 reference documents analyzed, status report generated
