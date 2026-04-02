# --- L9_META ---
# l9_schema: 1
# origin: l9-enrich-node
# engine: enrich
# layer: [core, config]
# tags: [L9_CONFIG, settings, backward-compat]
# owner: platform
# status: active
# --- /L9_META ---
"""
app/core/config.py

GAP #04: max_budget_tokens alias (token_budget, max_tokens).
GAP #05: perplexity_api_key safe empty-string default.

Settings model for the Enrichment Inference Engine node.
All env vars are read from the environment with safe defaults.

Aliases:
  - max_budget_tokens ← token_budget ← max_tokens (highest priority wins)
  - perplexity_api_key defaults to "" so startup doesn't crash when absent
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """L9 Enrichment Inference Engine settings."""

    # Database
    database_url: str = ""

    # Perplexity
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-pro"
    perplexity_temperature: float = 0.1

    # Token budget — canonical field
    max_budget_tokens: int = 4096

    # Backward-compat aliases (resolved in validator)
    token_budget: Optional[int] = None
    max_tokens: Optional[int] = None

    # Convergence defaults
    default_max_passes: int = 5
    default_confidence_threshold: float = 0.85

    # Downstream service URLs (optional — hooks skip when unset)
    graph_service_url: str = ""
    score_service_url: str = ""

    # Observability
    log_level: str = "INFO"
    otel_endpoint: str = ""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def resolve_token_budget_aliases(self) -> "Settings":
        """
        Resolve backward-compat aliases into max_budget_tokens.

        Priority: max_tokens > token_budget > max_budget_tokens (default).
        """
        if self.max_tokens is not None:
            self.max_budget_tokens = self.max_tokens
        elif self.token_budget is not None:
            self.max_budget_tokens = self.token_budget
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
