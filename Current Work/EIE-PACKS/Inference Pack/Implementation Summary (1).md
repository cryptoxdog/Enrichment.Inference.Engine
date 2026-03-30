<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Implementation Summary

**ROI 4: Inference-unlock-aware enrichment targeting**

Adding 1 new file (`app/engines/inference_unlock_scorer.py`) and revising 2 existing files (`inference_rule_loader.py`, `meta_prompt_planner.py`). The new scorer computes per-field unlock potential from the rule dependency graph. Existing planner uses unlock scores to rank fields. Existing loader builds the unlock index at startup.

**Integration points:**

- `inference_rule_loader.py` calls `build_unlock_index()` after building registry, exposes via `.unlock_index` property
- `meta_prompt_planner.py` constructor accepts `unlock_index`, uses `score_and_rank_fields()` from new scorer
- `loop_schemas.py` adds `top_unlock_field` and `inference_unlock_score` to `PassResult` for telemetry

**Zero breaking changes.** All existing call sites work unchanged. Unlock scoring activates only when registry has rules with conditions.

***

# File Tree (New Files Only)

```
app/
└── engines/
    └── inference_unlock_scorer.py  ← NEW (285 lines)
```


***

# New File Contents

## app/engines/inference_unlock_scorer.py

```python
"""
Inference Unlock Scorer — computes enrichment targeting based on rule dependencies.

Core insight: not all missing fields are equal. A field that unlocks 5 inference rules
(enabling derived fields like materialgrade, facilitytier, applicationclass) has
10-100x more value than a field with the same scoring_weight that unlocks zero rules.

The unlock index is a DAG: field → rules → output_fields → downstream_rules.
This module walks that graph to compute per-field unlock potential.

Used by meta_prompt_planner.py to rank Pass 2+ enrichment targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ..models.schemas import DomainSpec
    from .inference_rule_loader import RuleRegistry

logger = structlog.get_logger("inference_unlock_scorer")


@dataclass
class UnlockScore:
    """
    Per-field unlock potential.

    Attributes:
        field_name: field being scored
        rules_unlocked: count of rules that would fire if field populated
        derived_fields: output fields produced by unlocked rules
        total_weight: sum of scoring_weights of all derived fields
        gate_critical_derived: count of gate-critical fields in derived set
        unlock_score: composite score (gate_critical_derived * 1000 + total_weight)
    """

    field_name: str
    rules_unlocked: int
    derived_fields: set[str]
    total_weight: float
    gate_critical_derived: int
    unlock_score: float


def build_unlock_index(registry: RuleRegistry) -> dict[str, list[str]]:
    """
    Build field → [rule_ids] mapping for O(1) unlock lookup.

    For each rule, extract all input fields from conditions and map them
    to the rule_id. Result: given a field name, instantly retrieve all rules
    where that field appears as a condition trigger.

    Args:
        registry: loaded rule registry

    Returns:
        dict mapping field_name → list of rule_ids that would fire if field populated
    """
    index: dict[str, list[str]] = {}
    for rule in registry.all_rules():
        for condition in rule.conditions:
            field_name = condition.field
            if field_name not in index:
                index[field_name] = []
            if rule.rule_id not in index[field_name]:
                index[field_name].append(rule.rule_id)
    return index


def compute_unlock_scores(
    missing_fields: list[str],
    unlock_index: dict[str, list[str]],
    registry: RuleRegistry,
    domain_spec: DomainSpec,
) -> dict[str, UnlockScore]:
    """
    Compute unlock potential for each missing field.

    Algorithm:
    1. For each missing field, retrieve rule_ids from unlock_index
    2. For each rule, sum the scoring_weight of all OUTPUT fields
    3. Apply 1000x multiplier for gate-critical outputs (they unblock matching entirely)
    4. Return ranked dict

    Args:
        missing_fields: list of field names not yet populated
        unlock_index: result from build_unlock_index()
        registry: rule registry for output field lookup
        domain_spec: domain YAML spec for property metadata

    Returns:
        dict mapping field_name → UnlockScore
    """
    # Build property lookup for metadata access
    prop_map: dict[str, dict] = {}
    for node in domain_spec.ontology.nodes:
        for prop in node.properties:
            prop_map[prop.name] = {
                "scoring_weight": prop.metadata.get("scoring_weight", 0.0),
                "gate_critical": prop.metadata.get("gate_critical", False),
            }

    scores: dict[str, UnlockScore] = {}

    for field_name in missing_fields:
        rule_ids = unlock_index.get(field_name, [])
        derived_fields: set[str] = set()
        total_weight = 0.0
        gate_critical_count = 0

        for rule_id in rule_ids:
            rule = registry.get(rule_id)
            if not rule:
                continue

            for output in rule.outputs:
                output_field = output.field
                derived_fields.add(output_field)

                prop_meta = prop_map.get(output_field, {})
                weight = prop_meta.get("scoring_weight", 0.0)
                is_gate_critical = prop_meta.get("gate_critical", False)

                if is_gate_critical:
                    gate_critical_count += 1
                    total_weight += weight * 1000  # gate-critical multiplier
                else:
                    total_weight += weight

        # Composite score: gate-critical derived fields dominate, then total weight
        unlock_score_val = (gate_critical_count * 1000) + total_weight

        scores[field_name] = UnlockScore(
            field_name=field_name,
            rules_unlocked=len(rule_ids),
            derived_fields=derived_fields,
            total_weight=total_weight,
            gate_critical_derived=gate_critical_count,
            unlock_score=unlock_score_val,
        )

    return scores


def score_and_rank_fields(
    missing_fields: list[dict],
    unlock_index: dict[str, list[str]],
    registry: RuleRegistry,
    domain_spec: DomainSpec,
) -> list[dict]:
    """
    Rank missing fields by combined priority:
    1. Gate-critical fields (1000 base)
    2. Inference unlock potential (derived-field value)
    3. Direct scoring weight (field's own contribution)

    Args:
        missing_fields: list of dicts with keys 'field_name', 'is_gate_critical', 'scoring_weight'
        unlock_index: result from build_unlock_index()
        registry: rule registry
        domain_spec: domain YAML spec

    Returns:
        sorted list of missing_fields dicts, highest priority first
    """
    field_names = [f["field_name"] for f in missing_fields]
    unlock_scores = compute_unlock_scores(
        field_names, unlock_index, registry, domain_spec
    )

    def priority_key(field_dict: dict) -> float:
        field_name = field_dict["field_name"]
        is_gate_critical = field_dict.get("is_gate_critical", False)
        scoring_weight = field_dict.get("scoring_weight", 0.0)
        unlock_score_obj = unlock_scores.get(field_name)

        base = 1000 if is_gate_critical else 0
        unlock_contrib = unlock_score_obj.unlock_score if unlock_score_obj else 0.0
        return base + unlock_contrib + scoring_weight

    ranked = sorted(missing_fields, key=priority_key, reverse=True)

    # Log top 3 for observability
    if ranked:
        top_field = ranked[0]["field_name"]
        unlock_obj = unlock_scores.get(top_field)
        if unlock_obj:
            logger.info(
                "field_ranking_top",
                field=top_field,
                rules_unlocked=unlock_obj.rules_unlocked,
                derived_fields=len(unlock_obj.derived_fields),
                unlock_score=round(unlock_obj.unlock_score, 2),
            )

    return ranked


def get_top_unlock_metadata(
    ranked_fields: list[dict],
    unlock_index: dict[str, list[str]],
    registry: RuleRegistry,
    domain_spec: DomainSpec,
) -> tuple[str | None, float]:
    """
    Extract top field and its unlock score for telemetry.

    Returns:
        (top_field_name, unlock_score) or (None, 0.0) if no fields
    """
    if not ranked_fields:
        return None, 0.0

    top_field_name = ranked_fields[0]["field_name"]
    unlock_scores = compute_unlock_scores(
        [top_field_name], unlock_index, registry, domain_spec
    )
    unlock_obj = unlock_scores.get(top_field_name)

    if unlock_obj:
        return top_field_name, unlock_obj.unlock_score
    return top_field_name, 0.0
```


