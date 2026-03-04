"""Grade/tier classification engine — matches feature vectors against grade envelopes."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.6


class GradeCondition(BaseModel):
    field: str
    min: float | None = None
    max: float | None = None
    value: Any = None
    values: list[Any] | None = None


class GradeDefinition(BaseModel):
    grade_id: str
    grade_label: str = ""
    conditions: list[GradeCondition] = Field(min_length=1)
    tier: str = ""
    application_class: str = ""
    quality_tier: str = ""
    description: str = ""


class GradeResult(BaseModel):
    grade_id: str
    grade_label: str
    tier: str
    application_class: str
    quality_tier: str
    match_score: float
    conditions_met: list[str] = Field(default_factory=list)
    conditions_missed: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    confidence: float = 0.0


def _evaluate_grade_condition(cond: GradeCondition, entity: dict[str, Any]) -> bool:
    val = entity.get(cond.field)
    if val is None:
        return False
    if cond.min is not None and cond.max is not None:
        try:
            return cond.min <= float(val) <= cond.max
        except (ValueError, TypeError):
            return False
    if cond.min is not None:
        try:
            return float(val) >= cond.min
        except (ValueError, TypeError):
            return False
    if cond.max is not None:
        try:
            return float(val) <= cond.max
        except (ValueError, TypeError):
            return False
    if cond.values is not None:
        if isinstance(val, (list, tuple, set)):
            return bool(set(str(v).lower() for v in val) & set(str(v).lower() for v in cond.values))
        return str(val).lower() in {str(v).lower() for v in cond.values}
    if cond.value is not None:
        return str(val).strip().lower() == str(cond.value).strip().lower()
    return False


def _score_grade(grade_def: GradeDefinition, entity: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    met: list[str] = []
    missed: list[str] = []
    for cond in grade_def.conditions:
        if _evaluate_grade_condition(cond, entity):
            met.append(cond.field)
        else:
            missed.append(cond.field)
    total = len(grade_def.conditions)
    score = len(met) / total if total > 0 else 0.0
    return score, met, missed


def classify(
    entity_fields: dict[str, Any],
    grade_defs: list[GradeDefinition],
    threshold: float = DEFAULT_THRESHOLD,
) -> GradeResult | None:
    if not grade_defs:
        return None

    best: GradeResult | None = None
    closest: GradeResult | None = None

    for gd in grade_defs:
        score, met, missed = _score_grade(gd, entity_fields)

        candidate = GradeResult(
            grade_id=gd.grade_id,
            grade_label=gd.grade_label,
            tier=gd.tier,
            application_class=gd.application_class,
            quality_tier=gd.quality_tier,
            match_score=round(score, 4),
            conditions_met=met,
            conditions_missed=missed,
            fallback_used=False,
            confidence=round(score, 4),
        )

        if score >= threshold:
            if best is None or score > best.match_score:
                best = candidate
        if closest is None or score > closest.match_score:
            closest = candidate

    if best is not None:
        return best

    if closest is not None and closest.match_score > 0:
        closest.fallback_used = True
        closest.confidence = round(closest.match_score * 0.7, 4)
        return closest

    return None


def load_grade_definitions(kb_data: dict[str, Any]) -> list[GradeDefinition]:
    raw_grades = kb_data.get("material_grades", kb_data.get("grades", []))
    defs: list[GradeDefinition] = []
    for idx, entry in enumerate(raw_grades):
        conditions_raw = entry.get("conditions", [])
        if not conditions_raw and "properties" in entry:
            conditions_raw = _properties_to_conditions(entry["properties"])
        if not conditions_raw:
            continue
        entry_norm = {
            "grade_id": entry.get("grade_id", entry.get("id", f"grade-{idx}")),
            "grade_label": entry.get("grade_label", entry.get("grade_name", "")),
            "conditions": conditions_raw,
            "tier": entry.get("tier", ""),
            "application_class": entry.get("application_class", ""),
            "quality_tier": entry.get("quality_tier", ""),
            "description": entry.get("description", ""),
        }
        try:
            defs.append(GradeDefinition.model_validate(entry_norm))
        except Exception as exc:
            logger.warning("Skipping grade #%d: %s", idx, exc)
    return defs


def _properties_to_conditions(props: dict[str, Any]) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    for field, spec in props.items():
        if isinstance(spec, dict):
            cond: dict[str, Any] = {"field": field}
            if "min" in spec:
                cond["min"] = spec["min"]
            if "max" in spec:
                cond["max"] = spec["max"]
            if "value" in spec:
                cond["value"] = spec["value"]
            if "values" in spec:
                cond["values"] = spec["values"]
            conditions.append(cond)
        else:
            conditions.append({"field": field, "value": spec})
    return conditions
