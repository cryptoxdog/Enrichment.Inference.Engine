"""
app/engines/orchestration_layer.py
Orchestration Layer — wires the full L9 enrichment constellation.

Integration fixes applied (PR#21 merge pass):
    GAP-1: dispatch_to_score replaced with get_router().notify_score_invalidate()
    GAP-2: emit() corrected to get_emitter().emit_enrichment_completed()
    GAP-5: ResultStore.persist_enrich_response wired into enrich_and_sync
    GAP-6: packet_router.notify_graph_sync wired into enrich_and_sync
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import get_settings
from app.engines.graph_sync_client import GraphSyncClient
from app.engines.handlers import (
    handle_converge,
    handle_discover,
    handle_enrich,
    handle_enrichbatch,
    handle_simulate,
    handle_writeback,
    init_handlers,
)
from chassis import register_handler

logger = structlog.get_logger(__name__)

_graph_client: GraphSyncClient | None = None


def register(kb, idem_store=None, domain_reader=None) -> None:
    global _graph_client
    settings = get_settings()

    init_handlers(kb=kb, idem=idem_store, domain_reader=domain_reader)

    register_handler("enrich", handle_enrich)
    register_handler("enrichbatch", handle_enrichbatch)
    register_handler("converge", handle_converge)
    register_handler("discover", handle_discover)
    register_handler("simulate", handle_simulate)
    register_handler("writeback", handle_writeback)
    register_handler("enrich_and_sync", _make_enrich_and_sync_handler(kb, idem_store))

    _graph_client = GraphSyncClient(
        graph_url=settings.graph_node_url,
        api_key=settings.inter_node_secret,
        source_node="enrichment-engine",
    )

    logger.info(
        "orchestration.registered",
        handlers=[
            "enrich",
            "enrichbatch",
            "converge",
            "discover",
            "simulate",
            "writeback",
            "enrich_and_sync",
        ],
        graph_url=settings.graph_node_url,
    )


def _make_enrich_and_sync_handler(kb, idem_store):
    """Composite: enrich -> persist -> graph sync -> score invalidate -> event emit."""

    async def handle_enrich_and_sync(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        enrich_result = await handle_enrich(tenant, payload)

        entity_id = payload.get("entity_id", "unknown")
        entity_type = payload.get("entity_type", "Contact")
        domain = payload.get("domain", settings.default_domain)

        if enrich_result.get("state") != "completed":
            return enrich_result

        # GAP-5: Persist result via ResultStore
        try:
            from app.models.schemas import EnrichResponse
            from app.services.result_store import ResultStore

            store = ResultStore(tenant_id=tenant)
            resp_obj = EnrichResponse.model_validate(enrich_result)
            await store.persist_enrich_response(
                response=resp_obj,
                entity_id=entity_id,
                object_type=entity_type,
                domain=domain,
                idempotency_key=payload.get("idempotency_key"),
            )
        except Exception as exc:
            logger.warning(
                "orchestration.result_persist_failed", entity_id=entity_id, error=str(exc)
            )

        # Graph sync via GraphSyncClient
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
                enrich_result["graph_sync_status"] = sync_resp.get("status", "unknown")
            except Exception as exc:
                logger.warning(
                    "orchestration.graph_sync_failed", entity_id=entity_id, error=str(exc)
                )
                enrich_result["graph_sync_status"] = "failed"

        # GAP-6: Packet-routed graph sync
        try:
            from app.engines.packet_router import get_router

            router = get_router(settings)
            await router.notify_graph_sync(
                tenant_id=tenant,
                entity_id=entity_id,
                fields=enrich_result.get("fields", {}),
                domain=domain,
            )
        except Exception as exc:
            logger.warning(
                "orchestration.packet_graph_sync_failed", entity_id=entity_id, error=str(exc)
            )

        # GAP-1: Score invalidation via PacketRouter (replaces non-existent dispatch_to_score)
        try:
            from app.engines.packet_router import get_router

            router = get_router(settings)
            await router.notify_score_invalidate(
                tenant_id=tenant,
                entity_id=entity_id,
                domain=domain,
            )
        except Exception as exc:
            logger.warning(
                "orchestration.score_invalidate_failed", entity_id=entity_id, error=str(exc)
            )

        # GAP-2: Event emission via get_emitter() (replaces non-existent module-level emit())
        try:
            from app.services.event_emitter import get_emitter

            await get_emitter(settings).emit_enrichment_completed(
                tenant_id=tenant,
                entity_id=entity_id,
                domain=domain,
                fields=enrich_result.get("fields", {}),
                confidence=float(enrich_result.get("confidence", 0.0)),
                tokens_used=int(enrich_result.get("tokens_used", 0)),
            )
        except Exception as exc:
            logger.warning("orchestration.event_emit_failed", entity_id=entity_id, error=str(exc))

        return enrich_result

    handle_enrich_and_sync.__name__ = "handle_enrich_and_sync"
    return handle_enrich_and_sync


async def run_outcome_feedback(
    outcome: dict[str, Any],
    tenant: str,
    parent_packet_id: str | None = None,
) -> dict[str, Any]:
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
