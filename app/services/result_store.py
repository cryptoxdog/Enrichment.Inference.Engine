# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [services, persistence]
# tags: [L9_PERSISTENCE, pg_store, packet-safe]
# owner: platform
# status: active
# --- /L9_META ---
"""
app/services/result_store.py

GAP #01: ResultStore persistence layer — wires EnrichmentResult to pg_store.

Every converged enrichment pass produces an EnrichmentResult with:
  - tenant_id, entity_id, packet_id, lineage_id (PacketEnvelope trace)
  - pass_number, converged, confidence
  - enriched_fields (dict)
  - content_hash (SHA-256 of sorted enriched_fields — deterministic)
  - timestamp (UTC)

ResultStore.save() persists to PostgreSQL enrichment_results table via upsert
(ON CONFLICT DO UPDATE).  The store is initialized at startup and torn down
at shutdown via lifecycle hooks in app/main.py.

Storage backend: PostgreSQL via asyncpg connection pool.  The store is a
singleton — one pool per process.  All async operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import asyncpg

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _dsn_for_log(dsn: str) -> str:
    """Host + database for logs only (no userinfo)."""
    try:
        parsed = urlparse(dsn)
        if parsed.hostname:
            port = f":{parsed.port}" if parsed.port else ""
            db = (parsed.path or "").lstrip("/") or "?"
            return f"{parsed.scheme}://{parsed.hostname}{port}/{db}"
    except Exception:
        pass
    return "postgresql"


class StorePersistenceError(Exception):
    """Raised when ResultStore save() encounters unrecoverable errors."""


@dataclass
class EnrichmentResult:
    """Immutable enrichment result record."""

    tenant_id: str
    entity_id: str
    packet_id: str
    lineage_id: str
    pass_number: int
    converged: bool
    confidence: float
    enriched_fields: dict[str, Any]
    content_hash: str = field(init=False)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self):
        """Compute deterministic content_hash from enriched_fields."""
        serialized = json.dumps(self.enriched_fields, sort_keys=True, default=str)
        self.content_hash = hashlib.sha256(serialized.encode()).hexdigest()


class ResultStore:
    """Singleton persistence layer for enrichment results."""

    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def initialize(self, dsn: str) -> None:
        """Create the asyncpg pool and ensure the enrichment_results table exists."""
        self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        await self._ensure_table()
        logger.info(
            "result_store_initialized",
            extra={"database": _dsn_for_log(dsn)},
        )

    async def shutdown(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("result_store_shutdown")

    async def _ensure_table(self) -> None:
        """Create enrichment_results table if it doesn't exist (idempotent)."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrichment_results (
                    tenant_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    packet_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    pass_number INT NOT NULL,
                    converged BOOLEAN NOT NULL,
                    confidence FLOAT NOT NULL,
                    enriched_fields JSONB NOT NULL,
                    content_hash TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tenant_id, entity_id, packet_id, pass_number)
                );
                CREATE INDEX IF NOT EXISTS idx_enrichment_results_lineage
                    ON enrichment_results (lineage_id);
                CREATE INDEX IF NOT EXISTS idx_enrichment_results_hash
                    ON enrichment_results (content_hash);
                """
            )

    async def save(self, result: EnrichmentResult) -> None:
        """Persist enrichment result to pg_store.  Upserts on conflict."""
        if not self._pool:
            logger.warning(
                "result_store_save_skipped_no_pool",
                extra={"entity_id": result.entity_id},
            )
            return

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO enrichment_results (
                        tenant_id, entity_id, packet_id, lineage_id, pass_number,
                        converged, confidence, enriched_fields, content_hash, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (tenant_id, entity_id, packet_id, pass_number)
                    DO UPDATE SET
                        lineage_id = EXCLUDED.lineage_id,
                        converged = EXCLUDED.converged,
                        confidence = EXCLUDED.confidence,
                        enriched_fields = EXCLUDED.enriched_fields,
                        content_hash = EXCLUDED.content_hash,
                        timestamp = EXCLUDED.timestamp
                    """,
                    result.tenant_id,
                    result.entity_id,
                    result.packet_id,
                    result.lineage_id,
                    result.pass_number,
                    result.converged,
                    result.confidence,
                    json.dumps(result.enriched_fields),
                    result.content_hash,
                    result.timestamp,
                )
            logger.info(
                "enrichment_result_saved",
                extra={
                    "entity_id": result.entity_id,
                    "pass": result.pass_number,
                    "converged": result.converged,
                    "hash": result.content_hash[:12],
                },
            )
        except Exception as e:
            logger.error(
                "result_store_save_failed",
                extra={"entity_id": result.entity_id, "error": str(e)},
                exc_info=True,
            )
            raise StorePersistenceError(f"Failed to save result: {e}") from e


# Singleton instance
_store: ResultStore | None = None


def get_result_store() -> ResultStore:
    """Return the singleton ResultStore instance."""
    global _store
    if _store is None:
        _store = ResultStore()
    return _store


async def startup_result_store() -> None:
    """Initialize the result store at app startup."""
    settings = get_settings()
    store = get_result_store()
    if settings.database_url:
        await store.initialize(settings.database_url)
    else:
        logger.warning("result_store_not_initialized_no_database_url")


async def shutdown_result_store() -> None:
    """Shutdown the result store at app shutdown."""
    store = get_result_store()
    await store.shutdown()
