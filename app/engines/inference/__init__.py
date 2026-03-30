"""Deterministic inference engine — rule evaluation, grading, YAML rule loading."""

from .grade_engine import (
    GradeCondition,
    GradeDefinition,
    GradeResult,
    classify,
    load_grade_definitions,
)
from .rule_engine import (
    InferenceResult,
    RuleFired,
    infer,
)
from .rule_loader import (
    Operator,
    RuleCondition,
    RuleDefinition,
    RuleOutput,
    RuleRegistry,
    build_unlock_index,
    load_rules,
    rank_fields_by_unlock,
    reload_rules,
    score_unlock_potential,
)

__all__ = [
    # rule_loader.py
    "Operator",
    "RuleCondition",
    "RuleOutput",
    "RuleDefinition",
    "RuleRegistry",
    "load_rules",
    "reload_rules",
    "build_unlock_index",
    "score_unlock_potential",
    "rank_fields_by_unlock",
    # rule_engine.py
    "RuleFired",
    "InferenceResult",
    "infer",
    # grade_engine.py
    "GradeCondition",
    "GradeDefinition",
    "GradeResult",
    "classify",
    "load_grade_definitions",
]
