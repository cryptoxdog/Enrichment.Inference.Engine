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

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from ..models.schemas import EnrichRequest, EnrichResponse
from ..core.config import Settings
from ..services.idempotency import IdempotencyStore
from .meta_prompt_planner import MetaPromptPlanner, SearchPlan
from .inference_bridge_adapter import InferenceBridge
from .field_classifier import auto_classify_domain, DomainClassification
from .search_optimizer import (
    EntitySignals,
    SonarConfig,
    resolve_from_classification,
)
from .convergence.cost_tracker import CostTracker

logger = structlog.get_logger("convergence_controller")

MAX_PASSES = 3
CONVERGENCE_THRESHOLD = 2.0
MIN_DELTA = 0.05

# ── Module-level classification cache ──────────────────────
_classification_cache: dict[str, DomainClassification] = {}


def _cache_key(domain_spec: dict[str, Any]) -> str:
    """Deterministic hash of a domain spec for caching."""
    domain_name = domain_spec.get("domain") or domain_spec.get("metadata", {}).get(
        "domain", "unknown"
    )
    # Include field count for collision avoidance
    ontology = domain_spec.get("ontology", domain_spec)
    nodes = ontology.get("nodes", ontology.get("entities", {}))
    node_count = len(nodes) if isinstance(nodes, (dict, list)) else 0
    raw = f"{domain_name}:{node_count}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_or_classify_domain(domain_spec: dict[str, Any]) -> DomainClassification:
    """Classify domain fields with module-level caching."""
    key = _cache_key(domain_spec)
    if key in _classification_cache:
        logger.debug("classification_cache_hit", key=key)
        return _classification_cache[key]
    classification = auto_classify_domain(domain_spec)
    _classification_cache[key] = classification
    logger.info(
        "classification_cached",
        domain=classification.domain,
        fields=sum(classification.stats.values()),
        stats=classification.stats,
    )
    return classification


@dataclass
class PassResult:
    """Result of a single enrichment+inference pass."""

    pass_number: int
    enriched_fields: dict[str, Any] = field(default_factory=dict)
    inferred_fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    tokens_used: int = 0
    search_plan: SearchPlan | None = None
    sonar_config: SonarConfig | None = None
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
    unlock_map: dict[str, float] = field(default_factory=dict)


