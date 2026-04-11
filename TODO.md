# TODO — Enrichment.Inference.Engine

**Last Updated:** 2026-04-07
**Source:** Gap analysis of Core Gap Analysis-1.md, Core Gap Analysis-2.md

---

## Priority Legend

- 🔴 **CRITICAL** — Blocks production deployment
- 🟠 **HIGH** — Blocks full product functionality
- 🟡 **MEDIUM** — Enhances product value
- 🟢 **LOW** — Polish and optimization

---

## 🔴 CRITICAL — Blocks Production

### PostgreSQL Persistence Layer
- [ ] `app/services/pg_store.py` — Database connection pool, CRUD operations
- [ ] `app/services/pg_models.py` — SQLAlchemy/Pydantic models for persistence
- [ ] `app/services/result_store.py` — Durable enrichment record storage
- [ ] Database migrations (Alembic) for schema versioning

**Why:** No durable storage exists — enrichment results, convergence state, field confidence history all need PostgreSQL + pgvector for embedding storage.

### Event Emitter
- [ ] `app/services/event_emitter.py` — Publish events when enrichment completes, scores change, tiers transition

**Why:** Downstream services (SIGNAL, SCORE, ROUTE) need event notifications to react to enrichment completions.

### Async Task Queue
- [ ] `app/services/task_queue.py` — Celery/ARQ/Redis Streams for async processing

**Why:** Batch enrichment runs synchronously. Production needs async processing for scale.

---

## 🟠 HIGH — Blocks Full Product

### Single chassis HTTP ingress (fix multi-path gates)
- [ ] **Problem:** One FastAPI process exposes many first-class routes (`/api/v1/enrich`, `/api/v1/enrich/batch`, discover, scan, proposals, `/v1/converge/*`, fields, etc.) *and* chassis routes (`POST /v1/execute`, `POST /v1/outcomes`). That violates the L9 “single ingress” model (constellation traffic should normalize on `POST /v1/execute` + health, not parallel REST surfaces).
- [ ] **Target:** Collapse external HTTP to chassis contract — e.g. `POST /v1/execute` (and documented health/readiness only); map CRM and internal flows through `PacketEnvelope` actions or a single adapter layer (deprecate direct `/api/v1/*` enrichment paths behind a migration window).
- [ ] **Follow-through:** Regenerate/sync `docs/contracts/api/openapi.yaml`, `node.constitution.yaml`, and integration docs (Salesforce, Odoo, Clay); wire or relocate `app/score/score_api.py` (currently unmounted) under the same ingress story.

### Downstream Services (Constellation Nodes)

| Service | Purpose | Files Needed |
|---------|---------|--------------|
| **SIGNAL** | Engagement/intent signal detection | `app/signal/` (5 files) |
| **ROUTE** | Lead routing from scores + territory | `app/route/` (5 files) |
| **FORECAST** | Pipeline forecasting from enriched data | `app/forecast/` (5 files) |
| **HANDOFF** | Automated handoff orchestration | `app/handoff/` (4 files) |

### GRAPH Engine Gaps
- [ ] Outcome recording endpoint (`POST /v1/outcomes`) — feeds reinforcement scoring
- [ ] CO-OCCURRED_WITH edge generation — collaborative filtering (35% of Amazon GMV)
- [ ] Entity resolution pre-match hook — deduplication before matching
- [ ] Graph→enrichment feedback channel — tell ENRICH which entities need work

### ENRICH ↔ GRAPH Integration
- [ ] Schema bridge utility — `DomainSpec.ontology.nodes.properties` → `EnrichRequest.schema`
- [ ] `enrichment_hints` in domain YAMLs — per-node-type config
- [ ] Pre-match enrichment wiring — ambiguous intake → enriched queries
- [ ] Outcome→enrichment delegation — rejection triggers re-enrichment

### gap-fixes/ Integration (BLOCKED — Awaiting SDK Chassis)
**Status:** Code complete in `gap-fixes/`, integration blocked until SDK chassis defines wiring patterns.

| Gap | Component | File in gap-fixes/ | Integration Status |
|-----|-----------|-------------------|-------------------|
| Gap-1 | Contract Enforcement | `enrich/contract_enforcement.py` | ⏸️ BLOCKED |
| Gap-2 | GRAPH→ENRICH Return Channel | `enrich/graph_return_channel.py` | ⏸️ BLOCKED |
| Gap-3 | Inference Rule Registry | `enrich/inference_rule_registry.py` | ⏸️ BLOCKED |
| Gap-4 | Schema Proposal Emission | `enrich/convergence_controller_patch.py` | ⏸️ BLOCKED |
| Gap-5 | Audit Persistence | `shared/audit_persistence.py` | ⏸️ BLOCKED |
| Gap-6 | Community Export Hook | `graph/community_export.py` | ⏸️ BLOCKED |
| Gap-7 | Per-field Confidence | `enrich/convergence_controller_patch.py` | ⏸️ BLOCKED |
| Gap-8 | Domain Spec Enforcement | `enrich/convergence_controller_patch.py` | ⏸️ BLOCKED |
| Gap-9 | v1 Bridge Guard | `shared/inference_bridge_v1_guard.py` | ⏸️ BLOCKED |
| Gap-10 | Packet Type Registry | `enrich/contract_enforcement.py` | ⏸️ BLOCKED |

