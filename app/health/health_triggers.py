"""
HEALTH trigger engine — HEALTH → ENRICH feedback channel.

Manages the lifecycle of re-enrichment triggers: generation, deduplication,
priority queuing, rate limiting, and delivery via the enrichment profiles system.
This is the concrete implementation of Gap #22 (graph→enrichment feedback channel)
applied to the HEALTH service.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from .health_models import (
    EnrichmentTrigger,
    TriggerReason,
)


# ─── Trigger Store Protocol ──────────────────────────────────

class TriggerStore(Protocol):
    """Persistence layer for enrichment triggers."""

    def save(self, trigger: EnrichmentTrigger) -> None: ...
    def get(self, trigger_id: UUID) -> EnrichmentTrigger | None: ...
    def list_pending(self, domain: str, limit: int = 100) -> list[EnrichmentTrigger]: ...
    def mark_dispatched(self, trigger_id: UUID, dispatched_at: datetime) -> None: ...
    def mark_completed(self, trigger_id: UUID, completed_at: datetime) -> None: ...
    def count_pending(self, domain: str) -> int: ...
    def count_dispatched_since(self, domain: str, since: datetime) -> int: ...
    def get_recent_for_entity(self, entity_id: str, since: datetime) -> list[EnrichmentTrigger]: ...


# ─── Enrichment Dispatcher Protocol ─────────────────────────

class EnrichmentDispatcher(Protocol):
    """Interface to the ENRICH service for queueing re-enrichment."""

    def queue_enrichment(
        self,
        entity_id: str,
        domain: str,
        target_fields: list[str],
        priority: float,
        trigger_id: UUID,
    ) -> str: ...


# ─── Trigger Configuration ───────────────────────────────────

class TriggerConfig:
    __slots__ = (
        "max_triggers_per_hour",
        "max_triggers_per_entity_per_day",
        "cooldown_minutes",
        "batch_size",
        "priority_boost_gate_fields",
        "dedup_window_hours",
    )

    def __init__(
        self,
        max_triggers_per_hour: int = 500,
        max_triggers_per_entity_per_day: int = 3,
        cooldown_minutes: int = 30,
        batch_size: int = 50,
        priority_boost_gate_fields: float = 0.20,
        dedup_window_hours: int = 4,
    ):
        self.max_triggers_per_hour = max_triggers_per_hour
        self.max_triggers_per_entity_per_day = max_triggers_per_entity_per_day
        self.cooldown_minutes = cooldown_minutes
        self.batch_size = batch_size
        self.priority_boost_gate_fields = priority_boost_gate_fields
        self.dedup_window_hours = dedup_window_hours


# ─── Trigger Engine ──────────────────────────────────────────

class TriggerEngine:
    """Manages the HEALTH → ENRICH trigger lifecycle.

    Responsibilities:
    1. Accept triggers from HealthAssessor
    2. Deduplicate (don't re-trigger same entity within window)
    3. Rate-limit (don't flood ENRICH with requests)
    4. Priority-sort (gate-field-missing > staleness > low-confidence > ...)
    5. Dispatch to ENRICH via EnrichmentDispatcher
    """

    def __init__(
        self,
        store: TriggerStore,
        dispatcher: EnrichmentDispatcher,
        config: TriggerConfig | None = None,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._config = config or TriggerConfig()

    def ingest_triggers(self, triggers: list[EnrichmentTrigger]) -> IngestResult:
        """Accept triggers from an assessment run, deduplicate, and persist."""
        now = datetime.now(timezone.utc)
        dedup_since = now - timedelta(hours=self._config.dedup_window_hours)

        accepted: list[EnrichmentTrigger] = []
        deduplicated = 0
        rate_limited = 0

        entity_trigger_counts: dict[str, int] = defaultdict(int)

        for trigger in triggers:
            recent = self._store.get_recent_for_entity(trigger.entity_id, dedup_since)
            if self._is_duplicate(trigger, recent):
                deduplicated += 1
                continue

            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_triggers = self._store.get_recent_for_entity(trigger.entity_id, day_start)
            if len(day_triggers) + entity_trigger_counts[trigger.entity_id] >= self._config.max_triggers_per_entity_per_day:
                rate_limited += 1
                continue

            if trigger.reason == TriggerReason.GATE_FIELD_MISSING:
                trigger = EnrichmentTrigger(
                    trigger_id=trigger.trigger_id,
                    entity_id=trigger.entity_id,
                    domain=trigger.domain,
                    reason=trigger.reason,
                    priority=min(1.0, trigger.priority + self._config.priority_boost_gate_fields),
                    target_fields=trigger.target_fields,
                    current_health=trigger.current_health,
                    created_at=trigger.created_at,
                    metadata=trigger.metadata,
                )

            self._store.save(trigger)
            accepted.append(trigger)
            entity_trigger_counts[trigger.entity_id] += 1

        return IngestResult(
            total_received=len(triggers),
            accepted=len(accepted),
            deduplicated=deduplicated,
            rate_limited=rate_limited,
        )

    def dispatch_batch(self, domain: str) -> DispatchResult:
        """Dispatch the next batch of pending triggers to ENRICH.

        Rate-limited to max_triggers_per_hour. Returns dispatch results
        including any failures.
        """
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        dispatched_recently = self._store.count_dispatched_since(domain, hour_ago)
        remaining_capacity = max(0, self._config.max_triggers_per_hour - dispatched_recently)

        if remaining_capacity == 0:
            return DispatchResult(
                dispatched=0,
                failed=0,
                rate_limited=True,
                capacity_remaining=0,
            )

        batch_size = min(self._config.batch_size, remaining_capacity)
        pending = self._store.list_pending(domain, limit=batch_size)

        dispatched = 0
        failed = 0
        failures: list[dict[str, Any]] = []

        for trigger in pending:
            try:
                enrich_ref = self._dispatcher.queue_enrichment(
                    entity_id=trigger.entity_id,
                    domain=trigger.domain,
                    target_fields=trigger.target_fields,
                    priority=trigger.priority,
                    trigger_id=trigger.trigger_id,
                )
                self._store.mark_dispatched(trigger.trigger_id, now)
                dispatched += 1
            except Exception as exc:
                failed += 1
                failures.append({
                    "trigger_id": str(trigger.trigger_id),
                    "entity_id": trigger.entity_id,
                    "error": str(exc),
                })

        return DispatchResult(
            dispatched=dispatched,
            failed=failed,
            rate_limited=False,
            capacity_remaining=remaining_capacity - dispatched,
            failures=failures,
        )

    def get_queue_status(self, domain: str) -> QueueStatus:
        """Return current trigger queue metrics."""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        pending = self._store.count_pending(domain)
        dispatched_hour = self._store.count_dispatched_since(domain, hour_ago)
        remaining = max(0, self._config.max_triggers_per_hour - dispatched_hour)

        return QueueStatus(
            domain=domain,
            pending_count=pending,
            dispatched_last_hour=dispatched_hour,
            hourly_capacity=self._config.max_triggers_per_hour,
            remaining_capacity=remaining,
            batch_size=self._config.batch_size,
        )

    # ─── Internal ─────────────────────────────────────────────

    def _is_duplicate(
        self,
        trigger: EnrichmentTrigger,
        recent: list[EnrichmentTrigger],
    ) -> bool:
        """Check if an equivalent trigger already exists within the dedup window."""
        for existing in recent:
            if existing.reason == trigger.reason:
                if set(existing.target_fields) == set(trigger.target_fields):
                    return True
                if not existing.target_fields and not trigger.target_fields:
                    return True
        return False


# ─── Result Models ────────────────────────────────────────────

class IngestResult:
    __slots__ = ("total_received", "accepted", "deduplicated", "rate_limited")

    def __init__(self, total_received: int, accepted: int, deduplicated: int, rate_limited: int):
        self.total_received = total_received
        self.accepted = accepted
        self.deduplicated = deduplicated
        self.rate_limited = rate_limited

    def to_dict(self) -> dict[str, int]:
        return {
            "total_received": self.total_received,
            "accepted": self.accepted,
            "deduplicated": self.deduplicated,
            "rate_limited": self.rate_limited,
        }


class DispatchResult:
    __slots__ = ("dispatched", "failed", "rate_limited", "capacity_remaining", "failures")

    def __init__(
        self,
        dispatched: int,
        failed: int,
        rate_limited: bool,
        capacity_remaining: int,
        failures: list[dict[str, Any]] | None = None,
    ):
        self.dispatched = dispatched
        self.failed = failed
        self.rate_limited = rate_limited
        self.capacity_remaining = capacity_remaining
        self.failures = failures or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "capacity_remaining": self.capacity_remaining,
            "failures": self.failures,
        }


class QueueStatus:
    __slots__ = (
        "domain", "pending_count", "dispatched_last_hour",
        "hourly_capacity", "remaining_capacity", "batch_size",
    )

    def __init__(
        self,
        domain: str,
        pending_count: int,
        dispatched_last_hour: int,
        hourly_capacity: int,
        remaining_capacity: int,
        batch_size: int,
    ):
        self.domain = domain
        self.pending_count = pending_count
        self.dispatched_last_hour = dispatched_last_hour
        self.hourly_capacity = hourly_capacity
        self.remaining_capacity = remaining_capacity
        self.batch_size = batch_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "pending_count": self.pending_count,
            "dispatched_last_hour": self.dispatched_last_hour,
            "hourly_capacity": self.hourly_capacity,
            "remaining_capacity": self.remaining_capacity,
            "batch_size": self.batch_size,
        }
