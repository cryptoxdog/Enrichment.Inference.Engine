"""
Core enrichment orchestrator — the pipeline.

Sequence:
  1. Check idempotency cache
  2. Parse target schema
  3. Resolve KB fragments (supplementary, never a gate)
  4. Compute uncertainty → adaptive variation budget
  5. Build prompt (schema-aware, entity-rich)
  6. Fire N async Sonar variations (bounded by semaphore)
  7. Validate each response (partial acceptance)
  8. Weighted consensus synthesis
  9. Assemble response with full provenance
  10. Cache idempotency key
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from ..core.config import Settings
from ..models.schemas import EnrichRequest, EnrichResponse
from ..services.circuit_breaker import CircuitBreaker
from ..services.consensus_engine import synthesize
from ..services.idempotency import IdempotencyStore
from ..services.perplexity_client import SonarResponse, query_perplexity
from ..services.prompt_builder import build_prompt, build_schema_hash
from ..services.uncertainty_engine import compute_uncertainty
from ..services.validation_engine import ValidationError, validate_response

logger = structlog.get_logger("orchestrator")

breaker = CircuitBreaker(failure_threshold=5, cooldown=60)


async def enrich_entity(
    request: EnrichRequest,
    settings: Settings,
    kb_resolver,
    idem_store: IdempotencyStore | None = None,
) -> EnrichResponse:
    """Full enrichment pipeline for a single entity."""
    start = time.monotonic()

    if request.idempotency_key and idem_store:
        cached = await idem_store.get(request.idempotency_key)
        if cached:
            return EnrichResponse(**cached)

    try:
        target_schema = request.schema_

        kb_data = kb_resolver.resolve(
            kb_context=request.kb_context,
            entity=request.entity,
            max_fragments=3,
        )

        uncertainty = compute_uncertainty(
            entity=request.entity,
            target_schema=target_schema,
            max_variations=request.max_variations,
        )
        variation_count = min(uncertainty, request.max_variations)

        logger.info(
            "pipeline_started",
            entity_name=request.entity.get("Name", request.entity.get("name", "?")),
            object_type=request.object_type,
            variations=variation_count,
            kb_fragments=len(kb_data["fragment_ids"]),
        )

        payload = build_prompt(
            entity=request.entity,
            object_type=request.object_type,
            objective=request.objective,
            target_schema=target_schema,
            kb_context_text=kb_data["context_text"],
            model=settings.perplexity_model,
        )

        sem = asyncio.Semaphore(settings.max_concurrent_variations)

        async def _call() -> SonarResponse:
            async with sem:
                return await query_perplexity(
                    payload=payload,
                    api_key=settings.perplexity_api_key,
                    breaker=breaker,
                    timeout=settings.default_timeout_seconds,
                )

        tasks = [_call() for _ in range(variation_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[dict[str, Any]] = []
        raw_payloads: list[dict[str, Any]] = []
        errors: list[str] = []
        total_tokens = 0

        for result in results:
            if isinstance(result, Exception):
                errors.append(f"{type(result).__name__}: {result}")
                logger.warning("variation_failed", error=str(result))
                continue
            if not isinstance(result, SonarResponse):
                continue

            total_tokens += result.tokens_used
            raw_payloads.append(result.data)

            try:
                validated = validate_response(result.data, target_schema)
                valid.append(validated)
            except ValidationError as e:
                errors.append(f"validation: {e}")
                continue

        elapsed = int((time.monotonic() - start) * 1000)

        if not valid:
            return EnrichResponse(
                state="failed",
                failure_reason=f"no_valid_responses ({len(errors)} errors: {'; '.join(errors[:3])})",
                variation_count=variation_count,
                consensus_threshold=request.consensus_threshold,
                uncertainty_score=uncertainty,
                kb_content_hash=kb_data["content_hash"],
                kb_fragment_ids=kb_data["fragment_ids"],
                kb_files_consulted=kb_data["kb_files"],
                tokens_used=total_tokens,
                processing_time_ms=elapsed,
            )

        synthesis = synthesize(
            valid,
            request.consensus_threshold,
            total_attempted=variation_count,
        )

        if not synthesis["fields"]:
            return EnrichResponse(
                state="failed",
                failure_reason="no_fields_above_consensus_threshold",
                confidence=synthesis["confidence"],
                variation_count=variation_count,
                consensus_threshold=request.consensus_threshold,
                uncertainty_score=uncertainty,
                kb_content_hash=kb_data["content_hash"],
                kb_fragment_ids=kb_data["fragment_ids"],
                kb_files_consulted=kb_data["kb_files"],
                enrichment_payload={"raw": raw_payloads},
                tokens_used=total_tokens,
                processing_time_ms=elapsed,
            )

        schema_hash = build_schema_hash(target_schema)

        resp = EnrichResponse(
            fields=synthesis["fields"],
            confidence=round(synthesis["confidence"], 4),
            kb_content_hash=kb_data["content_hash"],
            kb_fragment_ids=kb_data["fragment_ids"],
            kb_files_consulted=kb_data["kb_files"],
            variation_count=variation_count,
            consensus_threshold=request.consensus_threshold,
            uncertainty_score=uncertainty,
            inference_version="v2.2.0",
            processing_time_ms=elapsed,
            tokens_used=total_tokens,
            enrichment_payload={"raw": raw_payloads},
            feature_vector={
                "schema_hash": schema_hash,
                "fields_enriched": list(synthesis["fields"].keys()),
            },
            state="completed",
        )

        if request.idempotency_key and idem_store:
            await idem_store.set(request.idempotency_key, resp.model_dump())

        logger.info(
            "pipeline_completed",
            fields_enriched=len(synthesis["fields"]),
            confidence=resp.confidence,
            tokens=total_tokens,
            elapsed_ms=elapsed,
        )

        return resp

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("pipeline_fatal", error=str(exc), exc_info=True)
        return EnrichResponse(
            state="failed",
            failure_reason=str(exc),
            processing_time_ms=elapsed,
        )


async def enrich_batch(
    requests: list[EnrichRequest],
    settings: Settings,
    kb_resolver,
    idem_store: IdempotencyStore | None = None,
) -> list[EnrichResponse]:
    """Batch enrichment with bounded concurrency."""
    sem = asyncio.Semaphore(10)

    async def _bounded(req: EnrichRequest) -> EnrichResponse:
        async with sem:
            return await enrich_entity(req, settings, kb_resolver, idem_store)

    results = await asyncio.gather(*[_bounded(r) for r in requests])
    return list(results)
