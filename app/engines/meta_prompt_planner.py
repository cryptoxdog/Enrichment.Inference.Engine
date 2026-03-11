"""
Meta-Prompt Planner — The Missing Piece.

Sits between convergence_controller and prompt_builder.
Each pass, it analyzes what's known, what's missing, what inference rules
could fire if specific fields were filled, and emits a SearchPlan.

This is NOT a prompt. It's a PLAN for what the prompt should ask about and why.
The prompt_builder then turns the plan into the actual Sonar payload.

Three modes:
  - discovery: Pass 1, zero prior context, maximize surface area
  - targeted: Pass 2+, surgical field targeting based on inference-gap analysis
  - verification: Final pass, confirm single remaining unknowns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchPlan:
    """What the prompt builder should construct."""

    mode: str  # "discovery" | "targeted" | "verification"
    target_fields: list[str] = field(default_factory=list)
    objective: str | None = None
    strategy: str = "broad"  # "broad" | "surgical" | "confirm"
    reasoning: str = ""
    kb_context: str | None = None
    variation_budget: int | None = None
    information_gain_scores: dict[str, float] = field(default_factory=dict)


class MetaPromptPlanner:
    """
    Analyzes entity state and inference rule catalog to produce
    an optimal search plan for each convergence pass.
    """

    def plan(
        self,
        entity: dict[str, Any],
        known_fields: dict[str, float],
        inferred_fields: dict[str, Any],
        domain_hints: dict[str, Any],
        inference_rule_catalog: list[dict],
        pass_number: int,
    ) -> SearchPlan:
        if pass_number == 1:
            return self._plan_discovery(entity, domain_hints)

        missing = self._find_high_value_gaps(
            entity, known_fields, inferred_fields, domain_hints, inference_rule_catalog
        )

        if len(missing) <= 2:
            return self._plan_verification(missing, entity, domain_hints)

        return self._plan_targeted(missing, entity, known_fields, domain_hints)

    def _plan_discovery(self, entity: dict[str, Any], hints: dict[str, Any]) -> SearchPlan:
        priority = hints.get("priority_fields", [])
        objective_template = hints.get(
            "objective_template",
            "Research this entity's capabilities, certifications, "
            "equipment, material handling, and operational characteristics.",
        )
        entity_name = entity.get("name", entity.get("Name", "unknown"))
        objective = objective_template.replace("{name}", str(entity_name))

        return SearchPlan(
            mode="discovery",
            target_fields=priority if priority else [],
            objective=objective,
            strategy="broad",
            reasoning=(
                f"Pass 1: zero prior enrichment context. "
                f"{'Prioritizing ' + str(len(priority)) + ' hint fields. ' if priority else ''}"
                f"Maximize surface area for schema discovery."
            ),
            kb_context=hints.get("kb_context"),
            variation_budget=hints.get("max_variations_discovery", 5),
        )

    def _plan_targeted(
        self,
        missing: list[dict],
        entity: dict[str, Any],
        known_fields: dict[str, float],
        hints: dict[str, Any],
    ) -> SearchPlan:
        target_fields = [m["field"] for m in missing[:8]]
        gain_scores = {m["field"]: m["gain"] for m in missing}

        top_reason = missing[0] if missing else {}
        entity_name = entity.get("name", entity.get("Name", "unknown"))

        return SearchPlan(
            mode="targeted",
            target_fields=target_fields,
            objective=(
                f"For {entity_name}, research specifically: "
                f"{', '.join(target_fields)}. "
                f"Primary reason: {top_reason.get('reason', 'high information gain')}."
            ),
            strategy="surgical",
            reasoning=(
                f"Pass 2+: {len(known_fields)} fields known, "
                f"{len(missing)} high-value gaps identified. "
                f"Top target: {top_reason.get('field', '?')} "
                f"(gain={top_reason.get('gain', 0):.2f}, "
                f"reason={top_reason.get('reason', '')})."
            ),
            kb_context=hints.get("kb_context"),
            variation_budget=min(3, hints.get("max_variations_targeted", 3)),
            information_gain_scores=gain_scores,
        )

    def _plan_verification(
        self,
        missing: list[dict],
        entity: dict[str, Any],
        hints: dict[str, Any],
    ) -> SearchPlan:
        target_fields = [m["field"] for m in missing]
        entity_name = entity.get("name", entity.get("Name", "unknown"))

        return SearchPlan(
            mode="verification",
            target_fields=target_fields,
            objective=(
                f"Confirm for {entity_name}: {', '.join(target_fields)}. "
                f"Low uncertainty remains — verify or fill these final fields."
            ),
            strategy="confirm",
            reasoning=(
                f"Verification pass: only {len(missing)} field(s) remaining. Minimal token budget."
            ),
            kb_context=hints.get("kb_context"),
            variation_budget=2,
        )

    def _find_high_value_gaps(
        self,
        entity: dict[str, Any],
        known_fields: dict[str, float],
        inferred_fields: dict[str, Any],
        hints: dict[str, Any],
        rule_catalog: list[dict],
    ) -> list[dict]:
        """
        Score every missing field by information gain:
        - Fields that unlock inference rules score highest
        - Priority fields from domain hints score high
        - Fields with low confidence score medium
        """
        all_known = set(entity.keys())
        priority = set(hints.get("priority_fields", []))
        gaps: list[dict] = []

        # Fields that would unlock inference rules
        for rule in rule_catalog:
            required = set(rule.get("requires", []))
            produces = set(rule.get("produces", []))
            missing_inputs = required - all_known
            if missing_inputs and not produces.issubset(all_known):
                unlock_value = len(produces - all_known)
                for f in missing_inputs:
                    gaps.append(
                        {
                            "field": f,
                            "gain": 0.4 + (0.15 * unlock_value),
                            "reason": (
                                f"unlocks rule '{rule.get('name', '?')}' "
                                f"→ {', '.join(produces - all_known)}"
                            ),
                        }
                    )

        # Priority fields from domain hints not yet known
        for f in priority:
            if f not in all_known:
                gaps.append(
                    {
                        "field": f,
                        "gain": 0.6,
                        "reason": "domain priority field",
                    }
                )

        # Low-confidence fields worth re-researching
        for f, conf in known_fields.items():
            if conf < 0.5:
                gaps.append(
                    {
                        "field": f,
                        "gain": 0.3 + (0.5 - conf),
                        "reason": f"low confidence ({conf:.2f})",
                    }
                )

        # Deduplicate by field, keep highest gain
        seen: dict[str, dict] = {}
        for g in gaps:
            fname = g["field"]
            if fname not in seen or g["gain"] > seen[fname]["gain"]:
                seen[fname] = g

        return sorted(seen.values(), key=lambda x: x["gain"], reverse=True)
