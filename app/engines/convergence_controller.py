"""
Convergence Controller — Multi-pass enrichment→inference loop.

Orchestrates the Schema Discovery Loop:
  Pass 1: Broad discovery (no target schema constraint)
  Pass 2+: Surgical targeting (meta_prompt_planner directs what to research)
  Each pass: enrich → infer → delta check → continue or converge

Config: max_passes=3, convergence_threshold=2.0, min_delta=0.05

Consumed by: chassis handlers.py (action="enrich" with mode="converge")
Produces: Final EnrichResponse with merged fields from all passes + inference results
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from ..models.schemas import EnrichRequest, EnrichResponse
from ..core.config import Settings
from ..services.idempotency import IdempotencyStore
from .meta_prompt_planner import MetaPromptPlanner, SearchPlan

# TODO(P1): convergence_controller uses InferenceBridge v1 API (.run(), .derived_fields).
# inference_bridge_v2.py has a different API (build_derivation_graph + run_inference).
# Migration requires: (1) adapter class wrapping v2 API, or (2) rewrite controller
# to use v2 API directly. See gap analysis for details. Do NOT just swap imports.
from .inference_bridge import InferenceBridge

logger = structlog.get_logger("convergence_controller")

MAX_PASSES = 3
CONVERGENCE_THRESHOLD = 2.0
MIN_DELTA = 0.05


@dataclass
class PassResult:
    """Result of a single enrichment+inference pass."""

    pass_number: int
    enriched_fields: dict[str, Any] = field(default_factory=dict)
    inferred_fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    tokens_used: int = 0
    search_plan: SearchPlan | None = None
    inference_fired: int = 0


@dataclass
class ConvergenceState:
    """Accumulated state across all passes."""

    known_fields: dict[str, Any] = field(default_factory=dict)
    confidence_map: dict[str, float] = field(default_factory=dict)
    inferred_fields: dict[str, Any] = field(default_factory=dict)
    pass_results: list[PassResult] = field(default_factory=list)
    total_tokens: int = 0
    converged: bool = False
    convergence_reason: str = ""


async def run_convergence_loop(
    request: EnrichRequest,
    settings: Settings,
    kb_resolver,
    idem_store: IdempotencyStore | None = None,
    enricher=None,
    inference_rules: list[dict] | None = None,
    domain_hints: dict[str, Any] | None = None,
) -> EnrichResponse:
    """
    Multi-pass convergence loop.

    Parameters
    ----------
    request : EnrichRequest
        The original enrichment request from Odoo/Salesforce/CLI.
    settings : Settings
        L9 env-var-driven settings.
    kb_resolver : KBResolver
        Selective KB fragment injector.
    idem_store : IdempotencyStore | None
        Redis idempotency cache.
    enricher : callable | None
        The single-pass enrich_entity function. Injected to avoid circular import.
    inference_rules : list[dict] | None
        YAML-loaded inference rules for this domain.
    domain_hints : dict | None
        enrichment_hints from domain YAML (priority_fields, objective_template, etc.)
    """
    start = time.monotonic()
    state = ConvergenceState()
    planner = MetaPromptPlanner()
    bridge = InferenceBridge(rules=inference_rules or [])

    # Seed known_fields from the entity's existing data
    state.known_fields = {k: v for k, v in request.entity.items() if v is not None}

    for pass_num in range(1, MAX_PASSES + 1):
        logger.info(
            "pass_started",
            pass_number=pass_num,
            known_fields=len(state.known_fields),
            inferred_fields=len(state.inferred_fields),
        )

        # --- META-PROMPT PLANNING ---
        search_plan = planner.plan(
            entity=state.known_fields,
            known_fields=state.confidence_map,
            inferred_fields=state.inferred_fields,
            domain_hints=domain_hints or {},
            inference_rule_catalog=bridge.get_rule_catalog(),
            pass_number=pass_num,
        )

        # --- BUILD PASS-SPECIFIC REQUEST ---
        pass_request = _build_pass_request(request, search_plan, state, pass_num)

        # --- SINGLE-PASS ENRICHMENT ---
        if enricher is None:
            from ..engines.enrichment_orchestrator import enrich_entity

            enricher = enrich_entity

        pass_response: EnrichResponse = await enricher(
            pass_request, settings, kb_resolver, idem_store
        )

        # --- COLLECT ENRICHED FIELDS ---
        pass_result = PassResult(
            pass_number=pass_num,
            enriched_fields=pass_response.fields or {},
            confidence=pass_response.confidence,
            tokens_used=pass_response.tokens_used,
            search_plan=search_plan,
        )

        # Merge into accumulated state
        for field_name, value in pass_result.enriched_fields.items():
            state.known_fields[field_name] = value
            state.confidence_map[field_name] = pass_response.confidence

        state.total_tokens += pass_result.tokens_used

        # --- INFERENCE PASS ---
        inference_result = bridge.run(
            entity=state.known_fields,
            confidence_map=state.confidence_map,
        )
        pass_result.inferred_fields = inference_result.derived_fields
        pass_result.inference_fired = inference_result.rules_fired

        for field_name, value in inference_result.derived_fields.items():
            state.inferred_fields[field_name] = value
            state.known_fields[field_name] = value
            state.confidence_map[field_name] = inference_result.confidence_map.get(field_name, 0.7)

        state.pass_results.append(pass_result)

        # --- CONVERGENCE CHECK ---
        if pass_num >= 2:
            prev = state.pass_results[-2]
            delta = abs(pass_result.confidence - prev.confidence)
            new_fields = len(pass_result.enriched_fields) + len(pass_result.inferred_fields)
            prev_fields = len(prev.enriched_fields) + len(prev.inferred_fields)

            if delta < MIN_DELTA and new_fields <= prev_fields:
                state.converged = True
                state.convergence_reason = (
                    f"delta={delta:.3f} < {MIN_DELTA}, "
                    f"new_fields={new_fields} <= prev={prev_fields}"
                )
                logger.info("converged", reason=state.convergence_reason, pass_number=pass_num)
                break

        if search_plan.mode == "verification":
            state.converged = True
            state.convergence_reason = "verification_pass_complete"
            break

    elapsed = int((time.monotonic() - start) * 1000)

    # --- ASSEMBLE FINAL RESPONSE ---
    all_fields = {**state.known_fields}
    # Remove original entity fields that weren't enriched/inferred
    original_keys = set(request.entity.keys())
    enriched_or_inferred = set()
    for pr in state.pass_results:
        enriched_or_inferred.update(pr.enriched_fields.keys())
        enriched_or_inferred.update(pr.inferred_fields.keys())
    final_fields = {k: v for k, v in all_fields.items() if k in enriched_or_inferred}

    avg_confidence = sum(state.confidence_map.get(k, 0) for k in final_fields) / max(
        len(final_fields), 1
    )

    return EnrichResponse(
        fields=final_fields,
        confidence=round(avg_confidence, 4),
        variation_count=sum(pr.tokens_used for pr in state.pass_results),
        uncertainty_score=len(state.pass_results),
        inference_version="v3.0.0-convergence",
        processing_time_ms=elapsed,
        tokens_used=state.total_tokens,
        state="completed",
        inferences=[
            {
                "pass": pr.pass_number,
                "mode": pr.search_plan.mode if pr.search_plan else "unknown",
                "enriched": list(pr.enriched_fields.keys()),
                "inferred": list(pr.inferred_fields.keys()),
                "confidence": pr.confidence,
                "rules_fired": pr.inference_fired,
            }
            for pr in state.pass_results
        ],
    )


def _build_pass_request(
    original: EnrichRequest,
    plan: SearchPlan,
    state: ConvergenceState,
    pass_number: int,
) -> EnrichRequest:
    """Build a pass-specific EnrichRequest from the search plan."""
    enriched_entity = {**original.entity, **state.known_fields, **state.inferred_fields}

    pass_objective = plan.objective or original.objective
    pass_schema = None
    if plan.target_fields:
        pass_schema = {f: "string" for f in plan.target_fields}
    elif original.schema:
        pass_schema = original.schema

    return EnrichRequest(
        entity=enriched_entity,
        object_type=original.object_type,
        schema=pass_schema,
        objective=pass_objective,
        kb_context=plan.kb_context or original.kb_context,
        consensus_threshold=original.consensus_threshold,
        max_variations=plan.variation_budget or original.max_variations,
        idempotency_key=None,
    )
