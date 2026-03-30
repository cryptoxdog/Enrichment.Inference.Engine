"""
l9/chassis/router.py
Packet router — the ONLY entry point for inbound PacketEnvelopes.

Flow:
    raw HTTP body
        → inflate_ingress (chassis_contract)
        → resolve handler from registry
        → handler(tenant, payload) -> response dict
        → deflate_egress (chassis_contract)
        → wire-format dict

The router never touches domain logic.
It only: validates, dispatches, wraps.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.engines.chassis_contract import deflate_egress, inflate_ingress

from .registry import resolve

logger = structlog.get_logger(__name__)


async def route_packet(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Route a raw inbound dict through the chassis pipeline.

    Raises:
        ValueError: if envelope validation fails (action missing, hash tampered)
        KeyError:   if no handler is registered for the action
        Exception:  any unhandled error from the handler (caller handles retry)
    """
    # 1. Inflate to canonical envelope
    envelope = inflate_ingress(raw)
    action = envelope["action"]
    tenant = envelope["tenant"]["actor"]
    payload = envelope["payload"]

    logger.info(
        "chassis.route",
        action=action,
        tenant=tenant,
        packet_id=envelope["packet_id"],
    )

    # 2. Resolve handler
    handler = resolve(action)

    # 3. Dispatch
    try:
        response_data = await handler(tenant, payload)
    except Exception as exc:
        logger.error(
            "chassis.handler_error",
            action=action,
            tenant=tenant,
            error=str(exc),
            exc_info=True,
        )
        raise

    # 4. Deflate to wire format
    return deflate_egress(envelope, response_data)
