# Belief Propagation Engine — Integration Spec

## Overview

This document defines the exact integration contracts for embedding the
`belief_propagation` engine into two L9 constellation repositories:

1. **CEG (Candidate Enrichment Graph)** — candidate re-scoring before Pareto gate
2. **GATE (Graph Traversal Engine)** — hop trace quality assessment

---

## CEG Integration

### Where to insert

File: `app/engines/ceg_match_engine.py`
Phase: After Neo4j candidate query, **before** GMP-05 Pareto ranking.

### Drop-in code

```python
from app.engines.belief_propagation import rescore_candidates

# After neo4j_result is available:
candidates = rescore_candidates(
    candidates=neo4j_result["candidates"],
    dimension_keys=["geo_score", "community_score", "temporal_score", "price_score"],
    prior_key="confidence",
    score_key="belief_score",
)
# candidates is now sorted descending by belief_score
# Pass directly into GMP-05 Pareto
```

### Contract guarantees

- Input dicts are **never mutated** (PacketEnvelope immutability)
- Output is sorted **descending** by `belief_score`
- `belief_score` is a float in `[0.0, 1.0]`
- Missing `prior_key` defaults to uniform prior (0.5)
- Missing dimension keys default to `TRUST_NEUTRAL` (0.60)
- Deterministic: identical inputs → identical outputs → identical content hash

---

## GATE Integration

### Where to insert

File: `app/engines/gate_traversal_engine.py`
Phase: After hop sequence completes, before writing `intelligence_quality` to payload.

### Drop-in code

```python
from app.engines.belief_propagation import (
    BayesianBeliefState,
    HopEntry,
    HopStatus,
    chain_composite,
    chain_propagation,
    hop_trust_from_entry,
)

# Build HopEntry list from completed trace
hop_entries = [
    HopEntry(
        hop_id=h["hop_id"],
        status=HopStatus(h["status"]),
        duration_ms=h["duration_ms"],
        timeout_ms=h["timeout_ms"],
        node_type=h["node_type"],
    )
    for h in trace["hops"]
]

# Derive trust scalars
trust_scores = [hop_trust_from_entry(h) for h in hop_entries]

# Compute chain quality metrics
prior = BayesianBeliefState(mu=0.5, entropy=1.0, n_observations=0)
terminal_belief = chain_propagation(trust_scores=trust_scores, prior=prior)
path_quality = chain_composite(trust_scores=trust_scores, prior=prior)

# Write to PacketEnvelope via .derive() to preserve immutability
payload = payload.derive({
    "intelligence_quality": {
        "chain_confidence": terminal_belief.posterior_score,
        "chain_composite": path_quality,
        "n_hops": len(hop_entries),
    }
})
```

### Contract guarantees

- Trust scalars derived from `HopStatus` tier mapping (not raw confidence fields)
- Timeout penalty fires at `duration_ms / timeout_ms > 0.5`
- `chain_confidence` = terminal `posterior_score` (mu − entropy, clamped to [0,1])
- `chain_composite` = entropy-penalised terminal belief after full chain
- **Use `.derive()` — never mutate the payload dict directly**

---

## Ordering Contract (CEG)

```
Neo4j query result
    → rescore_candidates()       ← belief propagation (multi-parent, independent dims)
    → sorted by belief_score     ← descending
    → GMP-05 Pareto gate         ← operates on belief-ranked candidates
    → final match output
```

## Ordering Contract (GATE)

```
Hop trace complete
    → hop_trust_from_entry()     ← per-hop trust derivation
    → chain_propagation()        ← causal chain (ordered hops)
    → chain_composite()          ← entropy-penalised path quality scalar
    → payload.derive()           ← immutable PacketEnvelope update
    → downstream consumers
```

---

## Definition of Done

- [ ] `rescore_candidates` called after Neo4j query, before Pareto in CEG
- [ ] `chain_propagation` + `chain_composite` called after hop trace in GATE
- [ ] No direct payload mutation — all writes via `.derive()`
- [ ] `test_belief_propagation.py` passes: 10 classes, 57 tests, zero skips
- [ ] `test_high_leverage.py` passes: 10 ranked classes, zero skips
- [ ] `ruff check app/engines/belief_propagation.py` — zero violations
- [ ] `mypy app/engines/belief_propagation.py --strict` — zero errors
- [ ] Both test files pass under `pytest -v --tb=short`