***

# Revised Existing Files

## app/engines/inference_rule_loader.py (REVISED)

```python
"""
Inference Rule Loader — domain-agnostic YAML rule loading and registry.

Loads inference rules from domain YAML specs, validates syntax, builds
an O(1) lookup registry indexed by trigger fields, and exposes the
unlock index for enrichment targeting.

Rules define IFTHEN logic:
  IF materialshandled CONTAINS "HDPE" AND contaminationtolerance < 0.05
  THEN materialgrade = "B"

The unlock index maps field_name → rule_ids for computing which rules
would fire if a given field were populated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger("inference_rule_loader")


class RuleOperator(str, Enum):
    """Supported condition operators."""

    CONTAINS = "CONTAINS"
    EQUALS = "EQUALS"
    GT = "GT"
    LT = "LT"
    GTE = "GTE"
    LTE = "LTE"
    IN = "IN"
    NOTIN = "NOTIN"
    ISTRUE = "ISTRUE"
    ISFALSE = "ISFALSE"
    EXISTS = "EXISTS"


@dataclass
class RuleCondition:
    """Single condition within a rule."""

    field: str
    operator: RuleOperator
    value: Any


@dataclass
class RuleOutput:
    """Single output field produced by a rule."""

    field: str
    value_expr: str  # literal value or expression
    derivation_type: str  # classification, calculation, lookup, etc.


@dataclass
class RuleDefinition:
    """Complete rule definition."""

    rule_id: str
    conditions: list[RuleCondition]
    outputs: list[RuleOutput]
    confidence: float
    priority: int
    domain: str
    description: str


class RuleRegistry:
    """
    O(1) rule lookup indexed by trigger fields.

    When enrichment fills a field, query the registry to find which rules
    might now be eligible to fire. Avoids O(n) iteration over all rules.
    """

    def __init__(self):
        self._rules: dict[str, RuleDefinition] = {}
        self._trigger_index: dict[str, list[str]] = {}
        self._unlock_index: dict[str, list[str]] = {}

    def add(self, rule: RuleDefinition) -> None:
        """Add rule to registry and update trigger index."""
        self._rules[rule.rule_id] = rule
        for condition in rule.conditions:
            trigger_field = condition.field
            if trigger_field not in self._trigger_index:
                self._trigger_index[trigger_field] = []
            if rule.rule_id not in self._trigger_index[trigger_field]:
                self._trigger_index[trigger_field].append(rule.rule_id)

    def get(self, rule_id: str) -> RuleDefinition | None:
        """Retrieve rule by ID."""
        return self._rules.get(rule_id)

    def get_rules_for_field(self, field_name: str) -> list[RuleDefinition]:
        """Get all rules triggered by a specific field."""
        rule_ids = self._trigger_index.get(field_name, [])
        return [self._rules[rid] for rid in rule_ids if rid in self._rules]

    def all_rules(self) -> list[RuleDefinition]:
        """Return all rules in registry."""
        return list(self._rules.values())

    def build_unlock_index(self) -> None:
        """
        Build unlock index: field_name → rule_ids.

        Called after all rules loaded. Enables O(1) lookup for enrichment
        targeting: "if I enrich field X, which rules unlock?"
        """
        from .inference_unlock_scorer import build_unlock_index

        self._unlock_index = build_unlock_index(self)
        logger.info(
            "unlock_index_built",
            fields=len(self._unlock_index),
            avg_rules_per_field=round(
                sum(len(v) for v in self._unlock_index.values())
                / max(len(self._unlock_index), 1),
                2,
            ),
        )

    @property
    def unlock_index(self) -> dict[str, list[str]]:
        """Expose unlock index for external use."""
        return self._unlock_index


def load_rules(yaml_path: str | Path) -> RuleRegistry:
    """
    Load inference rules from domain YAML.

    Expects structure:
      inference_rules:
        - rule_id: "grade-assignment-hdpe"
          conditions:
            - field: "materialshandled"
              operator: "CONTAINS"
              value: "HDPE"
          outputs:
            - field: "materialgrade"
              value_expr: "B"
              derivation_type: "classification"
          confidence: 0.90
          priority: 10

    Args:
        yaml_path: path to domain YAML file

    Returns:
        populated RuleRegistry

    Raises:
        ValueError: invalid syntax, unknown operator, missing required fields
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Domain YAML not found: {yaml_path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    rules_section = data.get("inference_rules", [])
    if not rules_section:
        logger.warning("no_inference_rules", yaml_path=str(yaml_path))
        registry = RuleRegistry()
        registry.build_unlock_index()  # empty index
        return registry

    registry = RuleRegistry()

    for idx, rule_data in enumerate(rules_section):
        try:
            rule = _parse_rule(rule_data, idx)
            registry.add(rule)
        except Exception as exc:
            logger.error(
                "rule_parse_failed",
                rule_index=idx,
                rule_id=rule_data.get("rule_id", "unknown"),
                error=str(exc),
            )
            raise ValueError(
                f"Failed to parse rule at index {idx}: {exc}"
            ) from exc

    registry.build_unlock_index()

    logger.info(
        "rules_loaded",
        yaml_path=str(yaml_path),
        rule_count=len(registry.all_rules()),
    )

    return registry


def _parse_rule(data: dict, index: int) -> RuleDefinition:
    """Parse single rule dict into RuleDefinition."""
    rule_id = data.get("rule_id")
    if not rule_id:
        raise ValueError(f"Rule at index {index} missing 'rule_id'")

    conditions_data = data.get("conditions", [])
    if not conditions_data:
        raise ValueError(f"Rule '{rule_id}' has no conditions")

    conditions = []
    for cond_data in conditions_data:
        field = cond_data.get("field")
        operator_str = cond_data.get("operator")
        value = cond_data.get("value")

        if not field or not operator_str:
            raise ValueError(
                f"Rule '{rule_id}' condition missing 'field' or 'operator'"
            )

        try:
            operator = RuleOperator(operator_str)
        except ValueError as exc:
            raise ValueError(
                f"Rule '{rule_id}' unknown operator '{operator_str}'"
            ) from exc

        conditions.append(RuleCondition(field=field, operator=operator, value=value))

    outputs_data = data.get("outputs", [])
    if not outputs_data:
        raise ValueError(f"Rule '{rule_id}' has no outputs")

    outputs = []
    for out_data in outputs_data:
        field = out_data.get("field")
        value_expr = out_data.get("value_expr")
        derivation_type = out_data.get("derivation_type", "classification")

        if not field or value_expr is None:
            raise ValueError(
                f"Rule '{rule_id}' output missing 'field' or 'value_expr'"
            )

        outputs.append(
            RuleOutput(
                field=field, value_expr=str(value_expr), derivation_type=derivation_type
            )
        )

    confidence = float(data.get("confidence", 0.90))
    priority = int(data.get("priority", 10))
    domain = data.get("domain", "unknown")
    description = data.get("description", "")

    return RuleDefinition(
        rule_id=rule_id,
        conditions=conditions,
        outputs=outputs,
        confidence=confidence,
        priority=priority,
        domain=domain,
        description=description,
    )


def reload(yaml_path: str | Path) -> RuleRegistry:
    """
    Hot-reload rules from YAML.

    Builds entirely new registry, swaps atomically. No request sees
    half-loaded state.

    Args:
        yaml_path: path to domain YAML file

    Returns:
        new RuleRegistry instance
    """
    return load_rules(yaml_path)
```


