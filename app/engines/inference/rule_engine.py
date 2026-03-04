"""Deterministic inference engine — fires rules against enriched feature vectors."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from .rule_loader import Operator, RuleCondition, RuleDefinition, RuleRegistry

logger = logging.getLogger(__name__)

MAX_CASCADE_DEPTH = 3


class RuleFired(BaseModel):
    rule_id: str
    conditions_met: list[str]
    outputs_produced: dict[str, Any]
    confidence: float
    priority: int
    cascade_level: int = 0


class InferenceResult(BaseModel):
    derived_fields: dict[str, Any] = Field(default_factory=dict)
    rules_fired: list[RuleFired] = Field(default_factory=list)
    rules_evaluated: int = 0
    rules_skipped: int = 0
    derivation_chains: dict[str, list[str]] = Field(default_factory=dict)
    inference_confidence: float = 1.0
    cascade_depth: int = 0


def _evaluate_condition(condition: RuleCondition, value: Any) -> bool:
    op = condition.operator
    target = condition.value

    if op is Operator.EXISTS:
        return value is not None
    if op is Operator.IS_TRUE:
        return bool(value)
    if op is Operator.IS_FALSE:
        return not bool(value)
    if value is None:
        return False
    if op is Operator.EQUALS:
        return _normalise(value) == _normalise(target)
    if op is Operator.GT:
        return float(value) > float(target)
    if op is Operator.LT:
        return float(value) < float(target)
    if op is Operator.GTE:
        return float(value) >= float(target)
    if op is Operator.LTE:
        return float(value) <= float(target)
    if op is Operator.CONTAINS:
        if isinstance(value, (list, tuple, set, frozenset)):
            return _normalise(target) in {_normalise(v) for v in value}
        return _normalise(target) in _normalise(value)
    if op is Operator.IN:
        if isinstance(target, (list, tuple, set, frozenset)):
            return _normalise(value) in {_normalise(t) for t in target}
        return _normalise(value) == _normalise(target)
    if op is Operator.NOT_IN:
        if isinstance(target, (list, tuple, set, frozenset)):
            return _normalise(value) not in {_normalise(t) for t in target}
        return _normalise(value) != _normalise(target)
    return False


def _normalise(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    return v


def _try_fire(rule: RuleDefinition, entity: dict[str, Any]) -> dict[str, Any] | None:
    conditions_met: list[str] = []
    for cond in rule.conditions:
        field_val = entity.get(cond.field)
        if cond.operator is not Operator.EXISTS and field_val is None:
            return None
        if not _evaluate_condition(cond, field_val):
            return None
        conditions_met.append(cond.field)
    outputs: dict[str, Any] = {}
    for out in rule.outputs:
        outputs[out.field] = out.value_expr
    return {"conditions_met": conditions_met, "outputs": outputs}


def infer(entity_fields: dict[str, Any], registry: RuleRegistry) -> InferenceResult:
    working = dict(entity_fields)
    all_fired: list[RuleFired] = []
    derivation_chains: dict[str, list[str]] = {}
    best_output: dict[str, tuple[Any, int, float, str]] = {}
    total_evaluated = 0
    total_skipped = 0

    for cascade in range(MAX_CASCADE_DEPTH + 1):
        available = set(working.keys())
        candidates = registry.candidates_for(available)
        new_fields_this_cascade: dict[str, Any] = {}
        fired_this_cascade = 0

        for rule in candidates:
            if not rule.trigger_fields.issubset(available):
                total_skipped += 1
                continue
            total_evaluated += 1
            result = _try_fire(rule, working)
            if result is None:
                continue

            fired_this_cascade += 1
            fired_record = RuleFired(
                rule_id=rule.rule_id,
                conditions_met=result["conditions_met"],
                outputs_produced=result["outputs"],
                confidence=rule.confidence,
                priority=rule.priority,
                cascade_level=cascade,
            )
            all_fired.append(fired_record)

            for field_name, field_value in result["outputs"].items():
                existing = best_output.get(field_name)
                if existing is not None:
                    _, ex_pri, ex_conf, _ = existing
                    if (rule.priority, rule.confidence) <= (ex_pri, ex_conf):
                        continue
                best_output[field_name] = (field_value, rule.priority, rule.confidence, rule.rule_id)
                derivation_chains.setdefault(field_name, []).append(rule.rule_id)
                if field_name not in working:
                    new_fields_this_cascade[field_name] = field_value

        working.update(new_fields_this_cascade)

        if fired_this_cascade == 0 or cascade == MAX_CASCADE_DEPTH:
            break

    derived: dict[str, Any] = {k: v[0] for k, v in best_output.items()}
    confidences = [v[2] for v in best_output.values()]
    min_conf = min(confidences) if confidences else 1.0

    return InferenceResult(
        derived_fields=derived,
        rules_fired=all_fired,
        rules_evaluated=total_evaluated,
        rules_skipped=total_skipped,
        derivation_chains=derivation_chains,
        inference_confidence=round(min_conf, 4),
        cascade_depth=min(cascade + 1, MAX_CASCADE_DEPTH) if all_fired else 0,
    )
