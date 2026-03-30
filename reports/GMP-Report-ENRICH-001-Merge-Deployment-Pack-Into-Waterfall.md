# GMP-Report-ENRICH-001: Merge Enrichment-Deployment-Pack Into WaterfallEngine

**GMP ID:** ENRICH-001
**Title:** Merge Enrichment-Deployment-Pack Into Existing WaterfallEngine
**Tier:** RUNTIME_TIER
**Date:** 2026-03-30
**Status:** PLANNED

---

## Executive Summary

Merge the unique capabilities from `Enrichment-Deployment-pack/` into the existing `app/services/enrichment/` infrastructure. This preserves L9 contract compliance while adding:

- **Consensus Engine** — Multi-response synthesis from parallel Perplexity calls
- **Uncertainty Engine** — Confidence thresholds and flagging
- **KB Resolver** — Knowledge base context injection for prompts
- **Prompt Variation Builder** — N-variation prompt generation
- **Circuit Breaker** — Failure threshold with cooldown (enhance existing)

---

## Scope Boundaries

### IN SCOPE

| Item | Description |
|------|-------------|
| Extract consensus logic | `consensus_engine.py` → `app/services/enrichment/consensus.py` |
| Extract uncertainty logic | `uncertainty_engine.py` → `app/services/enrichment/uncertainty.py` |
| Extract KB resolver | `kb_resolver.py` → `app/services/enrichment/kb_resolver.py` |
| Extract prompt builder | `prompt_builder.py` → enhance existing `app/services/prompt_builder.py` |
| Enhance WaterfallEngine | Add consensus/uncertainty phases to `enrich()` method |
| Add new handler action | `handle_enrich_consensus` for multi-variation enrichment |
| Tests | Unit + integration tests for new modules |

### OUT OF SCOPE

| Item | Reason |
|------|--------|
| Standalone FastAPI app | Violates L9 Contract 1 |
| Separate deployment | Single enrichment service, not two |
| CI/CD workflows from pack | Use existing repo CI/CD |
| AI review script | Can be extracted separately if needed |

---

## Phase 0: TODO Plan (LOCKED)

### TODO-01: Create Consensus Engine Module
**File:** `app/services/enrichment/consensus.py`
**Action:** CREATE
**Lines:** ~80-100
**Dependencies:** None

```python
# Synthesizes multiple enrichment responses into a single consensus result
# Inputs: list of validated responses, threshold, total_attempted
# Outputs: dict with fields, confidence, agreement_ratio
```

### TODO-02: Create Uncertainty Engine Module
**File:** `app/services/enrichment/uncertainty.py`
**Action:** CREATE
**Lines:** ~60-80
**Dependencies:** None

```python
# Applies confidence thresholds and generates uncertainty flags
# Inputs: fields dict, confidence float
# Outputs: (filtered_fields, adjusted_confidence, flags list)
```

### TODO-03: Create KB Resolver Module
**File:** `app/services/enrichment/kb_resolver.py`
**Action:** CREATE
**Lines:** ~100-120
**Dependencies:** None

```python
# Resolves knowledge base context for enrichment prompts
# Loads KB fragments from YAML/JSON files
# Returns context dict with fragment_ids, context_text
```

### TODO-04: Enhance Prompt Builder for Variations
**File:** `app/services/prompt_builder.py`
**Action:** MODIFY
**Lines:** Add ~40-60 lines
**Dependencies:** TODO-03

```python
# Add build_variation_prompts() function
# Generates N prompt variations with different angles/phrasings
# Uses KB context for domain-specific terminology
```

### TODO-05: Enhance WaterfallEngine with Consensus Phase
**File:** `app/services/enrichment/waterfall_engine.py`
**Action:** MODIFY
**Lines:** ~180-244 (enrich method)
**Dependencies:** TODO-01, TODO-02

```python
# Add optional consensus_mode parameter
# When enabled: fan-out N variations → validate → consensus → uncertainty
# Integrate with existing quality scoring
```

### TODO-06: Add handle_enrich_consensus Handler
**File:** `app/engines/handlers.py`
**Action:** MODIFY
**Lines:** Add ~30-40 lines after handle_enrich
**Dependencies:** TODO-05

```python
# New handler: handle_enrich_consensus
# Payload: entity, kb_context, max_variations, consensus_threshold
# Calls WaterfallEngine.enrich() with consensus_mode=True
```

### TODO-07: Register New Handler
**File:** `app/engines/handlers.py`
**Action:** MODIFY
**Lines:** ~293-302 (get_handler_map)
**Dependencies:** TODO-06

```python
# Add "enrich_consensus": handle_enrich_consensus to handler map
```

