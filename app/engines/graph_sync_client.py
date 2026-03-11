"""
Graph Sync Client — PacketEnvelope → Graph sync/match/outcome.

Emits PacketEnvelopes to the Graph Intelligence Service via HTTP.
Handles all 4 integration modes:
  1. Pre-Sync: enrich → sync enriched entities to graph
  2. Pre-Match: enrich → resolve → match with enriched params
  3. Nightly Batch: batch enrich → batch sync
  4. Outcome Feedback: match outcome → enrich for failure analysis

Speaks the L9 chassis contract:
  POST /v1/execute with action="sync"|"match"|"resolve"|"outcome"

PacketEnvelope carries:
  - address: sourcenode="enrichment-engine", destinationnode="graph-service"
  - tenant context: actor, onbehalfof, originator, orgid
  - lineage: parentids from the enrichment response packet
  - governance: intent, compliance_tags
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("graph_sync_client")


class GraphSyncClient:
    """
    HTTP client for the Graph Intelligence Service.
    Wraps all requests in L9 chassis-compatible envelopes.
    """

    def __init__(
        self,
        graph_url: str,
        api_key: str,
        source_node: str = "enrichment-engine",
        timeout: int = 30,
    ):
        self._url = graph_url.rstrip("/")
        self._api_key = api_key
        self._source = source_node
        self._timeout = timeout

    async def sync_entities(
        self,
        entity_type: str,
        batch: list[dict[str, Any]],
        tenant: str,
        parent_packet_id: str | None = None,
    ) -> dict[str, Any]:
        """Sync enriched entities to the graph (integration mode 1 & 3)."""
        envelope = self._build_envelope(
            action="sync",
            payload={
                "entity_type": entity_type,
                "batch": batch,
            },
            tenant=tenant,
            parent_id=parent_packet_id,
            intent=f"sync_{entity_type}",
        )
        return await self._send(envelope)

    async def match(
        self,
        query: dict[str, Any],
        match_direction: str,
        tenant: str,
        parent_packet_id: str | None = None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Run a match query against the graph (integration mode 2)."""
        envelope = self._build_envelope(
            action="match",
            payload={
                "query": query,
                "match_direction": match_direction,
                "top_n": top_n,
            },
            tenant=tenant,
            parent_id=parent_packet_id,
            intent=f"match_{match_direction}",
        )
        return await self._send(envelope)

    async def send_outcome(
        self,
        outcome: dict[str, Any],
        tenant: str,
        parent_packet_id: str | None = None,
    ) -> dict[str, Any]:
        """Send match outcome for feedback loop (integration mode 4)."""
        envelope = self._build_envelope(
            action="outcome",
            payload=outcome,
            tenant=tenant,
            parent_id=parent_packet_id,
            intent="outcome_feedback",
        )
        return await self._send(envelope)

    def _build_envelope(
        self,
        action: str,
        payload: dict[str, Any],
        tenant: str,
        parent_id: str | None = None,
        intent: str = "",
    ) -> dict[str, Any]:
        packet_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        hash_input = json.dumps(
            {
                "action": action,
                "payload": payload,
                "tenant": tenant,
            },
            sort_keys=True,
        )
        content_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        envelope: dict[str, Any] = {
            "action": action,
            "tenant": tenant,
            "version": "v1",
            "payload": {
                **payload,
                "_packet_metadata": {
                    "packet_id": packet_id,
                    "source_node": self._source,
                    "destination_node": "graph-service",
                    "timestamp": timestamp,
                    "content_hash": content_hash,
                },
            },
        }

        if parent_id:
            envelope["payload"]["_packet_metadata"]["parent_id"] = parent_id
            envelope["payload"]["_packet_metadata"]["lineage"] = {
                "parent_ids": [parent_id],
                "derivation_type": "enrichment",
            }

        if intent:
            envelope["payload"]["_packet_metadata"]["intent"] = intent

        return envelope

    async def _send(self, envelope: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._url}/v1/execute"
        headers = {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
            "X-Source-Node": self._source,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=envelope, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "graph_sync_failed",
                status=e.response.status_code,
                action=envelope.get("action"),
            )
            return {"status": "failed", "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error("graph_sync_error", error=type(e).__name__)
            return {"status": "failed", "error": "connection_failed"}
