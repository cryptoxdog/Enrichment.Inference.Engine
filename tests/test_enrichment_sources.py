"""
Tests for enrichment source adapters.

Validates that each source adapter:
1. Implements BaseSource contract
2. Handles missing API keys gracefully
3. Handles disabled state
4. Handles unsupported domains
5. Maps response fields to canonical names
"""

from __future__ import annotations

import pytest

from app.services.enrichment.sources import SOURCE_REGISTRY
from app.services.enrichment.sources.apollo import ApolloSource
from app.services.enrichment.sources.base import BaseSource, SourceConfig
from app.services.enrichment.sources.clearbit import ClearbitSource
from app.services.enrichment.sources.hunter import HunterSource
from app.services.enrichment.sources.zoominfo import ZoomInfoSource

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(name: str, enabled: bool = True, api_key: str = "test-key") -> SourceConfig:
    return SourceConfig(
        name=name,
        enabled=enabled,
        api_endpoint="https://api.example.com",
        auth_type="api_key",
        api_key=api_key,
        timeout=10,
        retry_count=1,
        supported_domains=["company", "contact"],
        quality_tier="standard",
    )


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------


class TestSourceRegistry:
    """Verify all sources are registered."""

    def test_registry_has_all_sources(self) -> None:
        expected = {"perplexity_sonar", "clearbit", "zoominfo", "apollo", "hunter"}
        assert expected == set(SOURCE_REGISTRY.keys())

    def test_all_registry_values_are_base_source(self) -> None:
        for name, cls in SOURCE_REGISTRY.items():
            assert issubclass(cls, BaseSource), f"{name} is not a BaseSource"


# ---------------------------------------------------------------------------
# Contract Tests — every adapter must handle these edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_cls,name",
    [
        (ClearbitSource, "clearbit"),
        (ZoomInfoSource, "zoominfo"),
        (ApolloSource, "apollo"),
        (HunterSource, "hunter"),
    ],
)
class TestSourceContract:
    """Contract tests that every source adapter must pass."""

    @pytest.mark.asyncio
    async def test_disabled_source_returns_error(self, source_cls: type, name: str) -> None:
        config = _make_config(name, enabled=False)
        src = source_cls(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert result.quality_score == 0.0
        assert result.error == "source_disabled"

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self, source_cls: type, name: str) -> None:
        config = _make_config(name, api_key="")
        src = source_cls(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert result.quality_score == 0.0
        assert result.error == "missing_api_key"

    @pytest.mark.asyncio
    async def test_result_has_source_name(self, source_cls: type, name: str) -> None:
        config = _make_config(name, enabled=False)
        src = source_cls(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert result.source_name == name

    @pytest.mark.asyncio
    async def test_result_has_latency(self, source_cls: type, name: str) -> None:
        config = _make_config(name, enabled=False)
        src = source_cls(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert isinstance(result.latency_ms, int)
        assert result.latency_ms >= 0


# ---------------------------------------------------------------------------
# Hunter-specific: contact-only domain
# ---------------------------------------------------------------------------


class TestHunterDomainRestriction:
    """Hunter only supports contact domain."""

    @pytest.mark.asyncio
    async def test_company_domain_returns_unsupported(self) -> None:
        config = _make_config("hunter")
        src = HunterSource(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert result.error == "unsupported_domain"

    @pytest.mark.asyncio
    async def test_contact_without_identifier_returns_error(self) -> None:
        config = _make_config("hunter")
        src = HunterSource(config=config)
        result = await src.enrich("contact", {})
        assert result.error == "missing_identifier"


# ---------------------------------------------------------------------------
# Apollo-specific: missing identifier
# ---------------------------------------------------------------------------


class TestApolloMissingIdentifier:
    """Apollo needs company_domain for company enrichment."""

    @pytest.mark.asyncio
    async def test_company_without_domain_returns_error(self) -> None:
        config = _make_config("apollo")
        src = ApolloSource(config=config)
        result = await src.enrich("company", {"company_name": "Test"})
        assert result.error == "missing_company_domain"
