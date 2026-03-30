"""
app/api/v1/chassis_endpoint.py
Universal chassis ingress — POST /v1/execute

All constellation nodes that call the ENRICH service use this endpoint.
The route_packet() function in the chassis router handles dispatch.

External HTTP clients (Salesforce, Odoo) continue to use /api/v1/enrich
and /api/v1/enrich/batch — those routes are in main.py and call the
enrichment orchestrator directly.

This endpoint is for node-to-node PacketEnvelope traffic.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from l9.chassis.router import route_packet

from app.core.auth import verify_api_key

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["chassis"])


@router.post(
    "/v1/execute",
    summary="L9 Chassis — universal packet ingress",
    description=(
        "Accepts any PacketEnvelope and routes it to the registered handler. "
        "action field determines which handler fires. "
        "Supported: enrich, enrichbatch, converge, discover, enrich_and_sync."
    ),
)
async def execute_packet(
    body: dict[str, Any],
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return await route_packet(body)
    except ValueError as exc:
        # Envelope validation failure (missing action, hash mismatch)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        # Unknown action
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("chassis_endpoint.error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal enrichment error") from exc


@router.post(
    "/v1/outcomes",
    summary="Receive match outcome for reinforcement feedback",
    description=(
        "Called by ROUTE/SCORE to record whether an enrichment-driven match "
        "was accepted or rejected. Feeds the outcome back to GRAPH for "
        "temporal decay adjustment and community re-scoring."
    ),
)
async def receive_outcome(
    body: dict[str, Any],
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    from app.engines.orchestration_layer import run_outcome_feedback

    tenant = body.get("tenant", "default")
    outcome = body.get("payload", body)
    result = await run_outcome_feedback(
        outcome=outcome,
        tenant=tenant,
        parent_packet_id=body.get("parent_packet_id"),
    )
    return result