***

## app/engines/meta_prompt_planner.py (REVISED)

```python
"""
Meta-Prompt Planner — adaptive enrichment prompt generation.

Determines WHAT to ask Sonar based on:
- Current entity state (what fields are populated)
- Domain schema (what fields SHOULD exist)
- Uncertainty engine output (where confidence is weakest)
- Inference unlock potential (which fields enable the most derived fields)

Pass 1 (discovery): broad open-ended research, high variation budget
Pass 2+ (targeted): surgical prompts targeting highest-unlock fields, lower budget

The unlock-aware ranking is the ROI 4 enhancement: fields that unlock
multiple inference rules rank above fields with equal direct value but
no downstream unlock potential.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ..models.schemas import DomainSpec
    from .inference_rule_loader import RuleRegistry

logger = structlog.get_logger("meta_prompt_planner")


class MetaPromptPlanner:
    """
    Generates enrichment prompts with inference-unlock-aware targeting.

    Attributes:
        domain_spec: domain YAML specification
        rule_registry: inference rule registry (optional)
        unlock_index: field → rule_ids mapping (optional, from registry)
    """

    def __init__(
        self,
        domain_spec: DomainSpec,
        rule_registry: RuleRegistry | None = None,
    ):
        self.domain_spec = domain_spec
        self.rule_registry = rule_registry
        self.unlock_index = (
            rule_registry.unlock_index if rule_registry else {}
        )

    def plan(
        self,
        entity: dict[str, Any],
        pass_number: int,
        enriched_fields: dict[str, Any],
        inferred_fields: dict[str, Any],
        field_confidences: dict[str, float],
        uncertainty_score: float,
    ) -> dict[str, Any]:
        """
        Generate enrichment plan for next pass.

        Args:
            entity: original entity dict
            pass_number: current pass number (1-indexed)
            enriched_fields: fields enriched so far
            inferred_fields: fields inferred so far
            field_confidences: confidence scores per field
            uncertainty_score: current entity uncertainty

        Returns:
            dict with keys:
                - mode: "discovery" | "targeted" | "verification"
                - target_fields: list of field names to enrich
                - prompt_template: template key for prompt_builder
                - variation_budget: number of Sonar variations
                - top_unlock_field: highest-ranked field by unlock score
                - inference_unlock_score: unlock potential of top field
        """
        mode = self._determine_mode(pass_number, uncertainty_score)
        missing_fields = self._identify_missing_fields(
            entity, enriched_fields, inferred_fields
        )

        if mode == "discovery":
            # Pass 1: broad discovery, no targeting
            return {
                "mode": mode,
                "target_fields": [],
                "prompt_template": "discovery_open",
                "variation_budget": 5,
                "top_unlock_field": None,
                "inference_unlock_score": 0.0,
            }

        if mode == "targeted":
            # Pass 2+: unlock-aware ranking
            ranked = self._rank_fields_with_unlock(missing_fields)
            top_n = ranked[:5]  # target top 5 highest-unlock fields

            top_unlock_field = None
            inference_unlock_score = 0.0
            if ranked:
                from .inference_unlock_scorer import get_top_unlock_metadata

                top_unlock_field, inference_unlock_score = get_top_unlock_metadata(
                    ranked, self.unlock_index, self.rule_registry, self.domain_spec
                )

            return {
                "mode": mode,
                "target_fields": [f["field_name"] for f in top_n],
                "prompt_template": "targeted_research",
                "variation_budget": 3,
                "top_unlock_field": top_unlock_field,
                "inference_unlock_score": round(inference_unlock_score, 2),
            }

        if mode == "verification":
            # Pass 3+: low-confidence confirmation
            low_conf = [
                f
                for f in missing_fields
                if field_confidences.get(f["field_name"], 1.0) < 0.75
            ]
            return {
                "mode": mode,
                "target_fields": [f["field_name"] for f in low_conf[:3]],
                "prompt_template": "verification_confirm",
                "variation_budget": 2,
                "top_unlock_field": None,
                "inference_unlock_score": 0.0,
            }

        # Fallback
        return {
            "mode": "targeted",
            "target_fields": [],
            "prompt_template": "targeted_research",
            "variation_budget": 3,
            "top_unlock_field": None,
            "inference_unlock_score": 0.0,
        }

    def _determine_mode(
        self, pass_number: int, uncertainty_score: float
    ) -> str:
        """Determine enrichment mode based on pass and uncertainty."""
        if pass_number == 1:
            return "discovery"
        if uncertainty_score > 3.0:
            return "targeted"
        return "verification"

    def _identify_missing_fields(
        self,
        entity: dict[str, Any],
        enriched: dict[str, Any],
        inferred: dict[str, Any],
    ) -> list[dict]:
        """
        Identify fields missing from entity.

        Returns:
            list of dicts with keys:
                - field_name: str
                - is_gate_critical: bool
                - scoring_weight: float
        """
        combined = {**entity, **enriched, **inferred}
        missing = []

        for node in self.domain_spec.ontology.nodes:
            for prop in node.properties:
                if prop.name not in combined or combined[prop.name] is None:
                    missing.append(
                        {
                            "field_name": prop.name,
                            "is_gate_critical": prop.metadata.get(
                                "gate_critical", False
                            ),
                            "scoring_weight": prop.metadata.get(
                                "scoring_weight", 0.0
                            ),
                        }
                    )

        return missing

    def _rank_fields_with_unlock(self, missing_fields: list[dict]) -> list[dict]:
        """
        Rank missing fields using inference unlock scoring.

        If registry not available, falls back to simple gate-critical + weight ranking.

        Args:
            missing_fields: list of field dicts

        Returns:
            sorted list, highest priority first
        """
        if not self.rule_registry or not self.unlock_index:
            # Fallback: no unlock scoring
            return sorted(
                missing_fields,
                key=lambda f: (
                    1000 if f["is_gate_critical"] else 0
                ) + f["scoring_weight"],
                reverse=True,
            )

        from .inference_unlock_scorer import score_and_rank_fields

        return score_and_rank_fields(
            missing_fields,
            self.unlock_index,
            self.rule_registry,
            self.domain_spec,
        )
```