### TODO-08: Update Package Exports
**File:** `app/services/enrichment/__init__.py`
**Action:** MODIFY
**Lines:** 1-15
**Dependencies:** TODO-01, TODO-02, TODO-03

```python
# Add exports: ConsensusEngine, UncertaintyEngine, KBResolver
```

### TODO-09: Create Unit Tests for Consensus
**File:** `tests/unit/services/enrichment/test_consensus.py`
**Action:** CREATE
**Lines:** ~100-150
**Dependencies:** TODO-01

```python
# Test synthesize() with various input scenarios
# Test threshold behavior
# Test edge cases (empty input, single response, all disagreement)
```

### TODO-10: Create Unit Tests for Uncertainty
**File:** `tests/unit/services/enrichment/test_uncertainty.py`
**Action:** CREATE
**Lines:** ~80-100
**Dependencies:** TODO-02

```python
# Test apply_uncertainty() with various confidence levels
# Test flag generation
# Test field filtering
```

### TODO-11: Create Unit Tests for KB Resolver
**File:** `tests/unit/services/enrichment/test_kb_resolver.py`
**Action:** CREATE
**Lines:** ~100-120
**Dependencies:** TODO-03

```python
# Test resolve() with various KB contexts
# Test missing KB handling
# Test fragment loading
```

### TODO-12: Create Integration Test for Consensus Enrichment
**File:** `tests/integration/test_consensus_enrichment.py`
**Action:** CREATE
**Lines:** ~150-200
**Dependencies:** TODO-05, TODO-06

```python
# End-to-end test: handle_enrich_consensus → WaterfallEngine → consensus
# Mock Perplexity responses
# Verify consensus output structure
```

### TODO-13: Add KB Test Fixtures
**File:** `tests/fixtures/kb/plastics_kb.yaml`
**Action:** CREATE
**Lines:** ~50-80
**Dependencies:** TODO-03

```yaml
# Sample KB for plastics domain
# polymer_types, grades, applications, terminology
```

### TODO-14: Update Enrichment Package Documentation
**File:** `app/services/enrichment/README.md`
**Action:** CREATE
**Lines:** ~80-100
**Dependencies:** All above

```markdown
# Document new consensus/uncertainty/KB features
# Usage examples
# Configuration options
```

---

## Phase 1: Baseline Confirmation

Before implementation, verify:

- [ ] `app/services/enrichment/waterfall_engine.py` exists and is functional
- [ ] `app/services/enrichment/quality_scorer.py` exists and is functional
- [ ] `app/engines/handlers.py` has working `handle_enrich` handler
- [ ] Existing tests pass: `pytest tests/unit/services/enrichment/ -v`
- [ ] No import cycles in enrichment package

**Baseline Command:**
```bash
pytest tests/unit/services/enrichment/ tests/integration/ -v --tb=short -k "enrich"
```

---

## Phase 2: Implementation Order

| Order | TODO | Rationale |
|-------|------|-----------|
| 1 | TODO-01 | Consensus engine is standalone, no deps |
| 2 | TODO-02 | Uncertainty engine is standalone, no deps |
| 3 | TODO-03 | KB resolver is standalone, no deps |
| 4 | TODO-09 | Test consensus before integration |
| 5 | TODO-10 | Test uncertainty before integration |
| 6 | TODO-11 | Test KB resolver before integration |
| 7 | TODO-13 | KB fixtures needed for integration |
| 8 | TODO-04 | Prompt builder needs KB resolver |
| 9 | TODO-05 | WaterfallEngine needs consensus + uncertainty |
| 10 | TODO-06 | Handler needs enhanced WaterfallEngine |
| 11 | TODO-07 | Register handler |
| 12 | TODO-08 | Update exports |
| 13 | TODO-12 | Integration test |
| 14 | TODO-14 | Documentation |

---

## Phase 3: Enforcement

### L9 Contract Compliance Checklist

- [ ] **Contract 1:** No FastAPI imports in new modules
- [ ] **Contract 2:** Handler signature: `async def handle_X(tenant: str, payload: dict) -> dict`
- [ ] **Contract 4:** Use `structlog.get_logger(__name__)` only
- [ ] **Contract 9:** No f-string Cypher (N/A for this GMP)
- [ ] **Contract 12:** Domain spec patterns followed
- [ ] **Contract 17:** Tests added for all new modules

### Code Quality Checklist

- [ ] Type hints on all function signatures
- [ ] Pydantic models for structured data
- [ ] Async/await for all I/O
- [ ] No bare except clauses
- [ ] Error messages use `msg = ...; raise ValueError(msg)` pattern

---

## Phase 4: Validation

