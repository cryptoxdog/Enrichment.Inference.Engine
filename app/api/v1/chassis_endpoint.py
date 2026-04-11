"""
app/api/v1/chassis_endpoint.py
Supplemental Gate runtime routes for ENRICH.

`/v1/execute` is now owned by the SDK-created node runtime. This module keeps
app-specific routes that are adjacent to transport, but not part of the SDK.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import verify_api_key

router = APIRouter(tags=["chassis"])


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
    return await run_outcome_feedback(
        outcome=outcome,
        tenant=tenant,
    )
