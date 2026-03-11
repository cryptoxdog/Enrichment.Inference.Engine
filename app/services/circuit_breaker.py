"""
Three-state circuit breaker: closed → open → half_open → closed.

Audit fix C2: Module-level singleton shared across all requests
within a worker process. Not per-request instantiation.

Audit fix M4: Logs state transitions.
"""

from __future__ import annotations

import time

import structlog

logger = structlog.get_logger("circuit_breaker")


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown: int = 60):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.failures = 0
        self.last_failure: float = 0.0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= self.failure_threshold and self.state != "open":
            self.state = "open"
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failures,
                cooldown=self.cooldown,
            )

    def record_success(self) -> None:
        if self.state != "closed":
            logger.info("circuit_breaker_closed", previous_state=self.state)
        self.failures = 0
        self.state = "closed"

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.monotonic() - self.last_failure > self.cooldown:
                self.state = "half_open"
                logger.info("circuit_breaker_half_open")
                return True
            return False
        return True  # half_open: allow one probe

    @property
    def is_open(self) -> bool:
        return self.state == "open"
