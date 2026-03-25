# ENRICH Engine — Next 12 Files to Close the Loop

## Current State

The single-pass enrichment pipeline is production-ready: 10-step orchestrator, 8 services, FastAPI ingress, auth, rate limiting, Redis idempotency, and full test coverage. The convergence loop skeleton exists — `convergence_controller.py`, `meta_prompt_planner.py`, `inference_bridge.py`, `schema_discovery.py` — but these are coordinators calling into modules that don't exist yet. The graph engine is done. Infrastructure is explicitly deferred. The goal is to make the enrichment-inference convergence loop a fully operational closed system.[^1][^2]

***

## Build Order

The files are sequenced so each one unlocks the next. No file depends on something later in the list.

| # | File | Path | Lines (est.) | Depends On |
|---|------|------|-------------|------------|
| 1 | Field Confidence Tracker | `app/models/field_confidence.py` | ~120 | schemas.py (exists) |
| 2 | Loop Schemas | `app/models/loop_schemas.py` | ~150 | field_confidence (#1) |
| 3 | Rule Loader | `app/engines/inference/rule_loader.py` | ~180 | domain YAML (exists) |
| 4 | Rule Engine | `app/engines/inference/rule_engine.py` | ~220 | rule_loader (#3) |
| 5 | Grade Engine | `app/engines/inference/grade_engine.py` | ~160 | rule_engine (#4), kb_resolver (exists) |
| 6 | Cost Tracker | `app/engines/convergence/cost_tracker.py` | ~100 | loop_schemas (#2) |
| 7 | Pass Telemetry | `app/engines/convergence/pass_telemetry.py` | ~130 | loop_schemas (#2), field_confidence (#1) |
| 8 | Loop State Store | `app/engines/convergence/loop_state.py` | ~140 | loop_schemas (#2), cost_tracker (#6) |
| 9 | CRM Field Scanner | `app/services/crm_field_scanner.py` | ~180 | domain_yaml_reader (exists) |
| 10 | Enrichment Profiles | `app/services/enrichment_profile.py` | ~150 | field_confidence (#1), cost_tracker (#6) |
| 11 | Schema Proposer | `app/engines/convergence/schema_proposer.py` | ~200 | field_confidence (#1), rule_loader (#3), domain_yaml_reader (exists) |
| 12 | Convergence API | `app/api/v1/converge.py` | ~160 | everything above |

**Total: ~1,890 lines across 12 files.**

***

## File 1 — `app/models/field_confidence.py`

**Why first:** Every downstream file needs per-field confidence. The existing consensus engine returns a single float for the entire entity. SCORE, HEALTH, the uncertainty engine, and the convergence check all need to know *which fields* are weak, not just that the entity as a whole scored 0.82.[^2][^1]

**What it does:**

- `FieldConfidence` — Pydantic model: `field_name`, `value`, `confidence` (0.0–1.0), `source` (enum: `crm`, `enrichment`, `inference`), `variation_agreement` (e.g., 4/5 = 0.80), `pass_discovered` (int), `kb_fragment_ids` (list)
- `FieldConfidenceMap` — dict wrapper keyed by field_name with aggregate methods: `weakest_fields(n)`, `fields_below(threshold)`, `avg_confidence`, `coverage_ratio`
- `compute_field_confidence(consensus_payloads, target_schema)` — takes the raw validated payloads from consensus and computes per-field agreement. If 4/5 variations return `materials_handled: ["HDPE", "LDPE"]` with same values, that field gets 0.80 confidence. If only 2/5 agree on `contamination_tolerance: 0.03`, that field gets 0.40[^1]
- Serializable to dict for PacketEnvelope payload embedding

**Feeds into:** loop_schemas (#2), pass_telemetry (#7), enrichment_profiles (#10), schema_proposer (#11), and eventually HEALTH + SCORE services.

***

## File 2 — `app/models/loop_schemas.py`

**Why second:** The convergence loop introduces request/response shapes that don't exist in `schemas.py`. Every convergence file needs these types.[^1]

**What it does:**

- `ConvergeRequest` — extends EnrichRequest with: `domain` (str), `max_passes` (int, default 5), `max_budget_tokens` (int, default 50000), `approval_mode` (enum: `auto` | `human`), `convergence_threshold` (float, default 2.0)
- `PassResult` — per-pass snapshot: `pass_number`, `mode` (discovery/targeted/verification), `fields_enriched` (list[str]), `fields_inferred` (list[str]), `field_confidences` (FieldConfidenceMap), `uncertainty_before`, `uncertainty_after`, `tokens_used`, `duration_ms`
- `ConvergeResponse` — full loop result: `entity_id`, `passes` (list[PassResult]), `final_fields` (dict), `final_field_confidences` (FieldConfidenceMap), `schema_proposals` (list[SchemaProposal]), `convergence_reason` (enum: `threshold_met` | `budget_exhausted` | `max_passes` | `human_hold`), `total_tokens`, `total_cost_usd`, `domain_yaml_version_before`, `domain_yaml_version_after`
- `SchemaProposal` — proposed field additions: `field_name`, `field_type`, `source` (enrichment/inference), `fill_rate`, `avg_confidence`, `sample_values`, `proposed_gate` (optional), `proposed_scoring_dimension` (optional)

***

## File 3 — `app/engines/inference/rule_loader.py`

**Why third:** The inference engine needs structured rules loaded from YAML before it can fire anything. `inference_bridge.py` currently has hardcoded plastics rules — this replaces that with a domain-agnostic loader.[^1]

**What it does:**

- `RuleDefinition` — Pydantic model: `rule_id`, `conditions` (list of `{field, operator, value}`), `outputs` (list of `{field, value_expr, derivation_type}`), `confidence` (float), `priority` (int), `domain` (str), `description` (str)
- Supported operators: `CONTAINS`, `EQUALS`, `GT`, `LT`, `GTE`, `LTE`, `IN`, `NOT_IN`, `IS_TRUE`, `IS_FALSE`, `EXISTS`
- `RuleRegistry` — indexed by trigger fields for O(1) candidate lookup. When the engine asks "which rules might fire given I just filled `materials_handled`?", the registry returns only rules where `materials_handled` appears in conditions[^1]
- `load_rules(domain_yaml_path)` — parses the `inference_rules` section of a domain YAML, validates syntax at load time (bad operator → error, not silent), builds registry
- `reload()` — hot-reload support: re-reads YAML, rebuilds registry, swaps atomically (no request sees a half-loaded state)

**Example rule from `plastics_recycling.yaml`:**

```yaml
inference_rules:
  - rule_id: grade-assignment-hdpe
    conditions:
      - field: materials_handled
        operator: CONTAINS
        value: HDPE
      - field: contamination_tolerance_pct
        operator: LT
        value: 0.05
    outputs:
      - field: material_grade
        value_expr: "B"
        derivation_type: classification
    confidence: 0.90
    priority: 10
```

***

## File 4 — `app/engines/inference/rule_engine.py`

**Why fourth:** This is the standalone deterministic inference engine that replaces the non-existent `plasticos.inference.engine` Odoo model. It fires rules against enriched feature vectors and produces derived fields.[^2]

**What it does:**

- `infer(entity_fields: dict, registry: RuleRegistry) → InferenceResult`
- For each rule in the registry where all trigger fields exist in the entity:
  1. Evaluate conditions (all must pass — AND logic within a rule)
  2. If rule fires → add outputs to derived_fields with full derivation chain
  3. Track `rules_fired`, `rules_evaluated`, `rules_skipped` (missing trigger fields)
- `InferenceResult` — `derived_fields` (dict), `rules_fired` (list[RuleFired]), `derivation_chains` (dict mapping field → list of rule_ids that produced it), `inference_confidence` (min confidence across all fired rules)
- Priority handling: if two rules produce the same output field, highest priority wins. Tie → highest confidence wins
- **Cascading inference:** after first pass, check if newly derived fields trigger additional rules. Loop until no new rules fire (max 3 cascade levels to prevent infinite loops)[^1]
- Domain-agnostic: works with any RuleRegistry from any domain YAML

***

## File 5 — `app/engines/inference/grade_engine.py`

**Why fifth:** Grade/tier classification is the highest-value inference output. `material_grade`, `facility_tier`, `application_class`, `buyer_class` — these are what make entities matchable in the graph. The rule engine (#4) handles generic IF/THEN rules; the grade engine handles the specific pattern of matching a feature vector against grade envelopes.[^1]

**What it does:**

- `GradeDefinition` — from KB YAML: `grade_id`, `grade_label` (A/B+/B/C/D), `conditions` (dict of field → range/value), `tier` (str), `application_class` (str)
- `classify(entity_fields: dict, grade_defs: list[GradeDefinition]) → GradeResult`
- Scoring: for each grade definition, compute match_score = (number of conditions met / total conditions). Best-fit grade = highest match_score above threshold (0.6 default)[^1]
- `GradeResult` — `grade`, `tier`, `application_class`, `quality_tier`, `match_score`, `conditions_met`, `conditions_missed`, `fallback_used` (bool)
- SIMILAR_TO fallback: if no grade meets threshold, return closest grade with `fallback_used: true` and reduced confidence
- Loads grade definitions from the domain KB (e.g., `plastics-recycling-v8.yaml` `grades` section)

***

## File 6 — `app/engines/convergence/cost_tracker.py`

**Why sixth:** The convergence loop can burn unlimited Sonar tokens if convergence is slow. This enforces a budget ceiling and tracks cost per pass.[^1]

**What it does:**

- `CostTracker` — initialized with `max_budget_tokens` (from ConvergeRequest)
- `record_pass(pass_number, tokens_used)` — accumulates spend, computes cost_usd (tokens × rate)
- `budget_remaining() → int` — tokens left before hard stop
- `can_continue() → bool` — returns False if budget exhausted
- `cost_per_field(total_fields_discovered)` — unit economics: total_cost / fields_discovered
- `to_summary() → CostSummary` — `total_tokens`, `total_cost_usd`, `tokens_per_pass` (list), `cost_per_field`, `budget_utilization_pct`
- Token rate configurable in Settings (default: $0.005/1K tokens for sonar-reasoning)
- Integrated into `convergence_controller.py`'s main loop: checked between passes

***

## File 7 — `app/engines/convergence/pass_telemetry.py`

**Why seventh:** The core product claim — "each pass gets better" — is currently an assertion, not a measurement. This makes it provable.[^1]

**What it does:**

- `PassTelemetryCollector` — accumulates PassResult objects across the loop
- `record_pass(pass_result: PassResult)` — stores snapshot
- `confidence_delta(pass_a, pass_b)` — per-field and aggregate confidence improvement
- `uncertainty_delta(pass_a, pass_b)` — uncertainty reduction between passes
- `diminishing_returns_check(window=2)` — if the last N passes improved uncertainty by less than 5%, signal convergence even if threshold not technically met
- `convergence_report() → ConvergenceReport` — full pass-over-pass comparison: fields discovered per pass, confidence trajectory, uncertainty trajectory, tokens spent per pass, ROI per pass (fields_gained / tokens_spent)
- This is the data that proves the upsell: "Pass 1 cost $0.25 and found 12 fields. Pass 2 cost $0.08 and found 6 more. Pass 3 cost $0.03 and confirmed 3. Total: $0.36 for 21 fields at 0.91 confidence."[^1]

***

## File 8 — `app/engines/convergence/loop_state.py`

**Why eighth:** `convergence_controller.py` runs in-memory. A crash mid-loop loses all multi-pass progress. For batch convergence of 5,000 entities, this is unacceptable.[^1]

**What it does:**

- `LoopState` — Pydantic model: `run_id` (UUID), `entity_id`, `domain`, `state` (enum: `running`, `converged`, `budget_exhausted`, `max_passes`, `human_hold`, `failed`), `current_pass`, `passes_completed` (list[PassResult]), `accumulated_fields`, `accumulated_confidences` (FieldConfidenceMap), `cost_summary` (CostSummary), `created_at`, `updated_at`
- `LoopStateStore` — abstract interface with two implementations:
  - `RedisLoopStateStore` — serializes LoopState to Redis with TTL (24h default). Fast, ephemeral
  - `PostgresLoopStateStore` — persists to `convergence_runs` table. Durable, queryable
- `save(state)`, `load(run_id) → LoopState | None`, `resume(run_id)` — picks up from last completed pass
- `list_active(domain=None)` — returns all in-progress loops (for admin dashboard)
- `convergence_controller.py` calls `save()` after every completed pass. On restart, `resume()` loads state and continues from the last checkpoint

***

## File 9 — `app/services/crm_field_scanner.py`

**Why ninth:** This is the Seed tier trojan horse. Day 0: customer connects CRM. The scanner reads their existing field schema and generates the discovery report that converts free → $500/mo.[^1]

**What it does:**

- `scan_crm_fields(fields: list[CRMField]) → ScanResult` — accepts raw CRM field list (name + type pairs from Salesforce/HubSpot/Odoo API metadata)
- `CRMField` — `name` (str), `type` (str: string/float/bool/enum/list), `sample_values` (list, optional), `fill_rate` (float, optional)
- Maps CRM fields against the domain YAML's `ontology.nodes.properties` to identify: **matched** (CRM field maps to a known property), **unmapped** (CRM field exists but isn't in the domain), **missing** (domain property has no CRM field)[^1]
- `generate_seed_yaml(scan_result, domain_template) → str` — produces a `v0.1.0-seed` domain YAML containing only the customer's current fields
- `generate_discovery_report(scan_result) → DiscoveryReport` — the sales document: "You have 5 fields. Your domain needs 23. Here are the 18 you're missing, ranked by impact on matching quality."
- Impact ranking: fields that are gate-critical in the domain YAML rank highest (e.g., `contamination_tolerance` is a gate → missing it blocks all matching). Scoring-dimension fields rank second. Nice-to-have fields rank last

***

## File 10 — `app/services/enrichment_profile.py`

**Why tenth:** Nightly batch enrichment has no selection criteria. Running all 5,000 entities every night wastes tokens. The profile selects the highest-impact entities.[^1]

**What it does:**

- `EnrichmentProfile` — Pydantic model: `profile_name`, `selection_criteria` (`max_staleness_days`, `min_null_count`, `confidence_below`, `min_failed_matches`, `is_gate_critical_incomplete`), `batch_size`, `max_budget_tokens`, `schedule_cron`, `convergence_mode` (bool — run full loop or single pass)
- `select_entities(profile, entity_store) → list[EntityRef]` — queries the entity store, applies selection criteria, ranks by priority score:
  - Priority = `(null_count × 0.4) + (staleness_days × 0.3) + ((1 - confidence) × 0.2) + (failed_matches × 0.1)`
  - Respects `batch_size` ceiling
- `allocate_budget(entities, max_budget_tokens) → list[EntityBudget]` — distributes tokens across selected entities. High-uncertainty entities get more tokens (more variations). Low-uncertainty entities get fewer (verification only)[^1]
- `ProfileRegistry` — loads profiles from config. Default profiles: `nightly_stale` (entities not enriched in 30+ days), `high_null` (entities with >50% NULL fields), `failed_match` (entities involved in rejected matches), `new_intake` (entities synced in last 24h)

***

## File 11 — `app/engines/convergence/schema_proposer.py`

**Why eleventh:** This is the Discover tier ($2K/mo) unlock. After running the convergence loop on a batch, the system aggregates what it discovered and proposes schema changes to the customer.[^1]

**What it does:**

- `propose(batch_results: list[ConvergeResponse], current_yaml: DomainSpec) → SchemaProposalSet`
- Aggregates discovered fields across all entities in the batch. For each candidate field:
  - `fill_rate` — what % of entities have this field after convergence
  - `avg_confidence` — mean confidence across entities
  - `value_distribution` — histogram of observed values (for enums: top 5 values; for floats: min/max/mean/stddev)
  - `source` — `enrichment` (discovered from research) or `inference` (derived from rules)
- Filter: only propose fields with fill_rate > 0.60 and avg_confidence > 0.70[^1]
- `propose_gates(proposed_fields, domain_spec)` — if a proposed field is numeric with meaningful variance, propose it as a scoring dimension. If it's categorical with clear partitioning, propose it as a gate
- `SchemaProposalSet` — `proposed_fields` (list), `proposed_gates` (list), `proposed_scoring_dimensions` (list), `yaml_diff` (the exact YAML additions), `version_bump` (e.g., `0.2.0-discovered`)
- `apply(proposal, approval_decisions) → DomainSpec` — takes human approvals (Discover tier) or auto-approves (Autonomous tier), writes updated YAML with version bump

***

## File 12 — `app/api/v1/converge.py`

**Why last:** This wires everything above into HTTP endpoints. It's the thin API layer on top of the convergence controller.[^1]

**What it does:**

- `POST /v1/converge` — runs full multi-pass convergence loop for a single entity. Accepts ConvergeRequest, returns ConvergeResponse. Calls `convergence_controller.run()` which orchestrates enrichment_orchestrator → rule_engine → grade_engine → meta_prompt_planner → loop until converged
- `POST /v1/converge/batch` — runs convergence for a batch with budget allocation via enrichment_profiles. Accepts `BatchConvergeRequest` (entities + profile_name or inline criteria). Returns `BatchConvergeResponse` (list of ConvergeResponse + aggregate stats)
- `GET /v1/converge/{run_id}` — check loop progress for long-running convergence. Returns current LoopState: which pass, current uncertainty, fields discovered so far, cost so far
- `POST /v1/converge/{run_id}/approve` — human approval endpoint for Discover tier. Accepts `ApprovalDecision` (list of field_name → approve/reject). If all proposals approved or rejected, loop continues or terminates
- `GET /v1/converge/proposals/{domain}` — returns all pending SchemaProposalSets for a domain, awaiting human review
- `POST /v1/scan` — CRM field scanner endpoint. Accepts CRM field list, returns DiscoveryReport + seed YAML. This is the Seed tier entry point

***

## Dependency Graph

```
schemas.py (exists)
    └─→ [^1] field_confidence.py
            └─→ [^2] loop_schemas.py
            │       └─→ [^6] cost_tracker.py ──→ [^8] loop_state.py
            │       └─→ [^7] pass_telemetry.py
            └─→ [^10] enrichment_profile.py
            └─→ [^11] schema_proposer.py

domain YAML (exists)
    └─→ [^3] rule_loader.py
            └─→ [^4] rule_engine.py
                    └─→ [^5] grade_engine.py

domain_yaml_reader.py (exists)
    └─→ [^9] crm_field_scanner.py

ALL OF THE ABOVE
    └─→ [^12] converge.py (API layer)
```

***

## What This Unlocks

| Revenue Tier | Files Required | Monthly |
|-------------|----------------|---------|
| **Seed** (free → conversion) | #1, #9 (field_confidence + crm_field_scanner) | $0 (but 50%+ conversion to Enrich)[^1] |
| **Enrich** ($500/mo) | + #10 (enrichment_profiles for nightly batch) | $500 |
| **Discover** ($2K/mo) | + #2–8, #11 (full convergence loop + schema proposals) | $2,000[^1] |
| **Autonomous** ($5K–10K/mo) | + #12 with auto-approval + graph integration (already built) | $5,000–10,000[^1] |

After these 12 files, the enrichment-inference engine is a complete, closed-loop system. The graph engine is already done. The next phase would be HEALTH (first downstream service), then SCORE — both of which consume field_confidence (#1) and convergence data from these files.[^1]

---

## References

1. [SCHEMA_DISCOVERY_LOOP-INFERENCE.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_da6cae39-fb04-40d2-8e51-f29164b3a1a6/deba6be4-b02f-4bb9-9b56-e555ed44ba46/SCHEMA_DISCOVERY_LOOP-INFERENCE.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=n7DVmJxkh14Ibb6s3hsHxWSMGic%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - --- TITLE Schema Discovery Loop - Enrichment Inference Schema Evolution The Correct Flow

2. [lead-enrichment-fastapi-jSFev7y4TxaCfHtXCv7_Pw.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_da6cae39-fb04-40d2-8e51-f29164b3a1a6/46a4230c-8094-4297-bd2f-0f56bc86af00/lead-enrichment-fastapi-jSFev7y4TxaCfHtXCv7_Pw.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=nLd7NZz1viY90WTYpk%2FLw8WjIH8%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - img srchttpsr2cdn.perplexity.aipplx-full-logo-primary-dark402x.png styleheight64pxmargin-right32px

3. [graph-repo-development-yvPwwEF_SyiqKAFuAiO7AA.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_da6cae39-fb04-40d2-8e51-f29164b3a1a6/771d6eba-337d-4e0b-9d2f-bb540dcbe116/graph-repo-development-yvPwwEF_SyiqKAFuAiO7AA.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=xVcBlbbW%2F0i%2FpdZ3H067Vw%2FEQ6c%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - Goal Add GDS jobs reinforcement learning. Deliverables - appjobsscheduler.py APScheduler - appjobslo...

4. [L9_CONTRACT_SPECIFICATIONS.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_da6cae39-fb04-40d2-8e51-f29164b3a1a6/9fb979c6-f784-4c6e-a221-90bf5d792732/L9_CONTRACT_SPECIFICATIONS.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=w%2BkNEuArIEst3X8o7Mv4s9ZZHCg%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - python class MatchPayloadBaseModel query dictstr, Any Entity attributes to match against matchdirect...

5. [L9_AI_Constellation_Infrastructure_Reference.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_da6cae39-fb04-40d2-8e51-f29164b3a1a6/f1b11331-8932-4b55-99bb-a300a099eba0/L9_AI_Constellation_Infrastructure_Reference.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=YbDHgNyXTwBVg80%2BFuP9tOcon%2Bg%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - --- TITLE L9 AI-Constellation Infrastructure Reference - Facts Only. No Prescriptions. - Version 1.0...

6. [circuit_breaker-2.py](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/971956af-7b74-44dc-9d37-b750ce1b5c6d/circuit_breaker-2.py?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=%2BaITOmMXGBn9Q8nUrV0vugZ1U5U%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)

7. [auth.py](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/221f6db8-66b7-4dc5-bf00-668f52a72e63/auth.py?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=5rdYmGPmXLacXWGNdA7ulUn08ro%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)

8. [CORE-INFRA-REMAINGIN-FILES-TO-HARVEST-5.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/d799b8ba-8d1a-4dde-a4c3-6bdacc44b7db/CORE-INFRA-REMAINGIN-FILES-TO-HARVEST-5.md?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=nDidNFyM55CdG5Zmihg%2B0JFI29Q%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714) - Let me provide the remaining files and write everything to disk in my response. Here's the complete ...

9. [config-3.py](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/b000f808-662f-4c6b-ba49-9a53d15b59f7/config-3.py?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=V9F%2B%2FsPqLaXDwtpn7xfO4emz22g%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)

10. [consensus_engine-4.py](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/d6c724c1-65f8-4281-b0b2-9f9531a642f1/consensus_engine-4.py?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=LVwOKtOz3xW94PBS6WgCBf%2FxyUA%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)

11. [env-8.example](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/77ba96b0-d310-4676-93aa-997c8bd68a6e/env-8.example?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=1u5Fuqa4G82RZORULYYjQDSZUcM%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)

12. [docker-compose-6.yml](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71024110/e456e65b-fdf6-455b-8ecf-c5342f1a8244/docker-compose-6.yml?AWSAccessKeyId=ASIA2F3EMEYE3JMWAB5I&Signature=Vdm6STksiTFn4Z9Fi0WodJo9s2A%3D&x-amz-security-token=IQoJb3JpZ2luX2VjELj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQCH1fEcbNazZvg%2BrM%2Fgy2oVCMnX%2B1suspzTyp%2F8qToWCwIhAKegRK1P1VHn5k04oHg1fbleWHMhtXpbTnQkTo7vAtOOKvwECIH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgwW5mIDhmE5P9dMLK8q0AS%2F0Odz7jYHkj%2FQPQ0MpoDs3qLFh%2FaMq%2Fqj3Jy88%2BjZ6f7XcixNRQIPsBbj%2BeEIGYSrY0NFVJTMUb2Q7224LVOz9H0H0TjwxnpW8RpiU%2FRNJlEc44f7NPIp53e7ilaO14DZpfitnzXs32P7v6PMWhOgYpoaHfMrBBNEHrhJQfwB%2B%2F1bVQcsqY8T8M4akrBRy8Glq8JFWKI57A3FdKzJR80HS5p6Lp3Xyw7a2oC%2BXJb0SdnJ%2B8IB3JpyywUUptguRapvkTgNg1fkGU1nq5Au5mmqbI0%2FnH7D7L0NweFNdTERj5ufPPR8EEIk1vdvK9U1%2FH2leKpzLYLscNtdRAI3jJ%2B1jA%2BY39atSKwvG%2FWRKOoBVr1tfZnVeaeUfIcLlF7gJJKRsBpFLvdkyc1OIGiIQHTkf8mj9b4WXC%2BzYOIrxwhDseNohJPggt5lYB8mBBdrG%2BHS4Q4aUVGriNxO3gTXMkHevA%2Bs4V%2BAc9wsF%2FEycatLTQoZB2Syj78N42nKhw3o7tD3tPcI4UcZSnK5z4qefDT5IjYDWQtP0Q5HBJMCOlqW5vIOqXvs0iY8k%2BSTYx12Cn9uICCVcVL%2BmyrXQTwitRebAHP5ESxfb2jqHa9L4ITxtbsWBr%2F5uJqvZ1C37EpqCX3k%2FWEn1PpGiJdt7YfHXAqWMv5ty8f6jG%2BUT3S1m%2FBw2uUkW3%2BsjS4DLRlUvPt8rQJQNROhBrpeBAeIOFoUaKcxpTzc95M4%2FqJZZ5oSMnOp1EfIGiDXlji3xtv8ifMY7qVfNA4NFLCTK9i5t6BsTSPgMNSDlc0GOpcBzxUzC8hReQzr4drPDx%2FvS2Y8HIc12ZiwIJSDnNJxmM0Vh5f%2Be%2FXJeaeNPQUGh4dI%2BjYH4ALNcruDGGnmXSqbDGP5Oouhdo%2F3YM2qHid2eSzl48ZkfIZhebKl1%2FyPiScssr3%2BDvtoSk20WffUWMqU9CSIpjKuFdSHK1CySPb5vLdZA%2BDguCrWU8wDUQNBY1slWaZqjD7JTA%3D%3D&Expires=1772443714)
