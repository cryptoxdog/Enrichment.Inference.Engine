"""
app/engines/packet_router.py

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
    Build a PacketEnvelope for inter-node dispatch.

    Includes:
    - Unique packet_id (UUID)
    - tenant_id propagation
    - correlation_id for request tracing
    - content_hash (SHA-256 of canonical JSON payload)
    - created_at timestamp (UTC ISO-8601)
    """
    packet_id = str(uuid.uuid4())
    corr_id = correlation_id or str(uuid.uuid4())
    canonical = json.dumps(payload, sort_keys=True, default=str)
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()

    return {
        "header": {
            "packet_id": packet_id,
            "action": action,
            "tenant_id": tenant_id,
            "correlation_id": corr_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
        },
        "payload": payload,
        "content_hash": content_hash,
    }


class PacketRouter:
    """
    Dispatches PacketEnvelopes to L9 constellation nodes.

    Node URLs are resolved from settings at construction time.
    All calls use httpx.AsyncClient with configurable timeout and retry.
    """

    def __init__(self, node_urls: dict[str, str], timeout: float = _ROUTE_TIMEOUT) -> None:
        self._node_urls = node_urls
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    def _url_for(self, target: NodeTarget) -> str | None:
        return self._node_urls.get(target.value)

    async def route(
        self,
        target: NodeTarget,
        action: str,
        tenant_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Dispatch a PacketEnvelope to a constellation node.

        Raises NodeUnreachableError if all retry attempts fail.
        Raises httpx.HTTPStatusError for non-retryable 4xx responses.
        """
        url = self._url_for(target)
        if not url:
            raise NodeUnreachableError(f"No URL configured for node: {target.value}")

        envelope = _build_envelope(action, tenant_id, payload, correlation_id)

        last_exc: Exception | None = None
        for attempt in range(_RETRY_ATTEMPTS + 1):
            try:
                resp = await self._http.post(f"{url}/v1/execute", json=envelope)

                if resp.status_code in _RETRYABLE_STATUS and attempt < _RETRY_ATTEMPTS:
                    last_exc = httpx.HTTPStatusError(
                        f"Retryable {resp.status_code}", request=resp.request, response=resp
                    )
                    await asyncio.sleep(2 ** attempt)
                    continue

                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    "packet_routed",
                    target=target.value,
                    action=action,
                    packet_id=envelope["header"]["packet_id"],
                    status=resp.status_code,
                )
                return data

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    "packet_route_error",
                    target=target.value,
                    action=action,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < _RETRY_ATTEMPTS:
                    await asyncio.sleep(2 ** attempt)

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
        Dispatch without awaiting. Errors are logged, never raised.
        Use for non-critical downstream notifications.
        """
        async def _safe_route() -> None:
            try:
                await self.route(target, action, tenant_id, payload, correlation_id)
            except Exception as exc:
                logger.warning(
                    "fire_and_forget_failed",
                    target=target.value,
                    action=action,
                    error=str(exc),
                )

        asyncio.create_task(_safe_route())

    async def notify_graph_sync(
        self,
        tenant_id: str,
        entity_id: str,
        fields: dict[str, Any],
        domain: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Notify the graph node to sync enriched entity fields.

        Returns the graph response or None if graph node not configured.
        """
        if not self._url_for(NodeTarget.GRAPH):
            logger.debug("graph_node_not_configured", entity_id=entity_id)
            return None

        try:
            return await self.route(
                NodeTarget.GRAPH,
                "graph_sync",
                tenant_id,
                {"entity_id": entity_id, "fields": fields, "domain": domain or ""},
                correlation_id,
            )
        except NodeUnreachableError as exc:
            logger.warning("graph_sync_failed", entity_id=entity_id, error=str(exc))
            return None

    async def notify_score_invalidate(
        self,
        tenant_id: str,
        entity_id: str,
        domain: str | None = None,
    ) -> None:
        """Fire-and-forget score invalidation after entity enrichment."""
        self.route_fire_and_forget(
            NodeTarget.SCORE,
            "score_invalidate",
            tenant_id,
            {"entity_id": entity_id, "domain": domain or ""},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()


@lru_cache(maxsize=1)
def get_router(settings: Any) -> PacketRouter:
    """Module-level singleton router. Cached per process."""
    node_urls = {}
    for target in NodeTarget:
        url_attr = f"{target.value}_node_url"
        if hasattr(settings, url_attr):
            url = getattr(settings, url_attr)
            if url:
                node_urls[target.value] = url
    return PacketRouter(node_urls=node_urls)