**Startup wiring recipe:** `gap-fixes/app/startup_wiring.py`
**Tests:** `gap-fixes/tests/test_gap*.py` (4 test files)

**Why blocked:** SDK chassis will dictate PacketEnvelope validation, handler registration, and startup lifecycle. Integrating now would require rework.

### Multi-Provider LLM Clients
- [ ] `app/services/openai_client.py` — OpenAI API client
- [ ] `app/services/anthropic_client.py` — Anthropic API client

**Why:** Multi-variation consensus requires multiple LLM providers to avoid single-provider bias.

### PacketEnvelope Router
- [ ] `app/engines/packet_router.py` — Dispatch envelopes to constellation nodes

**Why:** `chassis_contract.py` builds envelopes but `delegate_to_node` creates packets without sending them.

---

## 🟡 MEDIUM — Enhances Product

### Infrastructure
- [ ] Terraform IaC — `terraform/` directory for repeatable deployments
- [ ] OpenTelemetry distributed tracing — cross-service observability
- [ ] Multi-tenant database isolation — PostgreSQL RLS enforcement

### API Endpoints (Missing Routes)
- [ ] `POST /api/v1/discover` — Trigger schema discovery independently
- [ ] `POST /api/v1/infer` — Run inference rules independently
- [ ] `GET /api/v1/profile/{domain}` — Get/set enrichment profiles per domain
- [ ] `GET /api/v1/convergence/{run_id}` — Get convergence run status/history
- [ ] `GET /api/v1/fields/{entity_id}` — Get field-level confidence + provenance

### Testing
- [ ] Integration tests with real Neo4j (testcontainers)
- [ ] Contract tests (ENRICH ↔ GRAPH bidirectional validation)
- [ ] Load/stress tests — performance baselines

### Field Provenance
- [ ] `app/models/provenance.py` — Track which pass/LLM/KB rule produced each field

---

## 🟢 LOW — Polish

### Convergence Loop
- [ ] Human-in-the-loop approval gate for schema changes (Discover tier)
- [ ] Domain KB hot-reload — add domains without restart

### Domain KB Expansion
- [ ] KB versioning and migration strategy
- [ ] KB validation schema (JSON Schema or Pydantic)
- [ ] Customer KB upload via API

### Documentation
- [ ] README.md with setup instructions
- [ ] CONTRIBUTING.md
- [ ] API documentation (OpenAPI/Swagger)

---

## ✅ COMPLETED (Recent)

### GMP-ENRICH-001 — Consensus-Mode Enrichment (2026-03-30)
- [x] `app/services/enrichment/consensus.py` — Multi-response synthesis
- [x] `app/services/enrichment/uncertainty.py` — Confidence thresholds and flagging
- [x] `app/services/enrichment/kb_resolver.py` — KB context injection
- [x] `build_variation_prompts()` in `prompt_builder.py`
- [x] `enrich_with_consensus()` in `waterfall_engine.py`
- [x] `handle_enrich_consensus` handler in `handlers.py`
- [x] Unit tests for consensus, uncertainty, kb_resolver (50 passing)
- [x] Integration tests for consensus enrichment (8 passing)
- [x] `plastics_kb.yaml` test fixture
- [x] Enrichment package README documentation

### Previously Completed
- [x] HEALTH service — 5 files in `app/health/`
- [x] SCORE service — 6 files in `app/score/`
- [x] CI/CD pipelines — 13 workflow files
- [x] CRM field scanner — `crm_field_scanner.py`
- [x] Enrichment profiles — `enrichment_profile.py`
- [x] Cost tracking — `cost_tracker.py`
- [x] Pass-level telemetry — `pass_telemetry.py`
- [x] Confidence tracker — `confidence_tracker.py`
- [x] L9 chassis contract — `chassis_contract.py`, `handlers.py`

---

## Files to Delete (Obsolete)

These files are superseded by the GMP-ENRICH-001 merge:

- [ ] `Enrichment-Deployment-pack/` — Features merged into WaterfallEngine
- [ ] `plastics_enrichment_client.py` — Standalone reference, superseded
- [ ] `Clean-CRM-Data-Readiness-Checklist.md` — Business process doc, not code
- [ ] `Clean-CRM-for-AI-Business-Case.md` — Executive doc, not code
- [ ] `Core Gap Analysis-1.md` — Analysis complete, tracked in this TODO
- [ ] `Core Gap Analysis-2.md` — Analysis complete, tracked in this TODO
- [ ] `File Build Plan.md` — All 12 files now exist

---

## Revenue Impact per Gap Closure

| Gap Closed | Revenue Tier Unlocked | $/mo |
|-----------|----------------------|------|
| CRM field scanner + single discovery pass | **Seed** (free → conversion engine) | $0 (50%+ conversion to Enrich) |
| Enrichment profiles + nightly batch | **Enrich** | $500 |
| Convergence loop + schema proposals + approval gate | **Discover** | $2,000 |
| Graph service + outcome feedback + inference loop | **Autonomous** | $5,000–10,000 |
| HEALTH + SCORE + ROUTE | **RevOpsOS mid-market** | $10,000–25,000 |
| Full constellation with FORECAST + HANDOFF | **RevOpsOS enterprise** | $25,000–50,000 |
