"""Universal enrichment pipeline — the single async orchestrator.

KB resolve → prompt build → fan-out Perplexity variations →
validate → consensus → uncertainty → response.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from .config import Settings
from .circuit_breaker import CircuitBreaker
from .kb_resolver import KBResolver
from .perplexity_client import query_perplexity
from .prompt_builder import build_variation_prompts
from .validation_engine import validate_response
from .consensus_engine import synthesize
from .uncertainty_engine import apply_uncertainty
from .schemas import EnrichmentRequest, EnrichmentResponse

logger = structlog.get_logger("pipeline")


async def enrich_pipeline(
    request: EnrichmentRequest,
    settings: Settings,
    breaker: CircuitBreaker,
    kb_resolver: KBResolver,
) -> EnrichmentResponse:
    t0 = time.monotonic()

    # 1. KB resolution (never raises)
    kb_ctx = kb_resolver.resolve(
        kb_context=request.kb_context,
        entity=request.entity,
    )

    # 2. Build N variation prompts
    prompts = build_variation_prompts(
        request=request,
        kb_context=kb_ctx,
        n=min(
            request.max_variations or settings.default_max_variations,
            settings.max_concurrent_variations,
        ),
    )

    # 3. Fan-out to Perplexity (bounded concurrency)
    sem = asyncio.Semaphore(settings.max_concurrent_variations)

    async def _call(payload: dict) -> dict | None:
        async with sem:
            try:
                resp = await query_perplexity(
                    payload=payload,
                    api_key=settings.perplexity_api_key,
                    breaker=breaker,
                    timeout=settings.default_timeout_seconds,
                )
                return resp.data
            except RuntimeError as exc:
                logger.warning("variation_failed", error=str(exc))
                return None

    raw_results = await asyncio.gather(*[_call(p) for p in prompts])
    valid_results = [r for r in raw_results if r is not None]

    # 4. Validate each
    validated = []
    for raw in valid_results:
        v = validate_response(raw, request)
        if v is not None:
            validated.append(v)

    # 5. Consensus
    consensus = synthesize(
        payloads=validated,
        threshold=request.consensus_threshold or settings.default_consensus_threshold,
        total_attempted=len(prompts),
    )

    # 6. Uncertainty policy
    final_fields, final_confidence, flags = apply_uncertainty(
        fields=consensus.get("fields", {}),
        confidence=consensus.get("confidence", 0.0),
    )

    elapsed = round(time.monotonic() - t0, 3)
    logger.info(
        "pipeline_complete",
        variations_attempted=len(prompts),
        variations_valid=len(validated),
        confidence=final_confidence,
        elapsed_s=elapsed,
    )

    return EnrichmentResponse(
        fields=final_fields,
        confidence=final_confidence,
        flags=flags,
        variations_attempted=len(prompts),
        variations_valid=len(validated),
        kb_fragments=kb_ctx.get("fragment_ids", []),
        elapsed_seconds=elapsed,
    )
