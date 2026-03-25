"""
Base enrichment source interfaces and contracts.

Defines the abstract interface that all enrichment sources must implement.
Each source is a self-contained adapter that can be used within the
WaterfallEngine for multi-source enrichment with quality-based fallback.

L9 Architecture Note:
    This module is chassis-agnostic. Sources never import FastAPI.
    They receive domain + payload, return EnrichmentResult.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceConfig:
    """Configuration for an enrichment source."""

    name: str
    enabled: bool
    api_endpoint: str = ""
    auth_type: str = "bearer"
    api_key: str | None = None
    rate_limit: str | None = None
    cost_per_call: float = 0.0
    timeout: int = 10
    retry_count: int = 1
    supported_domains: list[str] = field(default_factory=list)
    quality_tier: str = "standard"


@dataclass
class EnrichmentResult:
    """Outcome of a single enrichment source call."""

    data: dict[str, Any]
    quality_score: float
    source_name: str
    latency_ms: int
    error: str | None = None


class BaseSource(ABC):
    """
    Abstract base class for enrichment sources.

    Concrete implementations must be deterministic and side-effect free
    beyond network IO and logging.
    """

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    async def enrich(
        self, domain: str, payload: dict[str, Any]
    ) -> EnrichmentResult:
        """
        Perform enrichment for a given domain and payload.

        Implementations must:
        - respect timeout
        - handle retries internally
        - never raise on network errors (return EnrichmentResult with error)
        """
        raise NotImplementedError

    def _now_ms(self) -> int:
        """Return current time in milliseconds."""
        return int(time.time() * 1000)
