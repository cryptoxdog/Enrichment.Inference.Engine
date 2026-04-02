# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [api, convergence]
# tags: [L9_ENDPOINT, converge, packet-safe]
# owner: platform
# status: active
# --- /L9_META ---
"""
app/api/v1/converge.py

GAP #03: Replace converge endpoint stub with real execution loop.

POST /v1/converge accepts a ConvergeRequest, invokes
ConvergenceController.run(), persists via ResultStore, fires graph sync
and score invalidation hooks, and returns a ConvergeResponse.

PacketEnvelope compliance:
  - lineage_id generated per request (UUID4)
  - packet_id generated per request (UUID4)
  - Both forwarded to persistence and downstream hooks
  - content_hash computed from enriched_fields (deterministic SHA-256)
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.engines.convergence_controller import ConvergenceController
from app.services.graph_sync_hooks import invalidate_score_cache, trigger_graph_sync
from app.services.result_store import (
    EnrichmentResult,
    StorePersistenceError,
    get_result_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["convergence"])


class ConvergeRequest(BaseModel):
    """Inbound convergence request."""

    tenant_id: str
    entity_id: str
    raw_fields: dict[str, Any]
    max_passes: int = Field(default=5, ge=1, le=20)
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    domain: str | None = None


class ConvergeResponse(BaseModel):
    """Outbound convergence result."""

    entity_id: str
    tenant_id: str
    pass_count: int
    converged: bool
    confidence: float
    enriched_fields: dict[str, Any]
    inference_outputs: dict[str, Any]
    content_hash: str
    lineage_id: str
    packet_id: str


@router.post("/converge", response_model=ConvergeResponse)
async def converge_entity(request: ConvergeRequest) -> ConvergeResponse:
    """
    Execute the enrichment-inference convergence loop for a single entity.

    1. Instantiate ConvergenceController
    2. Run convergence loop (multi-pass: enrich → infer → re-enrich → converge)
    3. Persist result via ResultStore
    4. Fire graph sync + score invalidation hooks
    5. Return ConvergeResponse
    """
    lineage_id = str(uuid.uuid4())
    packet_id = str(uuid.uuid4())

    try:
        controller = ConvergenceController(
            tenant_id=request.tenant_id,
            entity_id=request.entity_id,
            max_passes=request.max_passes,
            confidence_threshold=request.confidence_threshold,
            domain=request.domain,
        )
        loop_result = await controller.run(raw_fields=request.raw_fields)
    except Exception as e:
        logger.error(
            "converge_controller_failed",
            extra={"entity_id": request.entity_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Convergence failed: {e}") from e

    enriched = loop_result.enriched_fields if hasattr(loop_result, "enriched_fields") else {}
    inference = loop_result.inference_outputs if hasattr(loop_result, "inference_outputs") else {}
    converged = loop_result.converged if hasattr(loop_result, "converged") else False
    confidence = loop_result.confidence if hasattr(loop_result, "confidence") else 0.0
    pass_count = loop_result.pass_count if hasattr(loop_result, "pass_count") else 0

    content_hash = hashlib.sha256(
        json.dumps(enriched, sort_keys=True, default=str).encode()
    ).hexdigest()

    # Persist
    store = get_result_store()
    result = EnrichmentResult(
        tenant_id=request.tenant_id,
        entity_id=request.entity_id,
        packet_id=packet_id,
        lineage_id=lineage_id,
        pass_number=pass_count,
        converged=converged,
        confidence=confidence,
        enriched_fields=enriched,
    )
    try:
        await store.save(result)
    except StorePersistenceError as e:
        logger.error("converge_persist_failed", extra={"error": str(e)}, exc_info=True)
        msg = "Failed to persist enrichment result"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=msg,
        ) from e

    # Graph sync + score invalidation (fire-and-forget)
    try:
        await trigger_graph_sync(
            entity_id=request.entity_id,
            tenant_id=request.tenant_id,
            enriched_fields=enriched,
            confidence=confidence,
            lineage_id=lineage_id,
            packet_id=packet_id,
        )
    except Exception as e:
        logger.error("converge_graph_sync_failed", extra={"error": str(e)}, exc_info=True)

    try:
        await invalidate_score_cache(
            entity_id=request.entity_id,
            tenant_id=request.tenant_id,
            lineage_id=lineage_id,
            packet_id=packet_id,
        )
    except Exception as e:
        logger.error("converge_score_invalidation_failed", extra={"error": str(e)}, exc_info=True)

    return ConvergeResponse(
        entity_id=request.entity_id,
        tenant_id=request.tenant_id,
        pass_count=pass_count,
        converged=converged,
        confidence=confidence,
        enriched_fields=enriched,
        inference_outputs=inference,
        content_hash=content_hash,
        lineage_id=lineage_id,
        packet_id=packet_id,
    )