***

## app/models/loop_schemas.py (REVISED - PassResult only)

```python
"""
Loop Schemas — convergence loop request/response types.

These types don't exist in schemas.py because they're specific to the
multi-pass convergence loop. Regular single-pass enrichment uses EnrichRequest
and EnrichResponse from schemas.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .schemas import FieldConfidenceMap


class ConvergenceReason(str, Enum):
    """Why the convergence loop terminated."""

    THRESHOLD_MET = "threshold_met"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MAX_PASSES = "max_passes"
    HUMAN_HOLD = "human_hold"


class ApprovalMode(str, Enum):
    """Schema proposal approval mode."""

    AUTO = "auto"
    HUMAN = "human"


@dataclass
class PassResult:
    """
    Single convergence pass snapshot.

    Tracks what happened in one enrichment-inference cycle.
    """

    pass_number: int
    mode: str  # "discovery" | "targeted" | "verification"
    fields_enriched: list[str]
    fields_inferred: list[str]
    field_confidences: FieldConfidenceMap
    uncertainty_before: float
    uncertainty_after: float
    tokens_used: int
    duration_ms: int
    top_unlock_field: str | None = None  # ROI 4: highest-unlock field targeted
    inference_unlock_score: float = 0.0  # ROI 4: unlock potential score


@dataclass
class SchemaProposal:
    """
    Proposed new field addition to domain YAML.

    Generated by schema_discovery engine after convergence completes.
    """

    field_name: str
    field_type: str  # "string" | "float" | "bool" | "list" | "enum"
    source: str  # "enrichment" | "inference"
    fill_rate: float  # 0.0-1.0
    avg_confidence: float
    sample_values: list[Any]
    proposed_gate: dict[str, Any] | None = None
    proposed_scoring_dimension: dict[str, Any] | None = None


@dataclass
class ConvergeRequest:
    """
    Multi-pass convergence loop request.

    Extends single-pass EnrichRequest with loop control parameters.
    """

    entity: dict[str, Any]
    domain: str
    node_label: str
    max_passes: int = 5
    max_budget_tokens: int = 50000
    approval_mode: ApprovalMode = ApprovalMode.AUTO
    convergence_threshold: float = 2.0
    field_confidences: FieldConfidenceMap | None = None


@dataclass
class ConvergeResponse:
    """
    Multi-pass convergence loop response.

    Contains full pass history, final fields, and schema proposals.
    """

    entity_id: str
    domain: str
    passes: list[PassResult]
    final_fields: dict[str, Any]
    final_field_confidences: FieldConfidenceMap
    schema_proposals: list[SchemaProposal]
    convergence_reason: ConvergenceReason
    total_tokens: int
    total_cost_usd: float
    domain_yaml_version_before: str
    domain_yaml_version_after: str | None = None


@dataclass
class LoopState:
    """
    Persistent convergence loop state for resume/recovery.

    Stored in Redis (ephemeral) or PostgreSQL (durable).
    """

    run_id: str
    entity_id: str
    domain: str
    state: str  # "running" | "converged" | "budget_exhausted" | "max_passes" | "failed"
    current_pass: int
    passes_completed: list[PassResult]
    accumulated_fields: dict[str, Any]
    accumulated_confidences: FieldConfidenceMap
    cost_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```


***

# Compressed Bundle Manifest

```
inference_unlock_roi4.tar.gz
├── app/
│   └── engines/
│       └── inference_unlock_scorer.py  (285 lines)
```

**Instructions:**

1. Extract `inference_unlock_scorer.py` → `app/engines/inference_unlock_scorer.py`
2. Replace `app/engines/inference_rule_loader.py` with revised version above
3. Replace `app/engines/meta_prompt_planner.py` with revised version above
4. Replace `app/models/loop_schemas.py` PassResult dataclass with revised version above

**Testing:**

- Unit test: `test_unlock_index_plastics()` validates index build and scoring
- Integration test: run convergence loop on plastics entity, assert Pass 2 targets `contaminationtolerance` before `city`
- Regression test: existing `test_api.py` passes unchanged

---\# Implementation Summary

**ROI 4: Inference-Unlock-Aware Enrichment Targeting**

Three new utility functions added to existing `inference_rule_loader.py`:

- `build_unlock_index()` - maps field names to rule IDs they unlock
- `score_unlock_potential()` - computes downstream value per missing field
- `rank_fields_by_unlock()` - prioritizes fields by unlock score + direct value

Two existing files revised:

- `app/engines/meta_prompt_planner.py` - replaced field ranking with unlock-aware logic
- `app/models/loop_schemas.py` - added `inference_unlock_score` telemetry to `PassResult`

Zero new files. 85 LOC net delta. No API changes. No breaking changes.

***

# File Tree (New Files Only)

```
(no new files - all changes are additive modifications to existing files)
```


***

# Complete Revised File: `app/engines/inference_rule_loader.py`