### Test Commands

```bash
# Unit tests for new modules
pytest tests/unit/services/enrichment/test_consensus.py -v
pytest tests/unit/services/enrichment/test_uncertainty.py -v
pytest tests/unit/services/enrichment/test_kb_resolver.py -v

# Integration test
pytest tests/integration/test_consensus_enrichment.py -v

# Full enrichment test suite
pytest tests/unit/services/enrichment/ tests/integration/ -v -k "enrich"

# Lint check
ruff check app/services/enrichment/ --select=ALL
ruff format --check app/services/enrichment/

# Type check
mypy app/services/enrichment/ --strict
```

### Expected Outcomes

| Test Suite | Expected |
|------------|----------|
| test_consensus.py | 5+ tests pass |
| test_uncertainty.py | 4+ tests pass |
| test_kb_resolver.py | 5+ tests pass |
| test_consensus_enrichment.py | 3+ tests pass |
| Lint | 0 errors |
| Type check | 0 errors |

---

## Phase 5: Recursive Verification

### Scope Drift Check

| Original TODO | Final Implementation | Drift? |
|---------------|---------------------|--------|
| TODO-01 | consensus.py created | ❌ No |
| TODO-02 | uncertainty.py created | ❌ No |
| TODO-03 | kb_resolver.py created | ❌ No |
| TODO-04 | prompt_builder.py enhanced | ❌ No |
| TODO-05 | waterfall_engine.py enhanced | ❌ No |
| TODO-06 | handle_enrich_consensus added | ❌ No |
| TODO-07 | Handler registered | ❌ No |
| TODO-08 | Exports updated | ❌ No |
| TODO-09-13 | Tests created | ❌ No |
| TODO-14 | README created | ❌ No |

### Files Modified (Expected)

| File | Action | Lines Changed |
|------|--------|---------------|
| `app/services/enrichment/consensus.py` | CREATE | ~80-100 |
| `app/services/enrichment/uncertainty.py` | CREATE | ~60-80 |
| `app/services/enrichment/kb_resolver.py` | CREATE | ~100-120 |
| `app/services/prompt_builder.py` | MODIFY | +40-60 |
| `app/services/enrichment/waterfall_engine.py` | MODIFY | +50-70 |
| `app/engines/handlers.py` | MODIFY | +35-45 |
| `app/services/enrichment/__init__.py` | MODIFY | +10-15 |
| `tests/unit/services/enrichment/test_consensus.py` | CREATE | ~100-150 |
| `tests/unit/services/enrichment/test_uncertainty.py` | CREATE | ~80-100 |
| `tests/unit/services/enrichment/test_kb_resolver.py` | CREATE | ~100-120 |
| `tests/integration/test_consensus_enrichment.py` | CREATE | ~150-200 |
| `tests/fixtures/kb/plastics_kb.yaml` | CREATE | ~50-80 |
| `app/services/enrichment/README.md` | CREATE | ~80-100 |

**Total:** 13 files, ~900-1200 lines

---

## Phase 6: Final Audit

### Pre-Merge Checklist

- [ ] All 14 TODOs completed
- [ ] All tests pass
- [ ] Lint clean
- [ ] Type check clean
- [ ] No L9 contract violations
- [ ] Documentation updated
- [ ] `Enrichment-Deployment-pack/` can be archived

### Post-Merge Actions

1. Archive `Enrichment-Deployment-pack/` directory
2. Update `workflow_state.md` with completion
3. Consider extracting `ai_review.py` to `tools/` if useful

---

## Appendix A: Module Specifications

### A.1 ConsensusEngine

```python
"""
app/services/enrichment/consensus.py

Synthesizes multiple enrichment responses into a single consensus result.
Uses field-level voting with configurable agreement threshold.
"""

from dataclasses import dataclass

@dataclass
class ConsensusResult:
    fields: dict[str, Any]
    confidence: float
    agreement_ratio: float
    contributing_sources: int

def synthesize(
    payloads: list[dict[str, Any]],
    threshold: float = 0.65,
    total_attempted: int = 0,
) -> ConsensusResult:
    """
    Synthesize multiple responses into consensus.

    Args:
        payloads: Validated response dicts from parallel calls
        threshold: Minimum agreement ratio to include a field
        total_attempted: Total variations attempted (for confidence calc)

    Returns:
        ConsensusResult with merged fields and confidence
    """
```

### A.2 UncertaintyEngine

