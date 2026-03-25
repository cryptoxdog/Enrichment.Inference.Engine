"""
Settings — single source of truth for all configuration.
Loaded once at startup from env vars / .env file.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Perplexity ───────────────────────────────────
    perplexity_api_key: str
    perplexity_model: str = "sonar-reasoning"

    # ── Auth ─────────────────────────────────────────
    api_secret_key: str
    api_key_hash: str = ""

    # ── Knowledge Base ───────────────────────────────
    kb_dir: str = "/app/kb"

    # ── Redis ────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Enrichment ───────────────────────────────────
    default_consensus_threshold: float = 0.65
    default_max_variations: int = 5
    default_timeout_seconds: int = 120
    max_concurrent_variations: int = 3
    max_entities_per_batch: int = 50

    # ── CRM / Odoo (first consumer) ──────────────────
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_password: str = ""
    crm_mapping_path: str = "config/crm/odoo_mapping.yaml"

    # ── CRM / Salesforce ─────────────────────────────
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""

    # ── CRM / HubSpot ───────────────────────────────
    hubspot_access_token: str = ""

    # ── Enrichment Sources (waterfall providers) ─────
    clearbit_api_key: str = ""
    zoominfo_api_key: str = ""
    apollo_api_key: str = ""
    hunter_api_key: str = ""

    # ── Cognitive Engine Graphs (sibling node) ───────
    ceg_base_url: str = "http://localhost:8001"

    # ── Circuit Breaker ──────────────────────────────
    cb_failure_threshold: int = 5
    cb_cooldown_seconds: int = 60

    # ── Logging ──────────────────────────────────────
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
