# app/engines/packet_router.py
"""
PacketEnvelope router for inter-node constellation communication.

Builds and dispatches PacketEnvelopes to L9 constellation nodes
via POST /v1/execute. All inter-node traffic carries tenant lineage,
correlation_id, and content-hash integrity markers.

The content_hash covers (action, tenant_id, payload) to detect mutation
in transit. Recipients must re-derive and compare before processing.

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

    The content_hash covers (action, tenant_id, payload) to detect mutation
    in transit. Recipients must re-derive and compare before processing.
    """
    cid = correlation_id or str(uuid.uuid4())
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    content_hash = hashlib.sha256(
        f"{action}:{tenant_id}:{payload_json}".encode()
    ).hexdigest()

    return {
        "action": action,
        "tenant_id": tenant_id,
        "payload": payload,
        "correlation_id": cid,
        "content_hash": content_hash,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "source_node": "enrich",
    }


class PacketRouter:
    """
    Sends PacketEnvelopes to L9 constellation nodes.

    Builds URL map from Settings at construction time.
    Singleton per process via get_router().
    """

    def __init__(self, settings: Any) -> None:
        self._url_map: dict[NodeTarget, str] = {
            NodeTarget.GRAPH: settings.graph_node_url,
            NodeTarget.SCORE: settings.score_node_url,
            NodeTarget.ROUTE: settings.route_node_url,
            NodeTarget.SIGNAL: getattr(settings, "signal_node_url", ""),
            NodeTarget.FORECAST: getattr(settings, "forecast_node_url", ""),
            NodeTarget.HANDOFF: getattr(settings, "handoff_node_url", ""),
        }
        self._secret = settings.inter_node_secret
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(_ROUTE_TIMEOUT),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.inter_node_secret}",
            },
        )

    async def route(
        self,
        target: NodeTarget,
        action: str,
        tenant_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Route a PacketEnvelope to a constellation node.

        Retries up to _RETRY_ATTEMPTS times on 5xx responses.
        Raises NodeUnreachableError when all attempts fail.
        """
        base_url = self._url_map.get(target, "")
        if not base_url:
            raise NodeUnreachableError(
                f"No URL configured for node target: {target.value}"
            )

        envelope = _build_envelope(
            action=action,
            tenant_id=tenant_id,
            payload=payload,
            correlation_id=correlation_id,
        )
        url = f"{base_url.rstrip('/')}/v1/execute"

        last_exc: Exception | None = None
        for attempt in range(1, _RETRY_ATTEMPTS + 2):
            try:
                resp = await self._http.post(url, json=envelope)
                if resp.status_code in _RETRYABLE_STATUS and attempt <= _RETRY_ATTEMPTS:
                    logger.warning(
                        "packet_router_retrying",
                        target=target.value,
                        action=action,
                        status=resp.status_code,
                        attempt=attempt,
                    )
                    continue
                resp.raise_for_status()
                logger.info(
                    "packet_routed",
                    target=target.value,
                    action=action,
                    tenant_id=tenant_id,
                    correlation_id=envelope["correlation_id"],
                )
                return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    "packet_router_network_error",
                    target=target.value,
                    action=action,
                    attempt=attempt,
                    error=str(exc),
                )

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
