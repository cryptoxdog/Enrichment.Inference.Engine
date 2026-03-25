"""
Tests for WaterfallEngine auto-registration from provider config.
"""
from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from app.services.enrichment.waterfall_engine import WaterfallEngine
from app.services.enrichment.sources.clearbit import ClearbitSource
from app.services.enrichment.sources.apollo import ApolloSource


class TestAutoRegisterSources:
    """Verify auto_register_sources reads config and creates source instances."""

    def test_auto_register_from_config(self, tmp_path) -> None:
        config = {
            "providers": {
                "clearbit": {
                    "enabled": True,
                    "api_key": "test-clearbit-key",
                    "base_url": "https://company.clearbit.com",
                    "auth_type": "bearer",
                    "timeout": 15,
                    "supported_domains": ["company", "contact"],
                    "quality_tier": "premium",
                },
                "apollo": {
                    "enabled": True,
                    "api_key": "test-apollo-key",
                    "base_url": "https://api.apollo.io/api/v1",
                    "auth_type": "api_key",
                    "timeout": 20,
                    "supported_domains": ["company", "contact"],
                    "quality_tier": "standard",
                },
            }
        }
        config_path = tmp_path / "provider_config.yaml"
        config_path.write_text(yaml.dump(config))

        engine = WaterfallEngine()
        engine.auto_register_sources(str(config_path))

        assert "clearbit" in engine.source_clients
        assert "apollo" in engine.source_clients
        assert isinstance(engine.source_clients["clearbit"], ClearbitSource)
        assert isinstance(engine.source_clients["apollo"], ApolloSource)

    def test_disabled_providers_not_registered(self, tmp_path) -> None:
        config = {
            "providers": {
                "clearbit": {
                    "enabled": False,
                    "api_key": "test-key",
                },
            }
        }
        config_path = tmp_path / "provider_config.yaml"
        config_path.write_text(yaml.dump(config))

        engine = WaterfallEngine()
        engine.auto_register_sources(str(config_path))

        assert "clearbit" not in engine.source_clients

    def test_placeholder_api_keys_skipped(self, tmp_path) -> None:
        config = {
            "providers": {
                "clearbit": {
                    "enabled": True,
                    "api_key": "${CLEARBIT_API_KEY}",
                },
            }
        }
        config_path = tmp_path / "provider_config.yaml"
        config_path.write_text(yaml.dump(config))

        engine = WaterfallEngine()
        engine.auto_register_sources(str(config_path))

        assert "clearbit" not in engine.source_clients

    def test_missing_config_file_handled(self) -> None:
        engine = WaterfallEngine()
        # Should not raise
        engine.auto_register_sources("/nonexistent/path.yaml")
        assert len(engine.source_clients) == 0

    def test_unknown_provider_skipped(self, tmp_path) -> None:
        config = {
            "providers": {
                "unknown_provider": {
                    "enabled": True,
                    "api_key": "test-key",
                },
            }
        }
        config_path = tmp_path / "provider_config.yaml"
        config_path.write_text(yaml.dump(config))

        engine = WaterfallEngine()
        engine.auto_register_sources(str(config_path))

        assert "unknown_provider" not in engine.source_clients

    def test_already_registered_not_overwritten(self, tmp_path) -> None:
        config = {
            "providers": {
                "clearbit": {
                    "enabled": True,
                    "api_key": "new-key",
                    "base_url": "https://new.clearbit.com",
                },
            }
        }
        config_path = tmp_path / "provider_config.yaml"
        config_path.write_text(yaml.dump(config))

        engine = WaterfallEngine()
        # Pre-register with old key
        from app.services.enrichment.sources.base import SourceConfig
        old_config = SourceConfig(
            name="clearbit", enabled=True, api_endpoint="https://old.clearbit.com",
            auth_type="bearer", api_key="old-key", timeout=10, retry_count=1,
            supported_domains=["company"], quality_tier="standard",
        )
        engine.source_clients["clearbit"] = ClearbitSource(config=old_config)

        engine.auto_register_sources(str(config_path))

        # Should keep the old one
        assert engine.source_clients["clearbit"].config.api_key == "old-key"
