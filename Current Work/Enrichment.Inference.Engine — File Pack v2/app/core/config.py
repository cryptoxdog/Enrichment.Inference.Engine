"""
app/core/config.py
Centralised settings using pydantic-settings.
All environment variables live here — single source of truth.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Auth ──────────────────────────────────────────────────
    enrich_api_key: str = "dev-key"

    # ── LLM ───────────────────────────────────────────────────
    perplexity_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Graph ─────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # ── Persistence ───────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://enrich:changeme@localhost:5432/enrich"
    redis_url: str | None = None

    # ── Constellation nodes ───────────────────────────────────
    graph_node_url: str = "http://localhost:8001"
    score_node_url: str = "http://localhost:8002"
    route_node_url: str = "http://localhost:8003"
    inter_node_secret: str = "dev-inter-node-secret"

    # ── App ───────────────────────────────────────────────────
    log_level: str = "INFO"
    environment: str = "development"
    port: int = 8000
    workers: int = 4
    domains_dir: str = "./domains"
    default_domain: str = "plasticos"
    max_budget_tokens_default: int = 50_000
    token_rate_usd_per_1k: float = 0.005


settings = Settings()