async def run_convergence_loop(
    request: EnrichRequest,
    settings: Settings,
    kb_resolver,
    idem_store: IdempotencyStore | None = None,
    enricher=None,
    inference_rules: list[dict] | None = None,
    domain_hints: dict[str, Any] | None = None,
    domain_spec: dict[str, Any] | None = None,
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
    domain_spec : dict | None
        Full domain YAML for field classification and search optimization.
    """
    start = time.monotonic()
    state = ConvergenceState()
    planner = MetaPromptPlanner()
    bridge = InferenceBridge(
        rules=inference_rules or [],
        domain_spec=domain_spec,
    )

    # ── Domain classification (cached per domain) ──────────
    domain_classification: DomainClassification | None = None
    if domain_spec:
        domain_classification = get_or_classify_domain(domain_spec)
        logger.info(
            "domain_classified",
            domain=domain_classification.domain,
            stats=domain_classification.stats,
            gate_fields=sorted(domain_classification.gate_fields),
        )

    # ── Cost tracker ───────────────────────────────────────
    max_budget = getattr(settings, "max_budget_tokens", 30000)
    cost_tracker = CostTracker(max_budget_tokens=max_budget)

    # Seed known_fields from the entity's existing data
    state.known_fields = {k: v for k, v in request.entity.items() if v is not None}

    for pass_num in range(1, MAX_PASSES + 1):
        logger.info(
            "pass_started",
            pass_number=pass_num,
            known_fields=len(state.known_fields),
            inferred_fields=len(state.inferred_fields),
        )

        # ── Budget check ──────────────────────────────────
        if not cost_tracker.can_continue():
            logger.info("budget_exhausted", total_tokens=cost_tracker.total_tokens)
            state.converged = True
            state.convergence_reason = "budget_exhausted"
            break

        # --- META-PROMPT PLANNING ---
        search_plan = planner.plan(
            entity=state.known_fields,
            known_fields=state.confidence_map,
            inferred_fields=state.inferred_fields,
            domain_hints=domain_hints or {},
            inference_rule_catalog=bridge.get_rule_catalog(),
            pass_number=pass_num,
            unlock_map=state.unlock_map,
        )

        # ── Resolve optimal Sonar config for this pass ────
        sonar_config: SonarConfig | None = None
        if domain_classification and search_plan:
            total_domain_fields = sum(domain_classification.stats.values())
            null_field_count = max(0, total_domain_fields - len(state.known_fields))
            gate_critical_missing = len(
                domain_classification.gate_fields - set(state.known_fields.keys())
            )
            signals = EntitySignals(
                null_count=null_field_count,
                known_count=len(state.known_fields),
                avg_confidence=(
                    sum(state.confidence_map.values()) / max(len(state.confidence_map), 1)
                ),
                gate_fields_missing=gate_critical_missing,
                has_website=bool(state.known_fields.get("website")),
                pass_number=pass_num,
                allocated_tokens=cost_tracker.budget_remaining(),
            )
            sonar_config = resolve_from_classification(
                search_plan_mode=search_plan.mode,
                target_fields=search_plan.target_fields or [],
                signals=signals,
                classification=domain_classification,
                budget_tokens=cost_tracker.budget_remaining(),
            )
            logger.info(
                "sonar_config_resolved",
                pass_number=pass_num,
                model=sonar_config.model.value,
                context_size=sonar_config.search_context_size.value,
                variations=sonar_config.variations,
                estimated_cost=sonar_config.estimated_cost_per_call,
                disable_search=sonar_config.disable_search,
                reason=sonar_config.resolution_reason,
            )

            # Wire cost estimate into tracker
            if sonar_config.estimated_cost_per_call > 0:
                cost_tracker._rate_per_1k = _rate_from_sonar_config(sonar_config)

        # --- BUILD PASS-SPECIFIC REQUEST ---
        pass_request = _build_pass_request(request, search_plan, state, pass_num)

        # --- SINGLE-PASS ENRICHMENT ---
        if enricher is None:
            from ..engines.enrichment_orchestrator import enrich_entity

            enricher = enrich_entity

        pass_response: EnrichResponse = await enricher(
            pass_request,
            settings,
            kb_resolver,
            idem_store,
            sonar_config=sonar_config,
        )

        # --- COLLECT ENRICHED FIELDS ---
        pass_result = PassResult(
            pass_number=pass_num,
            enriched_fields=pass_response.fields or {},
            confidence=pass_response.confidence,
            tokens_used=pass_response.tokens_used,
            search_plan=search_plan,
            sonar_config=sonar_config,
        )

        # Merge into accumulated state
        for field_name, value in pass_result.enriched_fields.items():
            state.known_fields[field_name] = value
            state.confidence_map[field_name] = pass_response.confidence

        state.total_tokens += pass_result.tokens_used
        cost_tracker.record_pass(pass_num, pass_result.tokens_used)

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

        if hasattr(inference_result, "unlock_map"):
            state.unlock_map = inference_result.unlock_map

        state.pass_results.append(pass_result)

        # --- CONVERGENCE CHECK ---
        if pass_num >= 2:
            converged, reason = _check_pass_convergence(pass_result, state.pass_results[-2])
            if converged:
                state.converged = True
                state.convergence_reason = reason
                logger.info("converged", reason=reason)
                break

        if search_plan.mode == "verification":
            state.converged = True
            state.convergence_reason = "verification_pass_complete"
            break

    elapsed = int((time.monotonic() - start) * 1000)
    return _assemble_convergence_response(
        state, request, elapsed, domain_classification, cost_tracker
    )


def _rate_from_sonar_config(config: SonarConfig) -> float:
    """Extract cost rate from sonar config for the cost tracker."""
    from .search_optimizer import MODEL_COST_PER_1K, CONTEXT_COST_MULTIPLIER

    base = MODEL_COST_PER_1K.get(config.model, 0.005)
    mult = CONTEXT_COST_MULTIPLIER.get(config.search_context_size, 1.0)
    return base * mult


def _check_pass_convergence(
    current: PassResult,
    prev: PassResult,
) -> tuple[bool, str]:
    """Return (converged, reason) by comparing consecutive pass results."""
    delta = abs(current.confidence - prev.confidence)
    new_fields = len(current.enriched_fields) + len(current.inferred_fields)
    prev_fields = len(prev.enriched_fields) + len(prev.inferred_fields)
    if delta < MIN_DELTA and new_fields <= prev_fields:
        reason = f"delta={delta:.3f} < {MIN_DELTA}, new_fields={new_fields} <= prev={prev_fields}"
        return True, reason
    return False, ""


def _assemble_convergence_response(
    state: ConvergenceState,
    request: "EnrichRequest",
    elapsed: int,
    domain_classification: DomainClassification | None = None,
    cost_tracker: CostTracker | None = None,
) -> "EnrichResponse":
    """Build the final EnrichResponse from accumulated convergence state."""
    enriched_or_inferred: set[str] = set()
    for pr in state.pass_results:
        enriched_or_inferred.update(pr.enriched_fields.keys())
        enriched_or_inferred.update(pr.inferred_fields.keys())
    final_fields = {k: v for k, v in state.known_fields.items() if k in enriched_or_inferred}
    avg_confidence = sum(state.confidence_map.get(k, 0) for k in final_fields) / max(
        len(final_fields), 1
    )

    # Build per-pass inference metadata
    pass_inferences = []
    for pr in state.pass_results:
        entry: dict[str, Any] = {
            "pass": pr.pass_number,
            "mode": pr.search_plan.mode if pr.search_plan else "unknown",
            "enriched": list(pr.enriched_fields.keys()),
            "inferred": list(pr.inferred_fields.keys()),
            "confidence": pr.confidence,
            "rules_fired": pr.inference_fired,
        }
        if pr.sonar_config:
            entry["sonar_model"] = pr.sonar_config.model.value
            entry["sonar_context"] = pr.sonar_config.search_context_size.value
            entry["sonar_cost"] = pr.sonar_config.estimated_cost_per_call
        pass_inferences.append(entry)

    # Build feature_vector with classification + cost metadata
    feature_vector: dict[str, Any] = {}
    if domain_classification:
        feature_vector["domain_classification"] = domain_classification.to_dict()
    if cost_tracker:
        feature_vector["cost_summary"] = cost_tracker.to_summary(
            total_fields_discovered=len(final_fields)
        ).model_dump()

    return EnrichResponse(
        fields=final_fields,
        confidence=round(avg_confidence, 4),
        variation_count=sum(pr.tokens_used for pr in state.pass_results),
        uncertainty_score=len(state.pass_results),
        inference_version="v3.0.0-convergence",
        processing_time_ms=elapsed,
        tokens_used=state.total_tokens,
        state="completed",
        inferences=pass_inferences,
        feature_vector=feature_vector if feature_vector else None,
    )


def _build_pass_request(
    original: EnrichRequest,
    plan: SearchPlan,
    state: ConvergenceState,
    pass_num: int = 1,
) -> EnrichRequest:
    """Build a pass-specific EnrichRequest from the search plan."""
    enriched_entity = {**original.entity, **state.known_fields, **state.inferred_fields}

    pass_objective = plan.objective or original.objective
    pass_schema = None
    if plan.target_fields:
        pass_schema = {f: "string" for f in plan.target_fields}
    elif original.schema_:
        pass_schema = original.schema_

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
