"""
chassis/router.py
Packet router — the ONLY entry point for inbound PacketEnvelopes.

Flow:
    raw HTTP body
        → inflate_ingress  (chassis.envelope — self-contained, no app/ imports)
        → resolve handler from registry
        → handler(tenant, payload) -> response dict
        → deflate_egress   (chassis.envelope)
        → wire-format dict

The router never touches domain logic.
It only: validates, dispatches, wraps.
"""

from __future__ import annotations

from typing import Any

import structlog

from .envelope import deflate_egress, inflate_ingress
from .registry import resolve

logger = structlog.get_logger(__name__)


async def route_packet(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Route a raw inbound dict through the chassis pipeline.

    Raises:
        ValueError: envelope validation fails (action missing, hash tampered)
        KeyError:   no handler registered for the action
        Exception:  unhandled error from the handler (caller handles retry)
    """
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

    handler = resolve(action)

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

    return deflate_egress(envelope, response_data)
