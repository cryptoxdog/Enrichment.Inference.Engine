"""Token budget enforcement and per-pass cost accounting."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_RATE_PER_1K = 0.005  # USD per 1K tokens (sonar-reasoning default)


class CostSummary(BaseModel):
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    tokens_per_pass: list[int] = Field(default_factory=list)
    cost_per_field: float = 0.0
    budget_utilization_pct: float = 0.0


class CostTracker:
    """Tracks token spend across convergence passes and enforces a hard budget ceiling."""

    __slots__ = (
        "_max_tokens",
        "_rate_per_1k",
        "_tokens_used",
        "_tokens_per_pass",
    )

    def __init__(
        self,
        max_budget_tokens: int,
        rate_per_1k: float = DEFAULT_RATE_PER_1K,
    ) -> None:
        if max_budget_tokens <= 0:
            raise ValueError("max_budget_tokens must be positive")
        self._max_tokens = max_budget_tokens
        self._rate_per_1k = rate_per_1k
        self._tokens_used = 0
        self._tokens_per_pass: list[int] = []

    def record_pass(self, pass_number: int, tokens_used: int) -> None:
        if tokens_used < 0:
            raise ValueError("tokens_used cannot be negative")
        self._tokens_used += tokens_used
        while len(self._tokens_per_pass) < pass_number:
            self._tokens_per_pass.append(0)
        self._tokens_per_pass[pass_number - 1] = tokens_used
        logger.debug(
            "cost_tracker.record: pass=%d tokens=%d total=%d/%d",
            pass_number, tokens_used, self._tokens_used, self._max_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self._tokens_used

    @property
    def total_cost_usd(self) -> float:
        return round(self._tokens_used * self._rate_per_1k / 1000.0, 6)

    def budget_remaining(self) -> int:
        return max(0, self._max_tokens - self._tokens_used)

    def can_continue(self) -> bool:
        return self._tokens_used < self._max_tokens

    def cost_per_field(self, total_fields_discovered: int) -> float:
        if total_fields_discovered <= 0:
            return 0.0
        return round(self.total_cost_usd / total_fields_discovered, 6)

    def to_summary(self, total_fields_discovered: int = 0) -> CostSummary:
        utilization = (self._tokens_used / self._max_tokens * 100.0) if self._max_tokens > 0 else 0.0
        return CostSummary(
            total_tokens=self._tokens_used,
            total_cost_usd=self.total_cost_usd,
            tokens_per_pass=list(self._tokens_per_pass),
            cost_per_field=self.cost_per_field(total_fields_discovered),
            budget_utilization_pct=round(utilization, 2),
        )
