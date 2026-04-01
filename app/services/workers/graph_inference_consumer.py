"""
graph_inference_consumer.py
Redis Streams consumer — closes the bidirectional ENRICH↔GRAPH loop.

Subscribes to graph.inference.complete stream published by the GRAPH service
after each materialization batch. Qualifying inferred triples are fed back
into the convergence loop as external re-enrichment signals.

Stream: graph.inference.complete
Consumer group: enrich-convergence-group
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.engines.convergence.convergence_signals import (
    ConvergenceExitReason,
    GraphInferenceEvent,
    InferredTripleSignal,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)

# Stream / consumer group names
GRAPH_INFERENCE_STREAM = "graph.inference.complete"
CONSUMER_GROUP = "enrich-convergence-group"
CONSUMER_NAME = "graph-inference-consumer-1"

# Minimum confidence to feed triple back as enrichment signal
MIN_TRIPLE_CONFIDENCE: float = 0.70


class GraphInferenceConsumer:
    """
    Long-running consumer that bridges GRAPH materialization events back
    into the EIE convergence loop.

    Each event contains a list of InferredTripleSignal objects. Triples
    meeting the confidence threshold are forwarded to the active convergence
    run for the entity via an asyncio.Queue.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis: aioredis.Redis | None = None
        self._running = False
        # Maps run_id → asyncio.Queue[list[InferredTripleSignal]]
        self._signal_queues: dict[str, asyncio.Queue[list[InferredTripleSignal]]] = {}

    async def start(self) -> None:
        """Connect to Redis and ensure consumer group exists."""
        self._redis = aioredis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        # Ensure stream + consumer group exist
        try:
            await self._redis.xgroup_create(
                GRAPH_INFERENCE_STREAM,
                CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info("consumer_group_created", extra={"stream": GRAPH_INFERENCE_STREAM})
        except Exception:
            # Group already exists — expected on restart
            pass
        self._running = True
        logger.info("graph_inference_consumer_started")

    async def stop(self) -> None:
        self._running = False
        if self._redis:
            await self._redis.aclose()
        logger.info("graph_inference_consumer_stopped")

    def register_run(self, run_id: str) -> asyncio.Queue[list[InferredTripleSignal]]:
        """Register a convergence run_id so it can receive GRAPH signals."""
        q: asyncio.Queue[list[InferredTripleSignal]] = asyncio.Queue(maxsize=100)
        self._signal_queues[run_id] = q
        return q

    def deregister_run(self, run_id: str) -> None:
        self._signal_queues.pop(run_id, None)

    async def run(self) -> None:
        """Main consumer loop — blocks until stop() is called."""
        assert self._redis is not None, "Call start() before run()"
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={GRAPH_INFERENCE_STREAM: ">"},
                    count=50,
                    block=2000,  # ms
                )
                if not messages:
                    continue
                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        await self._handle_message(msg_id, fields)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("consumer_error", extra={"error": str(exc)})
                await asyncio.sleep(1.0)

    async def _handle_message(self, msg_id: str, fields: dict[str, str]) -> None:
        assert self._redis is not None
        try:
            raw = json.loads(fields.get("payload", "{}"))
            event = GraphInferenceEvent.model_validate(raw)

            # Filter triples by confidence threshold
            qualifying = [
                t for t in event.inferred_triples
                if t.confidence >= MIN_TRIPLE_CONFIDENCE
            ]

            if qualifying and event.run_id in self._signal_queues:
                q = self._signal_queues[event.run_id]
                if not q.full():
                    await q.put(qualifying)
                    logger.debug(
                        "graph_signal_queued",
                        extra={
                            "run_id": event.run_id,
                            "triples": len(qualifying),
                            "entity_id": event.entity_id,
                        },
                    )

            # ACK
            await self._redis.xack(GRAPH_INFERENCE_STREAM, CONSUMER_GROUP, msg_id)

        except Exception as exc:
            logger.warning(
                "graph_signal_parse_error",
                extra={"msg_id": msg_id, "error": str(exc)},
            )
            # ACK anyway to avoid poison-pill redelivery
            await self._redis.xack(GRAPH_INFERENCE_STREAM, CONSUMER_GROUP, msg_id)