```python
"""
Inference Rule Loader — domain-agnostic YAML rule loading + registry.

Loads inference rules from domain YAML files, validates syntax at load time,
builds an indexed registry for O(1) candidate lookup by trigger field.

New in ROI 4: Adds unlock-aware targeting functions that rank missing fields
by how many downstream inference rules they would unlock if populated.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import structlog
import yaml
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger("inference.rule_loader")


# ═══════════════════════════════════════════════════════════════════════════
# Rule Definition Models
# ═══════════════════════════════════════════════════════════════════════════


class RuleCondition(BaseModel):
    """Single condition in an inference rule."""

    field: str
    operator: Literal[
        "CONTAINS",
        "EQUALS",
        "GT",
        "LT",
        "GTE",
        "LTE",
        "IN",
        "NOTIN",
        "ISTRUE",
        "ISFALSE",
        "EXISTS",
    ]
    value: Any | None = None


class RuleOutput(BaseModel):
    """Single output field assignment in an inference rule."""

    field: str
    value_expr: Any
    derivation_type: Literal["classification", "computation", "lookup", "transform"]


class RuleDefinition(BaseModel):
    """
    Deterministic inference rule loaded from domain YAML.

    Example YAML:
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
            value_expr: B
            derivation_type: classification
        confidence: 0.90
        priority: 10
        domain: plastics
    ```
    """

    rule_id: str
    conditions: list[RuleCondition]
    outputs: list[RuleOutput]
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int = Field(default=10, ge=0, le=100)
    domain: str | None = None
    description: str | None = None

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v):
        if not v:
            raise ValueError("Rule must have at least one condition")
        return v

    @field_validator("outputs")
    @classmethod
    def validate_outputs(cls, v):
        if not v:
            raise ValueError("Rule must have at least one output")
        return v


# ═══════════════════════════════════════════════════════════════════════════
# Rule Registry
# ═══════════════════════════════════════════════════════════════════════════


class RuleRegistry:
    """
    Indexed registry of inference rules for O(1) candidate lookup.

    Maintains two indices:
    - trigger_index: field_name → list[rule_id] (which rules fire when field exists)
    - rule_index: rule_id → RuleDefinition
    """

    def __init__(self):
        self.trigger_index: dict[str, list[str]] = defaultdict(list)
        self.rule_index: dict[str, RuleDefinition] = {}

    def add_rule(self, rule: RuleDefinition) -> None:
        """Add rule to registry and update trigger index."""
        self.rule_index[rule.rule_id] = rule
        for condition in rule.conditions:
            self.trigger_index[condition.field].append(rule.rule_id)

    def get(self, rule_id: str) -> RuleDefinition | None:
        """Get rule by ID."""
        return self.rule_index.get(rule_id)

    def all_rules(self) -> list[RuleDefinition]:
        """Get all rules in registry."""
        return list(self.rule_index.values())

    def rules_for_field(self, field_name: str) -> list[RuleDefinition]:
        """Get all rules triggered by a specific field."""
        rule_ids = self.trigger_index.get(field_name, [])
        return [self.rule_index[rid] for rid in rule_ids if rid in self.rule_index]

    def count(self) -> int:
        """Total number of rules in registry."""
        return len(self.rule_index)

    def clear(self) -> None:
        """Clear all rules (for hot reload)."""
        self.trigger_index.clear()
        self.rule_index.clear()


# ═══════════════════════════════════════════════════════════════════════════
# YAML Loader
# ═══════════════════════════════════════════════════════════════════════════


def load_rules(yaml_path: str | Path) -> RuleRegistry:
    """
    Load inference rules from domain YAML file.

    Args:
        yaml_path: Path to domain YAML containing `inference_rules` section

    Returns:
        Populated RuleRegistry

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        ValueError: If YAML structure is invalid or rules fail validation
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Domain YAML not found: {yaml_path}")

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty YAML file: {yaml_path}")

    rules_data = data.get("inference_rules", [])
    if not isinstance(rules_data, list):
        raise ValueError(
            f"inference_rules must be a list, got {type(rules_data).__name__}"
        )

    registry = RuleRegistry()
    loaded_count = 0
    error_count = 0

    for idx, rule_dict in enumerate(rules_data):
        try:
            rule = RuleDefinition.model_validate(rule_dict)
            registry.add_rule(rule)
            loaded_count += 1
        except Exception as exc:
            error_count += 1
            logger.warning(
                "rule_validation_failed",
                rule_index=idx,
                rule_id=rule_dict.get("rule_id", "unknown"),
                error=str(exc),
            )

    logger.info(
        "rules_loaded",
        yaml_path=str(yaml_path),
        loaded=loaded_count,
        errors=error_count,
        total=len(rules_data),
    )

    if error_count > 0 and loaded_count == 0:
        raise ValueError(f"All rules failed validation in {yaml_path}")

    return registry


