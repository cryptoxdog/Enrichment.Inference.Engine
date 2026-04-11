"""
Settings — single source of truth for all configuration.
Loaded once at startup from env vars / .env file.

Gap pack adaptations:
- keep `max_budget_tokens` canonical
- accept deprecated aliases `max_tokens` and `token_budget`
- keep `perplexity_api_key` safe as empty string
- expose `warn_missing_keys()` for startup diagnostics
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger("core.config")


class Settings(BaseSettings):
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-reasoning"

    api_secret_key: str = ""
    api_key_hash: str = ""

    kb_dir: str = "/app/kb"

    redis_url: str = "redis://localhost:6379/0"

    default_consensus_threshold: float = 0.65
    default_max_variations: int = 5
    default_timeout_seconds: int = 120
    max_concurrent_variations: int = 3
    max_entities_per_batch: int = 50

    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_password: str = ""
    crm_mapping_path: str = "config/crm/odoo_mapping.yaml"

    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""

    hubspot_access_token: str = ""

    clearbit_api_key: str = ""
    zoominfo_api_key: str = ""
    apollo_api_key: str = ""
    hunter_api_key: str = ""

    ceg_base_url: str = "http://localhost:8001"

    graph_node_url: str = "http://localhost:8001"
    score_node_url: str = "http://localhost:8002"
    route_node_url: str = "http://localhost:8003"
    inter_node_secret: str = "dev-inter-node-secret"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    database_url: str = "postgresql+asyncpg://enrich:changeme@localhost:5432/enrich"

    domains_dir: str = "./domains"
    default_domain: str = "plasticos"

    max_budget_tokens: int = 50_000
    max_budget_tokens_default: int = 50_000
    max_tokens: int = 50_000
    token_budget: int = 50_000
    token_rate_usd_per_1k: float = 0.005

    cb_failure_threshold: int = 5
    cb_cooldown_seconds: int = 60

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        data = dict(values)
        if data.get("perplexity_api_key") is None:
            data["perplexity_api_key"] = ""

        alias_candidates = (
            data.get("max_budget_tokens"),
            data.get("max_tokens"),
            data.get("token_budget"),
            data.get("max_budget_tokens_default"),
        )
        for candidate in alias_candidates:
            if candidate not in (None, ""):
                normalized = int(candidate)
                data["max_budget_tokens"] = normalized
                data.setdefault("max_tokens", normalized)
                data.setdefault("token_budget", normalized)
                break

        return data

    @model_validator(mode="after")
    def align_legacy_token_budget(self) -> Settings:
        """Keep token budget aliases synchronized after settings resolution."""
        alias_value = self.max_budget_tokens
        if self.max_tokens != 50_000 and self.max_budget_tokens == 50_000:
            alias_value = self.max_tokens
        elif self.token_budget != 50_000 and self.max_budget_tokens == 50_000:
            alias_value = self.token_budget
        elif (
            self.max_budget_tokens_default != 50_000
            and self.max_budget_tokens == 50_000
            and self.max_tokens == 50_000
            and self.token_budget == 50_000
        ):
            alias_value = self.max_budget_tokens_default

        self.max_budget_tokens = int(alias_value)
        self.max_tokens = int(alias_value)
        self.token_budget = int(alias_value)
        return self

    def warn_missing_keys(self) -> None:
        if not self.perplexity_api_key:
            logger.warning(
                "config.perplexity_api_key_missing",
                hint="Set PERPLEXITY_API_KEY to enable Sonar enrichment passes.",
            )
        if not self.api_key_hash:
            logger.warning(
                "config.api_key_hash_missing",
                hint="Set API_KEY_HASH so authenticated endpoints can validate callers.",
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
