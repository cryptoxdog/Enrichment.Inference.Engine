"""
chassis/node_client.py
Generic constellation node HTTP client.
Any node can call any other node using this client + the PacketEnvelope protocol.

Usage:
    from chassis.node_client import NodeClient
    client = NodeClient(url=settings.graph_node_url, secret=settings.inter_node_secret)
    result = await client.execute(action="score", payload={...}, tenant="acme")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.5


class NodeClient:
    """
    Typed wrapper for POST /v1/execute on any constellation node.
    Handles PacketEnvelope construction, signing, retry, and hop_trace.
    """

    def __init__(
        self,
        url: str,
        secret: str,
        source_node: str = "enrichment-engine",
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = MAX_RETRIES,
    ) -> None:
        self._url = url.rstrip("/") + "/v1/execute"
        self._secret = secret
        self._source = source_node
        self._timeout = timeout
        self._retries = retries

    async def execute(
        self,
        action: str,
        payload: dict[str, Any],
        tenant: str,
        parent_packet_id: str | None = None,
        intent: str = "",
    ) -> dict[str, Any]:
        """Send a PacketEnvelope and return the response envelope."""
        envelope = self._build(action, payload, tenant, parent_packet_id, intent)
        return await self._send(envelope)

    def _build(
        self,
        action: str,
        payload: dict,
        tenant: str,
        parent_id: str | None,
        intent: str,
    ) -> dict[str, Any]:
        packet_id = str(uuid.uuid4())
        ts = time.time()
        content_hash = hashlib.sha256(
            json.dumps(
                {"action": action, "payload": payload, "tenant": tenant},
                sort_keys=True,
            ).encode()
        ).hexdigest()

        env: dict[str, Any] = {
            "action": action,
            "packet_id": packet_id,
            "tenant": tenant,
            "version": "v1",
            "timestamp": ts,
            "content_hash": content_hash,
            "payload": payload,
            "address": {
                "source_node": self._source,
                "destination_node": "unknown",
                "reply_to": self._source,
            },
            "governance": {
                "intent": intent or action,
                "audit_required": False,
                "compliance_tags": [],
            },
            "hop_trace": [
                {
                    "node": self._source,
                    "action": "send",
                    "status": "sent",
                    "timestamp": ts,
                }
            ],
        }
        if parent_id:
            env["lineage"] = {
                "parent_ids": [parent_id],
                "derivation_type": "enrichment",
            }
        return env

    async def _send(self, envelope: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        self._url,
                        json=envelope,
                        headers={
                            "Authorization": f"Bearer {self._secret}",
                            "X-Source-Node": self._source,
                            "X-Trace-Id": envelope["packet_id"],
                        },
                    )
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise
                last_exc = exc
            except (TimeoutError, httpx.TransportError) as exc:
                last_exc = exc
            wait = BACKOFF_BASE**attempt
            logger.warning("node_client.retry", attempt=attempt + 1, wait=wait)
            await asyncio.sleep(wait)
        msg = f"NodeClient: {self._retries} retries exhausted"
        raise RuntimeError(msg) from last_exc
