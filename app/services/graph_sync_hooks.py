# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [services, integration]
# tags: [L9_INTEGRATION, graph-sync, score-invalidation]
# owner: platform
# status: active
# --- /L9_META ---
"""
app/services/graph_sync_hooks.py

GAP #22: Graph sync + score invalidation hooks.

When an enrichment pass converges:
  1. trigger_graph_sync() → POST to GRAPH node /v1/sync with enriched fields
  2. invalidate_score_cache() → POST to SCORE node /v1/invalidate

Both calls forward lineage_id and packet_id in headers for PacketEnvelope
traceability.  Both are fire-and-forget with error logging (no blocking).

Configuration:
  - GRAPH_SERVICE_URL (optional) — if unset, graph sync is skipped
  - SCORE_SERVICE_URL (optional) — if unset, score invalidation is skipped

Architecture compliance:
  - Async HTTP calls only
  - No retries (let downstream services handle idempotency)
  - Lineage forwarding mandatory
  - Timeout: 10s per call
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def trigger_graph_sync(
    entity_id: str,
    tenant_id: str,
    enriched_fields: dict[str, Any],
    confidence: float,
    lineage_id: str,
    packet_id: str,
) -> None:
    """
    Notify GRAPH node of new enrichment data for entity.

    POST to {GRAPH_SERVICE_URL}/v1/sync with:
      - entity_id, tenant_id, enriched_fields, confidence in body
      - lineage_id, packet_id in headers

    Fire-and-forget.  If GRAPH_SERVICE_URL is not configured, no-op.
    """
    settings = get_settings()
    if not settings.graph_service_url:
        logger.debug("graph_sync_skipped_no_url", extra={"entity_id": entity_id})
        return

    base = settings.graph_service_url.rstrip("/")
    url = f"{base}/v1/sync"
    headers = {
        "X-L9-Lineage": lineage_id,
        "X-L9-Packet": packet_id,
        "Content-Type": "application/json",
    }
    payload = {
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "enriched_fields": enriched_fields,
        "confidence": confidence,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        logger.info(
            "graph_sync_triggered",
            extra={"entity_id": entity_id, "url": url, "status": response.status_code},
        )
    except Exception as e:
        logger.error(
            "graph_sync_failed",
            extra={"entity_id": entity_id, "url": url, "error": str(e)},
            exc_info=True,
        )


async def invalidate_score_cache(
    entity_id: str,
    tenant_id: str,
    lineage_id: str,
    packet_id: str,
) -> None:
    """
    Notify SCORE node to invalidate cached scores for entity.

    POST to {SCORE_SERVICE_URL}/v1/invalidate with:
      - entity_id, tenant_id in body
      - lineage_id, packet_id in headers

    Fire-and-forget.  If SCORE_SERVICE_URL is not configured, no-op.
    """
    settings = get_settings()
    if not settings.score_service_url:
        logger.debug("score_invalidation_skipped_no_url", extra={"entity_id": entity_id})
        return

    base = settings.score_service_url.rstrip("/")
    url = f"{base}/v1/invalidate"
    headers = {
        "X-L9-Lineage": lineage_id,
        "X-L9-Packet": packet_id,
        "Content-Type": "application/json",
    }
    payload = {
        "entity_id": entity_id,
        "tenant_id": tenant_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        logger.info(
            "score_cache_invalidated",
            extra={"entity_id": entity_id, "url": url, "status": response.status_code},
        )
    except Exception as e:
        logger.error(
            "score_invalidation_failed",
            extra={"entity_id": entity_id, "url": url, "error": str(e)},
            exc_info=True,
        )
