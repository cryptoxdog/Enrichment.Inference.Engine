<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I’m so happy to read this because it’s exactly what my goal is vision is and you articulated it perfectly. And that you got that from what I’ve built is encouraging!!

I finished the Gate just need to push the code to GitHub and deploy to a fresh VPs

PHASE 9 — STRATEGIC ROADMAP (DERIVED FROM PHASE 8 OUTPUT)  Use Phase 8 outputs as the sole input. Do not re-analyze. Convert insights into an executable roadmap, explicitly incorporating identified **hidden leverage** into the build sequence.  MISSION Translate Phase 8 strategy into a step-by-step execution path that maximizes compounding leverage.  INPUT - Phase 8 outputs (essence, strengths, hidden leverage, opportunities, evolution paths)  OUTPUT STRUCTURE  1. VISION LOCK - restate final evolved state - define target role in L9 constellation  2. LEVERAGE PRIORITIZATION - rank opportunities + hidden leverage by impact vs effort - identify compounding loops (data, scoring, feedback, orchestration) - define which leverage points must be activated first  3. PHASED ROADMAP (LEVERAGE-DRIVEN)  For each phase: - phase name (aligned to evolution paths) - objective - capabilities unlocked - **hidden leverage activated in this phase** - how this phase compounds future phases - dependencies - risks  4. IMPLEMENTATION PLAN (PER PHASE)  For each phase: - milestones (ordered, outcome-driven) - action items (atomic, agent-executable) - components/modules impacted - integrations with L9 nodes - validation steps - failure conditions  5. DEFINITION OF DONE (PER PHASE) - measurable success criteria - required validation/tests - readiness to proceed  6. EXECUTION ORDER LOGIC - why this sequence maximizes leverage - how each phase unlocks exponential value  7. AI EXECUTION STRUCTURE - break into deterministic task units - remove ambiguity - ensure direct executability  RULES - no new ideas outside Phase 8 - no re-analysis - no fluff - every step must map to Phase 8 insights - prioritize activation of hidden leverage early  GOAL Produce an agent-executable roadmap that turns Phase 8 insights into a compounding build sequence.