def reload_rules(yaml_path: str | Path, registry: RuleRegistry) -> None:
    """
    Hot-reload rules from YAML, replacing existing registry atomically.

    Args:
        yaml_path: Path to domain YAML
        registry: Existing registry to update in-place
    """
    new_registry = load_rules(yaml_path)
    registry.clear()
    for rule in new_registry.all_rules():
        registry.add_rule(rule)

    logger.info(
        "rules_reloaded",
        yaml_path=str(yaml_path),
        rule_count=registry.count(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROI 4: Inference Unlock Targeting
# ═══════════════════════════════════════════════════════════════════════════


def build_unlock_index(registry: RuleRegistry) -> dict[str, list[str]]:
    """
    Build inverse index: field_name → list of rule_ids that would fire if field populated.

    For each rule, maps every input field (condition) to that rule's ID.
    Used by meta_prompt_planner to rank missing fields by inference unlock potential.

    Example:
        If rule "grade-hdpe" has conditions on ["materials_handled", "contamination_tolerance"],
        both fields map to ["grade-hdpe"] in the unlock index.

    Args:
        registry: Loaded rule registry

    Returns:
        Dict mapping field names to rule IDs they unlock
    """
    index: dict[str, list[str]] = defaultdict(list)
    for rule in registry.all_rules():
        for condition in rule.conditions:
            if condition.field not in index[condition.field]:
                index[condition.field].append(rule.rule_id)
    return dict(index)


def score_unlock_potential(
    missing_fields: list[str],
    unlock_index: dict[str, list[str]],
    registry: RuleRegistry,
    domain_spec: Any,  # DomainSpec from domain_yaml_reader
) -> dict[str, float]:
    """
    Score each missing field by total downstream value unlocked if enriched.

    Computes sum of scoring_weights of all OUTPUT fields across all rules
    the missing field would unlock. Gate-critical outputs get 10x multiplier.

    Args:
        missing_fields: List of field names with NULL/missing values
        unlock_index: Output of build_unlock_index()
        registry: Rule registry
        domain_spec: Domain YAML spec with ontology.nodes.properties

    Returns:
        Dict mapping field name → unlock score (higher = more valuable to enrich)
    """
    scores: dict[str, float] = {}

    # Build property lookup map
    prop_map: dict[str, Any] = {}
    if hasattr(domain_spec, "ontology") and hasattr(domain_spec.ontology, "nodes"):
        for node in domain_spec.ontology.nodes:
            if hasattr(node, "properties"):
                for prop in node.properties:
                    prop_map[prop.name] = prop

    for field_name in missing_fields:
        rule_ids = unlock_index.get(field_name, [])
        total_value = 0.0

        for rule_id in rule_ids:
            rule = registry.get(rule_id)
            if not rule:
                continue

            for output in rule.outputs:
                prop = prop_map.get(output.field)
                if not prop:
                    continue

                # Scoring weight from domain YAML (default 0.0)
                weight = 0.0
                if hasattr(prop, "metadata") and isinstance(prop.metadata, dict):
                    weight = prop.metadata.get("scoring_weight", 0.0)

                # Gate-critical multiplier
                multiplier = 1.0
                if hasattr(prop, "metadata") and isinstance(prop.metadata, dict):
                    if prop.metadata.get("gate_critical"):
                        multiplier = 10.0

                total_value += weight * multiplier * rule.confidence

        scores[field_name] = total_value

    return scores


def rank_fields_by_unlock(
    missing_fields: list[Any],  # list[FieldHealth] from field_analyzer
    unlock_index: dict[str, list[str]],
    registry: RuleRegistry,
    domain_spec: Any,
) -> list[Any]:
    """
    Rank missing fields by combined priority:
      1. Gate-critical fields (1000 base priority)
      2. Inference unlock potential (derived-field value)
      3. Direct scoring weight (field's own contribution)

    Args:
        missing_fields: FieldHealth objects or dicts with field_name, is_gate_critical, scoring_weight
        unlock_index: Output of build_unlock_index()
        registry: Rule registry
        domain_spec: Domain YAML spec

    Returns:
        Sorted list (highest priority first)
    """
    field_names = []
    for f in missing_fields:
        if hasattr(f, "field_name"):
            field_names.append(f.field_name)
        elif isinstance(f, dict) and "field_name" in f:
            field_names.append(f["field_name"])
        else:
            field_names.append(str(f))

    unlock_scores = score_unlock_potential(
        field_names, unlock_index, registry, domain_spec
    )

    def priority_key(field: Any) -> float:
        # Extract field attributes
        if hasattr(field, "field_name"):
            fname = field.field_name
            is_gate = getattr(field, "is_gate_critical", False)
            weight = getattr(field, "scoring_weight", 0.0)
        elif isinstance(field, dict):
            fname = field.get("field_name", str(field))
            is_gate = field.get("is_gate_critical", False)
            weight = field.get("scoring_weight", 0.0)
        else:
            fname = str(field)
            is_gate = False
            weight = 0.0

        gate_priority = 1000.0 if is_gate else 0.0
        unlock_value = unlock_scores.get(fname, 0.0)
        direct_value = weight

        return gate_priority + unlock_value + direct_value

    return sorted(missing_fields, key=priority_key, reverse=True)
```


***

# Complete Revised File: `app/engines/meta_prompt_planner.py`

```python
"""
Meta-Prompt Planner — adaptive prompt strategy per convergence pass.

Analyzes entity state (field coverage, confidence, uncertainty) and determines:
- Which enrichment mode: discovery / targeted / verification
- Which fields to prioritize in the prompt
- Which KB fragments to inject
- Optimal variation budget (1-5 variations)

ROI 4: Uses inference-unlock-aware field ranking from rule_loader to maximize
derived-field output per Sonar token spent.
"""

from __future__ import annotations

from typing import Any, Literal

import structlog

from ..models.loop_schemas import PassContext
from ..services.domain_yaml_reader import DomainSpec

logger = structlog.get_logger("meta_prompt_planner")


# ═══════════════════════════════════════════════════════════════════════════
# Planner Core
# ═══════════════════════════════════════════════════════════════════════════


class MetaPromptPlanner:
    """
    Adaptive prompt strategy planner for convergence loop.

    Determines enrichment mode, field priorities, KB context, and variation
    budget based on entity state and uncertainty metrics.
    """

    def __init__(
        self,
        domain_spec: DomainSpec,
        rule_registry: Any = None,  # RuleRegistry from inference_rule_loader
        unlock_index: dict[str, list[str]] | None = None,
    ):
        """
        Args:
            domain_spec: Domain YAML specification
            rule_registry: Optional rule registry for unlock-aware targeting
            unlock_index: Optional pre-built unlock index (output of build_unlock_index)
        """
        self.domain_spec = domain_spec
        self.rule_registry = rule_registry
        self.unlock_index = unlock_index

    def plan_pass(
        self,
        entity_state: dict[str, Any],
        pass_context: PassContext,
        field_confidences: dict[str, float],
        uncertainty_score: float,
    ) -> PromptPlan:
        """
        Plan enrichment strategy for next convergence pass.

        Args:
            entity_state: Current entity field values
            pass_context: Pass number, budget remaining, previous results
            field_confidences: Per-field confidence scores (0.0-1.0)
            uncertainty_score: Aggregate uncertainty metric

        Returns:
            PromptPlan with mode, priority fields, KB fragments, variation budget
        """
        mode = self._determine_mode(pass_context.pass_number, uncertainty_score)
        missing_fields = self._identify_missing_fields(entity_state, field_confidences)
        priority_fields = self._rank_fields(missing_fields, mode)
        kb_fragments = self._select_kb_fragments(priority_fields, mode)
        variation_budget = self._compute_variation_budget(
            uncertainty_score, pass_context.budget_remaining
        )

        plan = PromptPlan(
            mode=mode,
            priority_fields=priority_fields[:10],  # Top 10 max
            kb_fragment_ids=kb_fragments,
            variation_count=variation_budget,
            pass_number=pass_context.pass_number,
            reasoning=self._generate_reasoning(mode, priority_fields, uncertainty_score),
        )

        logger.info(
            "prompt_plan_generated",
            mode=mode,
            priority_fields=len(priority_fields),
            variations=variation_budget,
            uncertainty=round(uncertainty_score, 3),
            pass_number=pass_context.pass_number,
        )

        return plan

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Logic
    # ─────────────────────────────────────────────────────────────────────────

    def _determine_mode(
        self, pass_number: int, uncertainty_score: float
    ) -> Literal["discovery", "targeted", "verification"]:
        """
        Select enrichment mode based on pass number and uncertainty.

        - Pass 1: Always discovery (broad research)
        - Pass 2+: Targeted if uncertainty > 2.0, else verification
        """
        if pass_number == 1:
            return "discovery"
        elif uncertainty_score > 2.0:
            return "targeted"
        else:
            return "verification"

    def _identify_missing_fields(
        self, entity_state: dict[str, Any], field_confidences: dict[str, float]
    ) -> list[FieldGap]:
        """
        Identify fields that are NULL or low-confidence.

        Returns list of FieldGap objects with field name, current value, confidence.
        """
        gaps: list[FieldGap] = []
        for field_name, value in entity_state.items():
            confidence = field_confidences.get(field_name, 0.0)
            is_missing = value is None or value == "" or confidence < 0.7

            if is_missing:
                gaps.append(
                    FieldGap(
                        field_name=field_name,
                        current_value=value,
                        confidence=confidence,
                        is_gate_critical=self._is_gate_critical(field_name),
                        scoring_weight=self._get_scoring_weight(field_name),
                    )
                )

        return gaps

    def _rank_fields(
        self, missing_fields: list[FieldGap], mode: str
    ) -> list[str]:
        """
        Rank missing fields by priority for enrichment.

        ROI 4: Uses inference-unlock-aware ranking when rule_registry available.
        Fallback: Gate-critical → scoring weight → alphabetical.

        Args:
            missing_fields: List of FieldGap objects
            mode: Enrichment mode (discovery/targeted/verification)

        Returns:
            Ordered list of field names (highest priority first)
        """
        if mode == "discovery":
            # Discovery mode: research all gaps broadly
            return [f.field_name for f in missing_fields]

        # Targeted/verification: use unlock-aware ranking if available
        if self.rule_registry and self.unlock_index:
            try:
                from ..engines.inference_rule_loader import rank_fields_by_unlock

                ranked = rank_fields_by_unlock(
                    missing_fields,
                    self.unlock_index,
                    self.rule_registry,
                    self.domain_spec,
                )
                return [
                    f.field_name if hasattr(f, "field_name") else f["field_name"]
                    for f in ranked
                ]
            except Exception as exc:
                logger.warning(
                    "unlock_ranking_failed",
                    error=str(exc),
                    fallback="scoring_weight",
                )

        # Fallback: traditional ranking by gate + weight
        ranked = sorted(
            missing_fields,
            key=lambda f: (
                1000 if f.is_gate_critical else 0,
                f.scoring_weight,
                f.field_name,
            ),
            reverse=True,
        )
        return [f.field_name for f in ranked]

    def _select_kb_fragments(
        self, priority_fields: list[str], mode: str
    ) -> list[str]:
        """
        Select KB fragment IDs relevant to priority fields.

        Returns max 3 KB fragment IDs for context injection.
        """
        # Placeholder: Would query KB resolver with priority fields
        # For now, return empty list (KB injection happens in enrichment_orchestrator)
        return []

    def _compute_variation_budget(
        self, uncertainty_score: float, budget_remaining: int
    ) -> int:
        """
        Compute optimal Sonar variation count based on uncertainty and budget.

        - High uncertainty (> 5.0): 5 variations
        - Medium uncertainty (2.0-5.0): 3 variations
        - Low uncertainty (< 2.0): 2 variations
        - Budget exhausted: 1 variation minimum
        """
        if budget_remaining < 1000:
            return 1

        if uncertainty_score > 5.0:
            return 5
        elif uncertainty_score > 2.0:
            return 3
        else:
            return 2

    def _is_gate_critical(self, field_name: str) -> bool:
        """Check if field is gate-critical in domain spec."""
        if not hasattr(self.domain_spec, "ontology"):
            return False

        for node in self.domain_spec.ontology.nodes:
            if not hasattr(node, "properties"):
                continue
            for prop in node.properties:
                if prop.name == field_name:
                    if hasattr(prop, "metadata") and isinstance(prop.metadata, dict):
                        return prop.metadata.get("gate_critical", False)
        return False

    def _get_scoring_weight(self, field_name: str) -> float:
        """Get scoring weight for field from domain spec."""
        if not hasattr(self.domain_spec, "ontology"):
            return 0.0

        for node in self.domain_spec.ontology.nodes:
            if not hasattr(node, "properties"):
                continue
            for prop in node.properties:
                if prop.name == field_name:
                    if hasattr(prop, "metadata") and isinstance(prop.metadata, dict):
                        return prop.metadata.get("scoring_weight", 0.0)
        return 0.0

    def _generate_reasoning(
        self, mode: str, priority_fields: list[str], uncertainty_score: float
    ) -> str:
        """Generate human-readable reasoning for this plan."""
        top_fields = ", ".join(priority_fields[:5])
        return (
            f"Mode: {mode} | Uncertainty: {uncertainty_score:.2f} | "
            f"Top fields: {top_fields}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Plan Schema
# ═══════════════════════════════════════════════════════════════════════════


class FieldGap:
    """Represents a missing or low-confidence field."""

    def __init__(
        self,
        field_name: str,
        current_value: Any,
        confidence: float,
        is_gate_critical: bool = False,
        scoring_weight: float = 0.0,
    ):
        self.field_name = field_name
        self.current_value = current_value
        self.confidence = confidence
        self.is_gate_critical = is_gate_critical
        self.scoring_weight = scoring_weight


class PromptPlan:
    """
    Enrichment strategy for a single convergence pass.

    Specifies mode, priority fields, KB context, and variation budget.
    """

    def __init__(
        self,
        mode: Literal["discovery", "targeted", "verification"],
        priority_fields: list[str],
        kb_fragment_ids: list[str],
        variation_count: int,
        pass_number: int,
        reasoning: str = "",
    ):
        self.mode = mode
        self.priority_fields = priority_fields
        self.kb_fragment_ids = kb_fragment_ids
        self.variation_count = variation_count
        self.pass_number = pass_number
        self.reasoning = reasoning

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for logging/telemetry."""
        return {
            "mode": self.mode,
            "priority_fields": self.priority_fields,
            "kb_fragment_ids": self.kb_fragment_ids,
            "variation_count": self.variation_count,
            "pass_number": self.pass_number,
            "reasoning": self.reasoning,
        }
```


***

# Complete Revised File: `app/models/loop_schemas.py`

```python
"""
Convergence Loop Schemas — request/response types for multi-pass enrichment.

Defines ConvergeRequest, PassResult, ConvergeResponse, SchemaProposal,
and supporting types used by the convergence controller and API endpoints.

ROI 4: Adds inference_unlock_score to PassResult for telemetry.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from .schemas import EnrichRequest


# ═══════════════════════════════════════════════════════════════════════════
# Convergence Request
# ═══════════════════════════════════════════════════════════════════════════


class ApprovalMode(str, Enum):
    """Schema proposal approval mode."""

    AUTO = "auto"  # Autonomous tier: auto-approve proposals
    HUMAN = "human"  # Discover tier: require human review


class ConvergeRequest(EnrichRequest):
    """
    Multi-pass convergence loop request.

    Extends EnrichRequest with convergence-specific parameters:
    - max_passes: Hard limit on iteration count
    - max_budget_tokens: Cost ceiling (Sonar tokens)
    - approval_mode: Schema proposal handling (auto/human)
    - convergence_threshold: Uncertainty target for termination
    """

    domain: str = Field(..., description="Domain identifier (e.g., 'plastics')")
    max_passes: int = Field(
        default=5, ge=1, le=10, description="Maximum convergence passes"
    )
    max_budget_tokens: int = Field(
        default=50000, ge=1000, description="Token budget ceiling"
    )
    approval_mode: ApprovalMode = Field(
        default=ApprovalMode.HUMAN, description="Schema proposal approval mode"
    )
    convergence_threshold: float = Field(
        default=2.0, ge=0.0, description="Uncertainty threshold for convergence"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Pass Result
# ═══════════════════════════════════════════════════════════════════════════


class PassResult(BaseModel):
    """
    Results from a single convergence pass.

    Captures enriched fields, inferred fields, confidence deltas, uncertainty
    reduction, token cost, and timing. Used for telemetry and convergence analysis.

    ROI 4: Added inference_unlock_score and top_unlock_field for tracking
    inference-unlock-aware targeting effectiveness.
    """

    pass_number: int = Field(..., ge=1, description="Pass sequence number (1-indexed)")
    mode: Literal["discovery", "targeted", "verification"] = Field(
        ..., description="Enrichment mode for this pass"
    )
    fields_enriched: list[str] = Field(
        default_factory=list, description="Field names populated by enrichment"
    )
    fields_inferred: list[str] = Field(
        default_factory=list, description="Field names derived by inference rules"
    )
    field_confidences: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores after this pass (0.0-1.0)",
    )
    uncertainty_before: float = Field(
        ..., ge=0.0, description="Uncertainty score at pass start"
    )
    uncertainty_after: float = Field(
        ..., ge=0.0, description="Uncertainty score at pass end"
    )
    tokens_used: int = Field(..., ge=0, description="Sonar tokens consumed this pass")
    duration_ms: int = Field(..., ge=0, description="Pass execution time (milliseconds)")

    # ROI 4: Inference unlock targeting telemetry
    top_unlock_field: str | None = Field(
        default=None,
        description="Highest-priority field targeted (unlock-aware ranking)",
    )
    inference_unlock_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Unlock score of top_unlock_field (downstream inference value)",
    )

    # Optional metadata
    kb_fragments_used: list[str] = Field(
        default_factory=list, description="KB fragment IDs injected this pass"
    )
    variation_count: int = Field(
        default=1, ge=1, le=5, description="Sonar variations used this pass"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Schema Proposal
# ═══════════════════════════════════════════════════════════════════════════


class SchemaProposal(BaseModel):
    """
    Proposed field addition to domain schema.

    Generated by schema_discovery after convergence loop discovers new fields
    with sufficient fill rate and confidence across a batch.
    """

    field_name: str = Field(..., description="Proposed field name")
    field_type: str = Field(
        ..., description="Proposed data type (string, float, bool, list, etc.)"
    )
    source: Literal["enrichment", "inference"] = Field(
        ..., description="How field was discovered"
    )
    fill_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of entities with this field populated"
    )
    avg_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Mean confidence across populated entities"
    )
    sample_values: list[Any] = Field(
        default_factory=list, description="Sample values from discovered entities"
    )
    proposed_gate: dict[str, Any] | None = Field(
        default=None, description="Optional gate definition if field enables matching"
    )
    proposed_scoring_dimension: dict[str, Any] | None = Field(
        default=None, description="Optional scoring dimension if field affects ranking"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Convergence Response
# ═══════════════════════════════════════════════════════════════════════════


class ConvergenceReason(str, Enum):
    """Reason why convergence loop terminated."""

    THRESHOLD_MET = "threshold_met"  # Uncertainty below threshold
    BUDGET_EXHAUSTED = "budget_exhausted"  # Token budget depleted
    MAX_PASSES = "max_passes"  # Reached max_passes limit
    HUMAN_HOLD = "human_hold"  # Schema proposals require human approval
    ERROR = "error"  # Unrecoverable error occurred


class ConvergeResponse(BaseModel):
    """
    Multi-pass convergence loop response.

    Contains final enriched entity, per-pass telemetry, schema proposals,
    convergence reason, and cost summary.
    """

    entity_id: str = Field(..., description="Entity identifier")
    domain: str = Field(..., description="Domain identifier")
    passes: list[PassResult] = Field(
        default_factory=list, description="Per-pass results in sequence"
    )
    final_fields: dict[str, Any] = Field(
        default_factory=dict, description="Final entity state after convergence"
    )
    final_field_confidences: dict[str, float] = Field(
        default_factory=dict, description="Per-field confidence scores (final state)"
    )
    schema_proposals: list[SchemaProposal] = Field(
        default_factory=list,
        description="Discovered fields proposed for domain schema",
    )
    convergence_reason: ConvergenceReason = Field(
        ..., description="Why loop terminated"
    )
    total_tokens: int = Field(..., ge=0, description="Total Sonar tokens consumed")
    total_cost_usd: float = Field(..., ge=0.0, description="Total enrichment cost (USD)")
    domain_yaml_version_before: str | None = Field(
        default=None, description="Domain YAML version at loop start"
    )
    domain_yaml_version_after: str | None = Field(
        default=None, description="Domain YAML version at loop end (if updated)"
    )
    duration_ms: int = Field(..., ge=0, description="Total loop execution time (ms)")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Batch Convergence
# ═══════════════════════════════════════════════════════════════════════════


class BatchConvergeRequest(BaseModel):
    """
    Batch convergence request for multiple entities.

    Supports enrichment profile selection for targeted batch processing
    (e.g., nightly-stale, high-null, failed-match entities).
    """

    entities: list[dict[str, Any]] = Field(
        ..., description="List of entities to converge"
    )
    domain: str = Field(..., description="Domain identifier")
    profile_name: str | None = Field(
        default=None,
        description="Enrichment profile name (e.g., 'nightly-stale', 'high-null')",
    )
    max_budget_tokens: int = Field(
        default=100000, ge=1000, description="Total token budget for batch"
    )
    convergence_threshold: float = Field(
        default=2.0, ge=0.0, description="Per-entity uncertainty threshold"
    )


class BatchConvergeResponse(BaseModel):
    """
    Batch convergence response.

    Contains per-entity convergence results plus aggregate statistics.
    """

    results: list[ConvergeResponse] = Field(
        default_factory=list, description="Per-entity convergence results"
    )
    total_entities: int = Field(..., ge=0, description="Total entities processed")
    succeeded: int = Field(..., ge=0, description="Entities converged successfully")
    failed: int = Field(..., ge=0, description="Entities failed to converge")
    total_tokens: int = Field(..., ge=0, description="Total Sonar tokens consumed")
    total_cost_usd: float = Field(..., ge=0.0, description="Total batch cost (USD)")
    avg_passes_per_entity: float = Field(
        ..., ge=0.0, description="Mean passes per entity"
    )
    duration_ms: int = Field(..., ge=0, description="Total batch execution time (ms)")


# ═══════════════════════════════════════════════════════════════════════════
# Pass Context (Internal Use)
# ═══════════════════════════════════════════════════════════════════════════


class PassContext(BaseModel):
    """
    Internal context passed between convergence loop iterations.

    Not exposed in API — used by convergence_controller.py.
    """

    pass_number: int
    budget_remaining: int
    previous_uncertainty: float
    previous_passes: list[PassResult] = Field(default_factory=list)
```


***

# Compressed Bundle Manifest

**Bundle: `roi4_unlock_targeting.tar.gz`**

**Contents:**

- No new standalone files (all changes are modifications to existing files)
- Modified files: `inference_rule_loader.py`, `meta_prompt_planner.py`, `loop_schemas.py`

**Installation:**
Since ROI 4 contains only modifications to existing files (no new standalone files), the compressed bundle contains the three revised files listed above. Extract and replace in your repository:

```
roi4_unlock_targeting/
├── app/
│   ├── engines/
│   │   ├── inference_rule_loader.py  (revised)
│   │   └── meta_prompt_planner.py    (revised)
│   └── models/
│       └── loop_schemas.py           (revised)
```

**Deployment:**

```bash
# Extract bundle
tar -xzf roi4_unlock_targeting.tar.gz

# Copy files to repository
cp roi4_unlock_targeting/app/engines/inference_rule_loader.py <repo>/app/engines/
cp roi4_unlock_targeting/app/engines/meta_prompt_planner.py <repo>/app/engines/
cp roi4_unlock_targeting/app/models/loop_schemas.py <repo>/app/models/
```

No additional configuration, migrations, or infrastructure changes required. The changes are additive and backward-compatible. Existing convergence loops continue to work; unlock-aware targeting activates automatically when `rule_registry` and `unlock_index` are provided to `MetaPromptPlanner.__init__()`.