```python
"""
app/services/enrichment/uncertainty.py

Applies confidence thresholds and generates uncertainty flags.
"""

from dataclasses import dataclass

@dataclass
class UncertaintyResult:
    fields: dict[str, Any]
    confidence: float
    flags: list[str]

def apply_uncertainty(
    fields: dict[str, Any],
    confidence: float,
    low_threshold: float = 0.5,
    high_threshold: float = 0.85,
) -> UncertaintyResult:
    """
    Apply uncertainty policy to enrichment result.

    Flags:
        - "low_confidence" if confidence < low_threshold
        - "needs_review" if low_threshold <= confidence < high_threshold
        - (no flag) if confidence >= high_threshold

    Returns:
        UncertaintyResult with potentially filtered fields and flags
    """
```

### A.3 KBResolver

```python
"""
app/services/enrichment/kb_resolver.py

Resolves knowledge base context for enrichment prompts.
"""

from dataclasses import dataclass

@dataclass
class KBContext:
    fragment_ids: list[str]
    context_text: str
    domain: str
    entity_hints: dict[str, Any]

class KBResolver:
    def __init__(self, kb_dir: str = "config/kb") -> None:
        self.kb_dir = kb_dir
        self._cache: dict[str, Any] = {}

    def resolve(
        self,
        kb_context: str | None,
        entity: dict[str, Any],
    ) -> KBContext:
        """
        Resolve KB context for an entity.

        Args:
            kb_context: KB identifier (e.g., "plastics", "saas")
            entity: Entity dict with name, type, etc.

        Returns:
            KBContext with relevant fragments and hints
        """
```

---

## Appendix B: Handler Integration

### New Handler Payload Schema

```python
# EnrichConsensusRequest
{
    "entity": {
        "name": "Acme Plastics",
        "type": "company",
        "domain": "acmeplastics.com"
    },
    "kb_context": "plastics",           # Optional KB identifier
    "max_variations": 5,                 # Max parallel prompts (default: 3)
    "consensus_threshold": 0.65,         # Agreement threshold (default: 0.65)
    "uncertainty_thresholds": {          # Optional
        "low": 0.5,
        "high": 0.85
    }
}
```

### Response Schema

```python
# EnrichConsensusResponse
{
    "fields": {...},                     # Consensus-merged fields
    "confidence": 0.82,                  # Overall confidence
    "flags": ["needs_review"],           # Uncertainty flags
    "variations_attempted": 5,
    "variations_valid": 4,
    "agreement_ratio": 0.75,
    "kb_fragments": ["plastics_polymers", "plastics_grades"],
    "elapsed_seconds": 2.34,
    "quality_score": 0.78                # From QualityScorer
}
```

---

## Appendix C: Disposition of Deployment Pack Files

| Pack File | Disposition | Notes |
|-----------|-------------|-------|
| `app/main.py` | DISCARD | Violates Contract 1 |
| `app/pipeline.py` | EXTRACT → waterfall_engine.py | Orchestration logic |
| `app/config.py` | DISCARD | Use existing settings |
| `app/logging_config.py` | DISCARD | Use existing structlog |
| `app/auth.py` | DISCARD | Chassis handles auth |
| `app/circuit_breaker.py` | REVIEW | May enhance existing |
| `app/kb_resolver.py` | EXTRACT → kb_resolver.py | New module |
| `app/perplexity_client.py` | DISCARD | Use existing |
| `app/prompt_builder.py` | EXTRACT → prompt_builder.py | Enhance existing |
| `app/validation_engine.py` | EXTRACT → waterfall_engine.py | Inline in enrich() |
| `app/consensus_engine.py` | EXTRACT → consensus.py | New module |
| `app/uncertainty_engine.py` | EXTRACT → uncertainty.py | New module |
| `app/schemas.py` | DISCARD | Use existing models |
| `tests/*` | ADAPT | Update for new structure |
| `scripts/ai_review.py` | PRESERVE | Move to tools/ if useful |
| `Makefile` | DISCARD | Use existing |
| `.github/workflows/*` | DISCARD | Use existing CI |
| `deploy/*` | DISCARD | Use existing Helm |

---

## Outstanding Items

None — plan is complete and ready for execution.

---

## Final Declaration

**GMP-ENRICH-001 PLAN LOCKED**

This plan merges the Enrichment-Deployment-pack into the existing L9-compliant enrichment infrastructure. Execution will:

1. Add 3 new modules (consensus, uncertainty, kb_resolver)
2. Enhance 2 existing modules (prompt_builder, waterfall_engine)
3. Add 1 new handler (handle_enrich_consensus)
4. Create comprehensive tests
5. Maintain full L9 contract compliance

**Estimated Effort:** 4-6 hours
**Risk Level:** LOW (additive changes, no breaking modifications)

---

*Generated: 2026-03-30*
*Author: Cursor Agent*
*Reviewed: Pending*
