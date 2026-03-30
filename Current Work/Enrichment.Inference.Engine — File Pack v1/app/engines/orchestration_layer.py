"""
app/engines/orchestration_layer.py
Orchestration Layer — wires the full L9 enrichment constellation.

This is the file that was missing: it connects
    chassis handlers → enrichment → inference → graph sync → downstream packets

It is called once at startup by app/main.py to register all handlers with
the l9 chassis and bind the graph sync client.

Architecture position:
    chassis router → orchestration_layer.register() → handlers.py → enrichment_orchestrator
                                                                    ↓
                                                         inference_bridge_v2
                                                                    ↓
                                                         graph_sync_client (PacketEnvelope)
                                                                    ↓
                                                         packet_router → SCORE / ROUTE
"""

from __future__ import annotations

from typing import Any

import structlog
from l9.chassis import register_handler

from app.core.config import settings
from app.engines.graph_sync_client import GraphSyncClient
from app.engines.handlers import (
    handle_converge,
    handle_discover,
    handle_enrich,
    handle_enrichbatch,
    init_handlers,
)
from app.engines.packet_router import dispatch_to_score
from app.services.event_emitter import EnrichmentEvent, emit

logger = structlog.get_logger(__name__)

# Module-level singletons initialised at startup
_graph_client: GraphSyncClient | None = None


def register(kb, idem_store=None, domain_reader=None) -> None:
    """
    Register all ENRICH handlers with the L9 chassis.
    Called once from app/main.py lifespan startup.

    This is the single line that connects the chassis to the engine:
        register_handler("enrich",       handle_enrich)
        register_handler("enrichbatch",  handle_enrichbatch)
        register_handler("converge",     handle_converge)
        register_handler("discover",     handle_discover)
    """
    global _graph_client

    # Inject dependencies into handlers
    init_handlers(kb=kb, idem=idem_store, domain_reader=domain_reader)

    # Register with chassis
    register_handler("enrich", handle_enrich)
    register_handler("enrichbatch", handle_enrichbatch)
    register_handler("converge", handle_converge)
    register_handler("discover", handle_discover)

    # Wrap enrichbatch to add post-enrichment graph sync + downstream dispatch
    register_handler("enrich_and_sync", _make_enrich_and_sync_handler(kb, idem_store))

    # Build graph sync client
    _graph_client = GraphSyncClient(
        graph_url=settings.graph_node_url,
        api_key=settings.inter_node_secret,
        source_node="enrichment-engine",
    )

    logger.info(
        "orchestration.registered",
        handlers=["enrich", "enrichbatch", "converge", "discover", "enrich_and_sync"],
        graph_url=settings.graph_node_url,
    )


def _make_enrich_and_sync_handler(kb, idem_store):
    """
    Composite handler: enrich → sync to graph → dispatch downstream.
    Action: "enrich_and_sync"

    This closes the ENRICH→GRAPH loop that was previously missing.
    """

    async def handle_enrich_and_sync(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
        # 1. Run enrichment
        enrich_result = await handle_enrich(tenant, payload)

        entity_id = payload.get("entity_id", "unknown")
        entity_type = payload.get("entity_type", "Contact")
        domain = payload.get("domain", settings.default_domain)

        if enrich_result.get("state") != "completed":
            return enrich_result

        # 2. Sync to GRAPH via PacketEnvelope
        if _graph_client:
            try:
                sync_resp = await _graph_client.sync_entities(
                    entity_type=entity_type,
                    batch=[
                        {
                            "entity_id": entity_id,
                            "domain": domain,
                            "fields": enrich_result.get("fields", {}),
                            "confidence": enrich_result.get("confidence", 0.0),
                        }
                    ],
                    tenant=tenant,
                    parent_packet_id=enrich_result.get("packet_id"),
                )
                logger.info(
                    "orchestration.graph_sync", entity_id=entity_id, status=sync_resp.get("status")
                )
                enrich_result["graph_sync_status"] = sync_resp.get("status", "unknown")
            except Exception as exc:
                logger.warning(
                    "orchestration.graph_sync_failed", entity_id=entity_id, error=str(exc)
                )
                enrich_result["graph_sync_status"] = "failed"

        # 3. Dispatch to SCORE node
        try:
            score_envelope = {
                "action": "score",
                "tenant": tenant,
                "payload": {
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "domain": domain,
                    "fields": enrich_result.get("fields", {}),
                    "confidence": enrich_result.get("confidence", 0.0),
                },
            }
            await dispatch_to_score(score_envelope)
        except Exception as exc:
            logger.warning(
                "orchestration.score_dispatch_failed", entity_id=entity_id, error=str(exc)
            )

        # 4. Emit domain event (consumed by SIGNAL, HEALTH, etc.)
        await emit(
            EnrichmentEvent.ENRICHMENT_COMPLETED,
            data={
                "entity_id": entity_id,
                "domain": domain,
                "fields": list(enrich_result.get("fields", {}).keys()),
                "confidence": enrich_result.get("confidence", 0.0),
            },
            tenant_id=tenant,
        )

        return enrich_result

    handle_enrich_and_sync.__name__ = "handle_enrich_and_sync"
    return handle_enrich_and_sync


async def run_outcome_feedback(
    outcome: dict[str, Any],
    tenant: str,
    parent_packet_id: str | None = None,
) -> dict[str, Any]:
    """
    Integration mode 4: send match outcome back to graph for reinforcement.
    Called by downstream services (e.g., ROUTE confirms a match was accepted).
    """
    if not _graph_client:
        logger.warning("orchestration.outcome_no_graph_client")
        return {"status": "skipped", "reason": "no_graph_client"}

    resp = await _graph_client.send_outcome(
        outcome=outcome,
        tenant=tenant,
        parent_packet_id=parent_packet_id,
    )
    logger.info(
        "orchestration.outcome_sent", entity_id=outcome.get("entity_id"), status=resp.get("status")
    )
    return resp
