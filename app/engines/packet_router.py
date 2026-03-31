# app/engines/packet_router.py
"""
PacketEnvelope router for inter-node constellation communication.

Builds and dispatches PacketEnvelopes to L9 constellation nodes
via POST /v1/execute. All inter-node traffic carries tenant lineage,
correlation_id, and content-hash integrity markers.

Usage:
    router = get_router(settings)
    await router.notify_graph_sync(tenant_id, entity_id, fields, domain)
    router.route_fire_and_forget(NodeTarget.SCORE, "score_invalidate", ...)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("packet_router")

_ROUTE_TIMEOUT = 30.0
_RETRY_ATTEMPTS = 2
_RETRYABLE_STATUS = frozenset({500, 502, 503, 504})


class NodeTarget(str, Enum):
    GRAPH = "graph"
    SCORE = "score"
    ROUTE = "route"
    SIGNAL = "signal"
    FORECAST = "forecast"
    HANDOFF = "handoff"


class NodeUnreachableError(Exception):
    """Raised when all retry attempts to a constellation node are exhausted."""


def _build_envelope(
    action: str,
    tenant_id: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a PacketEnvelope with lineage, hash integrity, and delegation trace.

    Fields:
        packet_id        — unique envelope UUID
        action           — target handler action string
        tenant_id        — originating tenant (lineage)
        correlation_id   — caller-supplied trace ID (or generated)
        payload          — action-specific data dict
        content_hash     — SHA-256 of serialized payload (integrity)
        sent_at          — ISO timestamp
    """
    cid = correlation_id or str(uuid.uuid4())
    payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()

    return {
        "packet_id": str(uuid.uuid4()),
        "action": action,
        "tenant_id": tenant_id,
        "correlation_id": cid,
        "payload": payload,
        "content_hash": content_hash,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


class PacketRouter:
    """
    Routes PacketEnvelopes to constellation node endpoints.

    Node URLs resolved from settings.node_urls dict keyed by NodeTarget value.
    Shared httpx.AsyncClient with connection pooling.
    """

    def __init__(self, settings: Any) -> None:
        self._node_urls: dict[str, str] = getattr(settings, "node_urls", {})
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(_ROUTE_TIMEOUT))

    def _url_for(self, target: NodeTarget) -> str:
        url = self._node_urls.get(target.value)
        if not url:
            raise NodeUnreachableError(
                f"No URL configured for node target: {target.value}"
            )
        return url.rstrip("/") + "/v1/execute"

    async def route(
        self,
        target: NodeTarget,
        action: str,
        tenant_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Dispatch a packet to a target node and return the response body.

        Retries up to _RETRY_ATTEMPTS times on retryable HTTP errors.
        Raises NodeUnreachableError if all attempts fail.
        """
        envelope = _build_envelope(action, tenant_id, payload, correlation_id)
        url = self._url_for(target)
        last_exc: Exception | None = None

        for attempt in range(1, _RETRY_ATTEMPTS + 2):
            try:
                resp = await self._http.post(url, json=envelope)
                if resp.status_code in _RETRYABLE_STATUS:
                    last_exc = NodeUnreachableError(
                        f"{target.value} returned {resp.status_code} on attempt {attempt}"
                    )
                    await asyncio.sleep(attempt * 0.5)
                    continue
                resp.raise_for_status()
                logger.debug(
                    "packet_routed",
                    target=target.value,
                    action=action,
                    packet_id=envelope["packet_id"],
                    status=resp.status_code,
                )
                return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    "packet_route_network_error",
                    target=target.value,
                    attempt=attempt,
                    error=str(exc),
                )
                await asyncio.sleep(attempt * 0.5)

        raise NodeUnreachableError(
            f"Node {target.value} unreachable after {_RETRY_ATTEMPTS + 1} attempts"
        ) from last_exc

    def route_fire_and_forget(
        self,
        target: NodeTarget,
        action: str,
        tenant_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        """
        Fire-and-forget packet dispatch via asyncio.create_task.

        Never awaited. Errors are logged internally by _route_safe.
        Use for notifications that must not block the enrichment path.
        """
        asyncio.create_task(
            self._route_safe(target, action, tenant_id, payload, correlation_id)
        )

    async def _route_safe(
        self,
        target: NodeTarget,
        action: str,
        tenant_id: str,
        payload: dict[str, Any],
        correlation_id: str | None,
    ) -> None:
        try:
            await self.route(target, action, tenant_id, payload, correlation_id)
        except NodeUnreachableError as exc:
            logger.error(
                "packet_router_fire_forget_failed",
                target=target.value,
                action=action,
                error=str(exc),
            )

    async def notify_graph_sync(
        self,
        tenant_id: str,
        entity_id: str,
        fields: dict[str, Any],
        domain: str,
    ) -> None:
        """Notify the GRAPH node to upsert an enriched entity."""
        await self.route(
            target=NodeTarget.GRAPH,
            action="entity_upsert",
            tenant_id=tenant_id,
            payload={
                "entity_id": entity_id,
                "fields": fields,
                "domain": domain,
            },
        )

    async def notify_score_invalidated(
        self, tenant_id: str, entity_id: str
    ) -> None:
        """Notify the SCORE node to invalidate cached scores for an entity."""
        await self.route(
            target=NodeTarget.SCORE,
            action="score_invalidate",
            tenant_id=tenant_id,
            payload={"entity_id": entity_id},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()


@lru_cache(maxsize=1)
def get_router(settings: Any) -> PacketRouter:
    """Module-level singleton PacketRouter. Cached per process."""
    return PacketRouter(settings)