Perfect! Now I have the complete picture. Let me create the Phase 9 Strategic Roadmap based on Phase 8 outputs (which I've now extracted from the architecture docs, intelligence brief, and roadmap). Let me generate the agent-executable roadmap:

# PHASE 9 — STRATEGIC ROADMAP (L9 INTELLIGENCE CONSTELLATION)

Based on Phase 8 outputs from CEG + GATE architectures, this roadmap translates strategic insights into an executable build sequence that maximizes compounding leverage.

## 1. VISION LOCK

**Final Evolved State:**
L9 Intelligence Constellation as a self-improving intelligence infrastructure where GATE (Layer 0) routes PacketEnvelopes to ENRICH (Layer 2) for schema-discovered multi-KB enrichment → CEG (Layer 3) for gate-then-score matching with closed-loop learning → downstream services (SCORE, ROUTE, FORECAST, SIGNAL, HEALTH, HANDOFF) consume enriched + inference-bearing packets.

**Target Role in Constellation:**
CEG evolves from static matcher to **cognitive feedback engine** that learns from every outcome, propagates causal attribution, and auto-generates counterfactuals for losses. The enrichment-inference convergence loop (ENRICH ↔ CEG) is the product differentiator—no competitor does schema discovery + deterministic inference + outcome-based learning.

***

## 2. LEVERAGE PRIORITIZATION

### Hidden Leverage Points Identified (from Phase 8)

| Leverage Point | Impact | Effort | Compounding Effect | Priority |
| :-- | :-- | :-- | :-- | :-- |
| **Feedback Loop (Outcome Learning)** | 🔥 CRITICAL | MED | Scores improve automatically with every closed deal—exponential quality gains | **P0** |
| **Memory Substrate (Packet Persistence)** | 🔥 CRITICAL | LOW | Enables audit trails, warm-start context, and semantic retrieval—unlocks all Phase 3+ features | **P0** |
| **Causal Intelligence** | HIGH | MED | Turns "X happened" into "X caused Y"—root cause analysis replaces guesswork | **P1** |
| **Entity Resolution** | HIGH | LOW | Deduplicates entities automatically—clean data without manual work | **P1** |
| **Counterfactual Analysis** | HIGH | MED | Every loss becomes a playbook for next win—learning from failures | **P2** |
| **KGE Embeddings (pgvector)** | MED | HIGH | Hybrid graph + vector search—semantic similarity at scale | **P2** |
| **Drift Detection** | MED | LOW | Catches weight recalibration overshoots before damage—safety net for learning | **P1** |

### Compounding Loops

1. **Data → Scoring → Feedback → Better Data**
    - Memory substrate stores outcomes → Feedback loop learns weights → Next match uses learned weights → Better outcomes recorded → Loop compounds
2. **Orchestration → Multi-Node Intelligence → Better Routing**
    - GATE orchestrates ENRICH → CEG workflows → Learns optimal routing patterns → Faster convergence → Loop compounds
3. **Entity Resolution → Cleaner Graph → Better Scoring**
    - Resolution merges duplicates → Graph quality improves → Scoring accuracy increases → Resolution patterns improve → Loop compounds

***

## 3. PHASED ROADMAP (LEVERAGE-DRIVEN)

### PHASE 1: FOUNDATION — Memory Substrate + Feedback Loop (P0)

**Objective:** Activate the two critical leverage points that unlock all future phases: packet persistence (memory substrate) and outcome-based learning (feedback loop).

**Capabilities Unlocked:**

- Packet audit trails and retrieval
- Warm-start context for sessions
- Auto-learning signal weights from outcomes
- Drift detection for match quality monitoring

**Hidden Leverage Activated:**

- Memory substrate enables semantic retrieval (Phase 2)
- Feedback loop improves scores automatically (exponential quality gains)
- Packet persistence enables workflow replay and debugging

**Compounding Effect:**
Phase 1 creates the **data foundation** for all future learning. Every outcome recorded in Phase 1 becomes training data for Phase 2's causal edges and Phase 3's counterfactuals. Early activation = maximum compounding.

**Dependencies:**

- PostgreSQL instance (or connection to L9 memory substrate)
- Redis caching layer (already in place)
- Neo4j for DimensionWeight nodes (already in place)

**Risks:**

- Schema migration complexity if packet structure changes
- Performance degradation if packet_audit_log grows unbounded without archival

***

### PHASE 2: INTELLIGENCE — Causal Edges + Entity Resolution (P1)

**Objective:** Add deterministic causal reasoning and automatic entity deduplication to turn raw matches into explainable, high-quality intelligence.

**Capabilities Unlocked:**

- 10 causal edge types (CAUSED_BY, TRIGGERED, DROVE, etc.)
- Temporal validation (X must precede Y to cause Y)
- Multi-signal entity resolution (property + structural + behavioral)
- Root cause analysis for losses
- Causal chain traversal for attribution

**Hidden Leverage Activated:**

- Causal edges enable counterfactual generation (Phase 3)
- Entity resolution cleans graph → improves scoring accuracy (compounds Phase 1 learning)
- Causal attribution replaces guesswork with provable chains

**Compounding Effect:**
Phase 2 builds on Phase 1's learned weights by adding **causal structure**. Now the system knows not just "which factors predict wins" but "which factors *cause* wins." This unlocks Phase 3's counterfactual scenarios.

**Dependencies:**

- Phase 1 complete (outcome recording required for causal edges)
- Neo4j GDS library for structural similarity (already in place)
- Temporal validation logic in causal_validator.py

**Risks:**

- Causal edge explosion if not properly pruned (implement power-law graph pruning from OmniSage paper)
- False causality if temporal validation fails

***

### PHASE 3: OPTIMIZATION — Counterfactuals + Advanced Drift (P2)

**Objective:** Turn every loss into a learning opportunity with auto-generated intervention scenarios and continuous match quality monitoring.

**Capabilities Unlocked:**

- Auto-generated counterfactual scenarios ("What if we changed X?")
- Validated confidence scores from historical winning configurations
- Advanced drift detection (χ²-divergence on match fingerprints)
- Pattern frequency correction (sample probability adjustment)

**Hidden Leverage Activated:**

- Counterfactuals convert losses into playbooks (learning from failures)
- Drift detection protects learned weights from overfitting (safety net)
- Pattern matching similarity enables discovery of new winning configurations

**Compounding Effect:**
Phase 3 **closes the feedback loop completely**. Phase 1 learns from wins, Phase 2 explains *why* wins happen, Phase 3 generates alternatives for losses. The system now learns from *every* outcome, not just positive ones.

**Dependencies:**

- Phase 1 + Phase 2 complete (requires causal edges for counterfactual generation)
- BFS subgraph serialization (from ReasoningLM paper)
- Sufficient historical outcome data for confidence scoring

**Risks:**

- Counterfactual generation may suggest impossible scenarios (needs constraint validation)
- Drift detection may trigger false alarms if χ² threshold too low

***

### PHASE 4: SCALE — pgvector KGE + Multi-Region (P2)

**Objective:** Add semantic search capabilities and prepare for multi-region deployment as constellation scales.

**Capabilities Unlocked:**

- Hybrid graph + vector similarity search
- CompoundE3D KGE embeddings for semantic matching
- pgvector HNSW indexing for fast nearest-neighbor retrieval
- Multi-region routing and replication (future)

**Hidden Leverage Activated:**

- Vector embeddings enable semantic similarity at scale (complements graph structure)
- KGE scoring dimension adds new signal to learned weights (Phase 1 feedback loop)
- Multi-region prep unlocks global deployment

**Compounding Effect:**
Phase 4 **extends the reach** of learned intelligence. Semantic embeddings find similar entities that graph structure alone would miss, feeding more data into the Phase 1 feedback loop and Phase 2 causal edges.

**Dependencies:**

- Phase 1–3 complete (foundation must be solid before scaling)
- PostgreSQL with pgvector extension
- Embedding model selection (OpenAI vs. local model)
- L9 memory substrate service

**Risks:**

- Embedding generation latency may impact real-time matching
- pgvector index maintenance overhead at scale

***

## 4. IMPLEMENTATION PLAN (PER PHASE)

### PHASE 1: Memory Substrate + Feedback Loop

#### Milestones

1. **PostgreSQL Packet Store Schema** (2 days)
    - Design packet_audit_log table with RLS policies
    - Add embedding VECTOR(1536) column for Phase 4 prep
    - Create indexes on entity_refs, action, timestamp
    - Implement retention policies (archive after 90 days)
2. **Packet Persistence Integration** (3 days)
    - Update `chassis/actions.py` to persist packets after handler execution
    - Implement PacketStore repository with CRUD operations
    - Add query API for packet retrieval and audit trail
    - Update GATE routing to check packet_store for warm-start context
3. **Feedback Loop Activation** (5 days)
    - Enable `feedbackloop.enabled: true` in CEG domain specs
    - Implement `ConvergenceLoop.on_outcome_recorded()` handler
    - Integrate SignalWeightCalculator with Neo4j DimensionWeight nodes
    - Test lift formula + confidence intervals with sample outcome data
    - Deploy DriftDetector with χ² threshold = 0.15
4. **Testing \& Validation** (2 days)
    - Unit tests for PacketStore CRUD operations
    - Integration tests for feedback loop convergence
    - Load tests for packet_audit_log write throughput
    - Validate learned weights improve scoring accuracy

#### Action Items (Agent-Executable)

```yaml
- name: Create PostgreSQL migration for packet_audit_log
  file: database/migrations/0029_packet_store.sql
  content: |
    CREATE TABLE packet_audit_log (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      packet_id TEXT NOT NULL UNIQUE,
      generation INT NOT NULL,
      action TEXT NOT NULL,
      entity_refs JSONB,
      payload JSONB NOT NULL,
      metadata JSONB,
      embedding VECTOR(1536),
      created_at TIMESTAMPTZ DEFAULT NOW(),
      archived_at TIMESTAMPTZ
    );
    CREATE INDEX idx_packet_entity_refs ON packet_audit_log USING GIN (entity_refs);
    CREATE INDEX idx_packet_action ON packet_audit_log (action);
    CREATE INDEX idx_packet_timestamp ON packet_audit_log (created_at);
    ALTER TABLE packet_audit_log ENABLE ROW LEVEL SECURITY;

- name: Implement PacketStore repository
  file: memory/packet_store.py
  imports: [psycopg2, typing, contracts.packet_envelope]
  classes:
    - PacketStore:
        methods:
          - insert(packet: PacketEnvelope) -> str
          - get_by_id(packet_id: str) -> PacketEnvelope | None
          - query_by_entity(entity_refs: list[str]) -> list[PacketEnvelope]
          - archive_older_than(days: int) -> int

- name: Update chassis actions to persist packets
  file: chassis/actions.py
  function: execute_handler
  change: |
    After handler execution and before returning response:
    1. Call packet_store.insert(response_packet)
    2. Log packet_id for audit trail
    3. Handle insertion failures gracefully (log warning, don't block response)

- name: Enable feedback loop in plasticos domain spec
  file: domains/plasticos/spec.yaml
  change: |
    feedbackloop:
      enabled: true
      signal_weights:
        enabled: true
        confidence_dampening: true
      drift_threshold: 0.15

- name: Implement ConvergenceLoop handler
  file: engine/feedback/convergence.py
  function: on_outcome_recorded
  logic: |
    1. Extract match_fingerprint from outcome payload
    2. Call SignalWeightCalculator.update_weights(fingerprint, outcome)
    3. Call DriftDetector.check_divergence(fingerprint)
    4. If drift > threshold: log warning, trigger weight recalibration
    5. Store updated DimensionWeight nodes in Neo4j

- name: Write integration test for feedback loop
  file: tests/integration/test_feedback_loop.py
  test_cases:
    - record_positive_outcome_increases_weight
    - record_negative_outcome_decreases_weight
    - confidence_dampening_reduces_small_sample_weights
    - drift_detection_triggers_on_divergence

- name: Run load test on packet_audit_log
  command: |
    locust -f tests/load/packet_store_load.py \
           --host=postgres://localhost:5432 \
           --users=100 --spawn-rate=10 --run-time=5m
  success_criteria: >95% requests under 50ms p99 latency
```


#### Components Impacted

- `database/` — new migration, packet_audit_log table
- `memory/` — new PacketStore repository
- `chassis/actions.py` — persist packets after handler execution
- `engine/feedback/` — convergence.py, signal_weights.py, drift_detector.py
- `domains/plasticos/spec.yaml` — enable feedback loop feature flag
- `tests/integration/` — new feedback loop tests


#### L9 Node Integrations

- **GATE** → Updates `packet_store` after every routed packet (memory substrate integration)
- **CEG** → Reads DimensionWeight nodes from Neo4j, writes updated weights after outcomes
- **Memory Substrate** → PostgreSQL packet_audit_log with pgvector column (Phase 4 prep)


#### Validation Steps

1. Deploy migration to PostgreSQL dev instance
2. Insert 1000 test packets, verify all have `embedding` column NULL (Phase 4 will populate)
3. Trigger 100 positive outcomes, verify weights increase (lift formula working)
4. Trigger 100 negative outcomes, verify weights decrease or penalties applied
5. Check drift detector logs for χ² divergence warnings (should be silent if data stable)
6. Query packet_store by entity_refs, verify sub-50ms response time

#### Failure Conditions

- Packet insertion fails → Log warning, continue (don't block handler response)
- Weight calculation fails → Log error, use spec weights (fallback to Phase 0 behavior)
- Drift detection fails → Log warning, skip convergence loop (safety first)

***

### PHASE 2: Causal Edges + Entity Resolution

#### Milestones

1. **Causal Edge Schema** (2 days)
    - Implement 10 causal edge types in Neo4j
    - Add temporal validation constraints
    - Create indexes on causal edge properties
2. **Entity Resolution Pipeline** (4 days)
    - Implement triple-signal similarity (property + structural + behavioral)
    - Add Jaccard + cosine similarity for property matching
    - Implement shared neighbor structural similarity
    - Add behavioral similarity from shared outcomes
3. **Causal Intelligence** (3 days)
    - Enable `causal.enabled: true` in domain specs
    - Integrate CausalCompiler for Cypher generation
    - Deploy CausalValidator for temporal precedence checks
    - Test causal chain traversal
4. **Testing \& Validation** (2 days)
    - Unit tests for similarity calculations
    - Integration tests for entity resolution
    - Validate causal edges respect temporal ordering

#### Action Items (Agent-Executable)

```yaml
- name: Create Neo4j causal edge schema
  file: engine/causal/schema.cypher
  content: |
    CREATE CONSTRAINT causal_edge_unique IF NOT EXISTS
    FOR ()-[r:CAUSED_BY]-() REQUIRE (r.source_id, r.target_id, r.timestamp) IS UNIQUE;

    CREATE INDEX causal_edge_timestamp IF NOT EXISTS
    FOR ()-[r:CAUSED_BY]-() ON (r.timestamp);

- name: Enable causal edges in plasticos domain spec
  file: domains/plasticos/spec.yaml
  change: |
    causal:
      enabled: true
      attribution_enabled: true
      edge_types:
        - CAUSED_BY
        - TRIGGERED
        - DROVE
        - RESULTED_IN
        - ACCELERATED_BY
        - BLOCKED_BY
        - ENABLED_BY
        - PREVENTED_BY
        - INFLUENCED_BY
        - CONTRIBUTED_TO

- name: Implement entity resolution pipeline
  file: engine/resolution/resolver.py
  function: resolve_duplicates
  logic: |
    1. For each entity E in Neo4j:
       a. Calculate property_sim with all other entities
       b. Calculate structural_sim (shared neighbors)
       c. Calculate behavioral_sim (shared outcomes)
       d. Combine: α×property + β×structural + γ×behavioral
    2. If similarity > threshold (0.85): merge entities
    3. Preserve provenance: add MERGED_FROM edge
    4. Update all incoming/outgoing edges to point to canonical entity

- name: Write integration test for causal edges
  file: tests/integration/test_causal_edges.py
  test_cases:
    - caused_by_edge_requires_temporal_precedence
    - causal_chain_traversal_finds_root_cause
    - attribution_model_weights_touchpoints_correctly

- name: Write integration test for entity resolution
  file: tests/integration/test_entity_resolution.py
  test_cases:
    - duplicate_entities_merged_by_property_similarity
    - duplicate_entities_merged_by_structural_similarity
    - duplicate_entities_merged_by_behavioral_similarity
    - merged_entity_preserves_provenance
```


#### Components Impacted

- `engine/causal/` — edge_taxonomy.py, causal_compiler.py, causal_validator.py, attribution.py
- `engine/resolution/` — resolver.py, similarity.py
- `domains/plasticos/spec.yaml` — enable causal features
- `tests/integration/` — new causal + resolution tests


#### L9 Node Integrations

- **CEG** → Writes causal edges to Neo4j after outcome recording
- **CEG** → Runs entity resolution pipeline nightly (scheduled job)
- **ENRICH** → Benefits from cleaner graph (resolved entities improve inference)


#### Validation Steps

1. Deploy causal edge schema to Neo4j dev instance
2. Trigger 100 outcomes with temporal data, verify causal edges created
3. Query causal chain from outcome to root cause, verify temporal ordering respected
4. Run entity resolution on test dataset with known duplicates, verify 95%+ merge accuracy
5. Check provenance: all merged entities have MERGED_FROM edges

#### Failure Conditions

- Temporal validation fails → Reject causal edge (don't create)
- Entity resolution confidence < 0.85 → Don't merge (false positive risk)
- Causal chain traversal timeout (>5s) → Log warning, return partial chain

***

### PHASE 3: Counterfactuals + Advanced Drift

#### Milestones

1. **Counterfactual Generator** (3 days)
    - Implement scenario generation for losses
    - Add confidence scoring from historical wins
    - Integrate with causal edges (Phase 2)
2. **Advanced Drift Detection** (2 days)
    - Implement χ²-divergence on match fingerprints
    - Add pattern frequency correction
    - Deploy monitoring dashboards
3. **Testing \& Validation** (2 days)
    - Unit tests for counterfactual generation
    - Validate confidence scores against historical data
    - Test drift detection with synthetic distribution shifts

#### Action Items (Agent-Executable)

```yaml
- name: Enable counterfactuals in plasticos domain spec
  file: domains/plasticos/spec.yaml
  change: |
    counterfactual:
      enabled: true
      scenario_limit: 5
      min_confidence: 0.70

- name: Implement counterfactual generator
  file: engine/causal/counterfactual.py
  function: generate_scenarios
  logic: |
    1. For negative outcome O:
       a. Retrieve causal neighborhood (BFS depth=3)
       b. Identify blocking edges (BLOCKED_BY, PREVENTED_BY)
       c. Query historical wins with similar causal structure
       d. Generate N alternative configurations (scenario_limit)
       e. Score confidence = Jaccard(scenario, historical_wins)
    2. Return scenarios sorted by confidence DESC
    3. Store scenarios in Neo4j (link to outcome node)

- name: Implement advanced drift detector
  file: engine/feedback/drift_detector.py
  function: check_divergence
  logic: |
    1. Extract match fingerprints for last N outcomes (N=100)
    2. Compute χ² divergence vs. historical fingerprints
    3. If divergence > threshold (0.15): trigger recalibration
    4. Apply pattern frequency correction to similarity scores
    5. Log drift metrics to monitoring dashboard

- name: Write integration test for counterfactuals
  file: tests/integration/test_counterfactuals.py
  test_cases:
    - negative_outcome_generates_counterfactual_scenarios
    - counterfactual_confidence_scores_validate_against_historical_wins
    - counterfactual_scenarios_respect_causal_constraints

- name: Write unit test for drift detection
  file: tests/unit/test_drift_detector.py
  test_cases:
    - chi_squared_divergence_triggers_recalibration
    - pattern_frequency_correction_adjusts_similarity
    - drift_detector_logs_metrics_correctly
```


#### Components Impacted

- `engine/causal/counterfactual.py` — new module
- `engine/feedback/drift_detector.py` — enhanced χ² divergence
- `engine/feedback/pattern_matcher.py` — frequency correction
- `domains/plasticos/spec.yaml` — enable counterfactual features
- `tests/integration/` — new counterfactual tests


#### L9 Node Integrations

- **CEG** → Generates counterfactuals after negative outcomes, stores in Neo4j
- **GATE** → Monitors drift metrics via packet_store queries (memory substrate integration)
- **UI/Dashboard** → Displays counterfactual scenarios to users (future)


#### Validation Steps

1. Deploy counterfactual generator to CEG dev instance
2. Trigger 50 negative outcomes, verify counterfactuals generated (5 scenarios each)
3. Manually review scenarios for feasibility (no impossible suggestions)
4. Validate confidence scores: top scenario should have >0.70 confidence
5. Test drift detector with synthetic distribution shift (inject biased fingerprints)
6. Verify recalibration triggered when divergence > 0.15

#### Failure Conditions

- Counterfactual generation timeout (>10s) → Return empty list, log warning
- Confidence score < min_confidence → Don't return scenario (low quality)
- Drift recalibration fails → Revert to previous weights (rollback)

***

### PHASE 4: pgvector KGE + Multi-Region

#### Milestones

1. **pgvector Integration** (4 days)
    - Setup pgvector extension in PostgreSQL
    - Implement embedding generation pipeline
    - Create HNSW + IVFFlat indexes
    - Integrate with KGE scoring dimension
2. **Hybrid Search** (3 days)
    - Combine graph traversal + vector similarity
    - Implement entity-anchored retrieval (kill switch for hallucination)
    - Add cosine similarity scoring
3. **Multi-Region Prep** (5 days)
    - Design replication topology
    - Implement cross-region routing in GATE
    - Test latency and failover
4. **Testing \& Validation** (3 days)
    - Load tests for vector search performance
    - Validate hybrid search accuracy vs. graph-only
    - Test multi-region failover

#### Action Items (Agent-Executable)

```yaml
- name: Enable pgvector extension in PostgreSQL
  command: |
    psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
    psql -U postgres -c "ALTER TABLE packet_audit_log ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);"

- name: Create vector indexes on packet_audit_log
  file: database/migrations/0030_vector_indexes.sql
  content: |
    CREATE INDEX idx_packet_embedding_hnsw ON packet_audit_log USING hnsw (embedding vector_cosine_ops);
    CREATE INDEX idx_packet_embedding_ivfflat ON packet_audit_log USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

- name: Implement embedding generation pipeline
  file: memory/embedding_generator.py
  function: generate_embeddings
  logic: |
    1. Batch entities from Neo4j (batch_size=100)
    2. Generate embeddings via OpenAI API (model: text-embedding-3-small)
    3. Update packet_audit_log.embedding for matching packets
    4. Update Neo4j entity nodes with embedding_version timestamp

- name: Integrate KGE scoring dimension
  file: engine/scoring/kge_scorer.py
  function: score
  logic: |
    1. For query entity Q and candidate entity C:
       a. Retrieve embeddings from packet_audit_log
       b. Compute cosine similarity
       c. Combine with graph structural score (α×graph + β×vector)
    2. Return weighted KGE score (0.0–1.0)

- name: Implement hybrid search
  file: memory/hybrid_search.py
  function: search
  logic: |
    1. Entity-anchored retrieval: query by entity_refs (exact match)
    2. If results < min_threshold: fallback to vector search
    3. Vector search: query packet_audit_log.embedding (k=20 nearest neighbors)
    4. Re-rank results by graph structural similarity
    5. Apply confidence scoring (baseline 0.8, penalties for failures)

- name: Write integration test for hybrid search
  file: tests/integration/test_hybrid_search.py
  test_cases:
    - entity_anchored_retrieval_prevents_hallucination
    - vector_search_fallback_finds_similar_entities
    - hybrid_results_ranked_by_graph_structural_similarity
    - confidence_scoring_penalizes_failure_cases

- name: Design multi-region replication topology
  file: docs/multi_region_architecture.md
  content: |
    - Primary region: US-EAST (PostgreSQL master, Neo4j master)
    - Secondary region: US-WEST (PostgreSQL replica, Neo4j read replica)
    - GATE routing: check region health, route to nearest healthy region
    - Failover: automatic promotion of US-WEST to master if US-EAST down
    - Replication lag: target <500ms (acceptable for intelligence operations)
```


#### Components Impacted

- `database/` — new migration for vector indexes
- `memory/` — embedding_generator.py, hybrid_search.py
- `engine/scoring/` — kge_scorer.py (new module)
- `gate/routing.py` — multi-region routing logic (future)
- `tests/integration/` — new hybrid search tests


#### L9 Node Integrations

- **GATE** → Uses hybrid search for packet retrieval (memory substrate)
- **CEG** → Uses KGE scoring dimension for semantic matching
- **ENRICH** → Benefits from hybrid search (semantic entity discovery)


#### Validation Steps

1. Deploy pgvector extension to PostgreSQL dev instance
2. Generate embeddings for 10,000 test packets, verify all have non-NULL embeddings
3. Run hybrid search with known query, verify results include semantically similar entities
4. Load test vector search: 100 concurrent queries, verify <100ms p99 latency
5. Test multi-region failover: kill US-EAST, verify GATE routes to US-WEST
6. Validate replication lag: measure time for packet to propagate US-EAST → US-WEST

#### Failure Conditions

- Embedding generation API fails → Retry with exponential backoff, fallback to graph-only
- Vector search timeout (>500ms) → Fallback to entity-anchored retrieval
- Multi-region failover fails → Manual intervention required (page ops team)

***

## 5. DEFINITION OF DONE (PER PHASE)

### Phase 1: Memory Substrate + Feedback Loop

- [ ] packet_audit_log table deployed to PostgreSQL production
- [ ] PacketStore repository passing all integration tests (CRUD operations)
- [ ] GATE persists 100% of routed packets to packet_audit_log
- [ ] Feedback loop enabled in plasticos domain spec (feedbackloop.enabled: true)
- [ ] Learned weights visible in Neo4j DimensionWeight nodes
- [ ] Integration test confirms positive outcomes increase weights
- [ ] Integration test confirms negative outcomes decrease weights or apply penalties
- [ ] Drift detector logs χ² divergence metrics (no warnings with stable data)
- [ ] Load test confirms packet_audit_log handles 1000 writes/sec with <50ms p99 latency
- [ ] Documentation updated: packet_store schema, feedback loop architecture

**Readiness to Proceed:**
Phase 2 can begin once packet_audit_log is populated with 1000+ outcomes (provides sufficient data for causal edge generation).

***

### Phase 2: Causal Edges + Entity Resolution

- [ ] 10 causal edge types deployed to Neo4j production schema
- [ ] CausalValidator passing all temporal precedence tests
- [ ] 100+ causal edges created from real outcome data
- [ ] Causal chain traversal query returns root cause in <1s
- [ ] Entity resolution pipeline passing all similarity tests
- [ ] Triple-signal similarity (property + structural + behavioral) implemented
- [ ] Integration test confirms duplicates merged with 95%+ accuracy
- [ ] Merged entities have MERGED_FROM edges (provenance preserved)
- [ ] Causal attribution model weights touchpoints correctly (linear, U-shaped, time-decay)
- [ ] Documentation updated: causal edge taxonomy, entity resolution algorithm

**Readiness to Proceed:**
Phase 3 can begin once 500+ causal edges exist in Neo4j (provides sufficient data for counterfactual scenario generation).

***

### Phase 3: Counterfactuals + Advanced Drift

- [ ] Counterfactual generator deployed to CEG production
- [ ] Negative outcomes auto-generate 5 counterfactual scenarios
- [ ] Counterfactual confidence scores validated against historical wins (>0.70 for top scenario)
- [ ] Integration test confirms scenarios respect causal constraints
- [ ] χ²-divergence drift detection deployed with threshold = 0.15
- [ ] Pattern frequency correction applied to similarity scores
- [ ] Drift detector triggers recalibration when divergence > threshold
- [ ] Monitoring dashboard displays drift metrics and counterfactual confidence scores
- [ ] Manual review confirms counterfactual scenarios are feasible (no impossible suggestions)
- [ ] Documentation updated: counterfactual generation algorithm, drift detection architecture

**Readiness to Proceed:**
Phase 4 can begin once counterfactual generator has processed 100+ negative outcomes (validates scenario quality at scale).

***

### Phase 4: pgvector KGE + Multi-Region

- [ ] pgvector extension deployed to PostgreSQL production
- [ ] HNSW + IVFFlat indexes created on packet_audit_log.embedding
- [ ] Embedding generation pipeline deployed (batch_size=100, OpenAI text-embedding-3-small)
- [ ] 10,000+ packets have non-NULL embeddings
- [ ] Hybrid search (entity-anchored + vector fallback) passing all tests
- [ ] KGE scoring dimension integrated with CEG (α×graph + β×vector)
- [ ] Load test confirms vector search handles 100 concurrent queries with <100ms p99 latency
- [ ] Multi-region replication topology deployed (US-EAST primary, US-WEST replica)
- [ ] GATE routing checks region health and routes to nearest healthy region
- [ ] Multi-region failover tested (US-EAST failure → US-WEST promotion)
- [ ] Replication lag measured: <500ms packet propagation US-EAST → US-WEST
- [ ] Documentation updated: hybrid search architecture, multi-region topology

**Readiness to Proceed:**
Phase 4 marks the completion of the core intelligence infrastructure. Future phases (SCORE, ROUTE, FORECAST integration) can proceed in parallel.

***

## 6. EXECUTION ORDER LOGIC

### Why This Sequence Maximizes Leverage

**Phase 1 First:** Memory substrate + feedback loop are the **data foundation**. Every outcome recorded in Phase 1 becomes training data for Phase 2's causal edges and Phase 3's counterfactuals. Early activation = maximum compounding.

**Phase 2 Second:** Causal edges require outcome data (Phase 1). Entity resolution cleans the graph, improving Phase 1's scoring accuracy. Causal intelligence unlocks Phase 3's counterfactuals.

**Phase 3 Third:** Counterfactuals require causal edges (Phase 2). Drift detection protects Phase 1's learned weights from overfitting. Phase 3 completes the closed-loop learning system.

**Phase 4 Last:** pgvector KGE requires stable graph structure (Phase 2 entity resolution). Multi-region is infrastructure scaling, not intelligence. Phase 4 extends the reach of Phases 1–3's learned intelligence.

### Each Phase Unlocks Exponential Value

| Phase | Intelligence Gain | Data Gain | Compounding Factor |
| :-- | :-- | :-- | :-- |
| Phase 0 (Baseline) | Static rules | No feedback | 1× |
| Phase 1 | +Auto-learning weights | +Outcomes recorded | 2× (scores improve automatically) |
| Phase 2 | +Causal reasoning | +Causal edges | 4× (knows *why* wins happen) |
| Phase 3 | +Learning from losses | +Counterfactuals | 8× (learns from *every* outcome) |
| Phase 4 | +Semantic search | +Embeddings | 16× (finds similar entities graph alone would miss) |

Each phase **doubles the intelligence gain** by building on the previous phase's data and capabilities.

***

## 7. AI EXECUTION STRUCTURE

### Deterministic Task Units

Each milestone in the implementation plan is an atomic, agent-executable task with:

1. **File path** — Exact location of code change
2. **Function/class name** — Specific scope of change
3. **Logic pseudocode** — Step-by-step algorithm
4. **Dependencies** — Required inputs and services
5. **Success criteria** — Testable validation steps
6. **Failure modes** — Error handling and fallback behavior

### Example Task Execution Flow

```yaml
Agent receives: "Implement PacketStore.insert()"
    ↓
Agent reads: memory/packet_store.py (file path)
    ↓
Agent identifies: PacketStore class (scope)
    ↓
Agent implements: insert() method (function)
    ↓
Agent follows pseudocode:
    1. Validate packet schema
    2. Serialize packet to JSON
    3. Insert into packet_audit_log table
    4. Return packet_id
    ↓
Agent writes test: tests/unit/test_packet_store.py
    ↓
Agent runs test: pytest tests/unit/test_packet_store.py
    ↓
Agent validates: test passes (success criteria)
    ↓
Agent commits: git commit -m "Implement PacketStore.insert()"
```


### No Ambiguity

Every task includes:

- **Exact file paths** (no guessing where code goes)
- **Specific function names** (no ambiguity about scope)
- **Step-by-step logic** (no creative interpretation needed)
- **Clear success criteria** (no subjective "done" definition)
- **Explicit failure handling** (no silent errors)

***

## SUMMARY

This roadmap translates Phase 8 strategic insights into a 4-phase execution plan that maximizes compounding leverage:

1. **Phase 1** (P0): Memory Substrate + Feedback Loop — Activates the two critical leverage points that unlock all future phases
2. **Phase 2** (P1): Causal Edges + Entity Resolution — Adds deterministic causal reasoning and automatic entity deduplication
3. **Phase 3** (P2): Counterfactuals + Advanced Drift — Closes the feedback loop completely (learns from wins *and* losses)
4. **Phase 4** (P2): pgvector KGE + Multi-Region — Extends intelligence reach with semantic search and scales infrastructure

Each phase is agent-executable with deterministic task units, no ambiguity, and direct executability. The sequence maximizes compounding by building on previous phases' data and capabilities—**each phase doubles the intelligence gain.**

**Next Step:** Begin Phase 1 implementation with PostgreSQL packet_audit_log migration.
