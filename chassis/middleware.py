"""
chassis/middleware.py
FastAPI middleware that traces transport requests at the chassis boundary.
Emits: packet_id, action, tenant, latency_ms, status to structlog.
Consumed by Prometheus/Grafana via the observability stack.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("chassis.middleware")


class PacketTracingMiddleware(BaseHTTPMiddleware):
    """
    Trace all requests through /v1/execute.
    Adds X-Packet-Id and X-Trace-Latency-Ms to every response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()

        if request.url.path == "/v1/execute":
            body = await request.body()
            try:
                raw = json.loads(body)
                action = raw.get("action", "unknown")
                tenant = raw.get("tenant", "unknown")
                packet_id = raw.get("packet_id", "")
            except Exception:
                action = tenant = packet_id = "parse_error"

            request = Request(
                scope=request.scope,
                receive=_body_to_receive(body),
            )
        else:
            action = tenant = packet_id = "-"

        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if action != "-":
            logger.info(
                "chassis.packet_traced",
                action=action,
                tenant=tenant,
                packet_id=packet_id,
                status=response.status_code,
                latency_ms=elapsed_ms,
            )
            response.headers["X-Packet-Id"] = packet_id
            response.headers["X-Trace-Latency-Ms"] = str(elapsed_ms)

        return response


def _body_to_receive(body: bytes):
    """Re-inject consumed request body into ASGI receive channel."""

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return receive
