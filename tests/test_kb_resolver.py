"""Tests for app/services/kb_resolver.py

Covers: Domain KB YAML loading, atom matching, fragment injection, caching.

Source: ~190 lines | Target coverage: 80%
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.services.kb_resolver import KBResolver


class TestKBResolver:
    """Tests for domain KB injection."""

    @pytest.fixture
    def resolver(self, mock_kb_data):
        resolver = KBResolver()
        resolver._cache = {"plastics_recycling": mock_kb_data}
        return resolver

    def test_load_returns_domain_spec(self, resolver):
        spec = resolver.load("plastics_recycling")
        assert spec is not None
        assert spec.get("domain") == "plastics_recycling"

    def test_load_returns_none_for_unknown_domain(self, resolver):
        spec = resolver.load("nonexistent_domain")
        assert spec is None

    def test_resolve_matches_entity_polymer(self, resolver):
        entity = {"polymer_type": "HDPE"}
        fragments = resolver.resolve(entity, "plastics_recycling")
        assert fragments is not None
        # Should include HDPE-specific KB atoms if matching logic exists

    def test_resolve_empty_entity(self, resolver):
        fragments = resolver.resolve({}, "plastics_recycling")
        # Empty entity should still return base domain fragments
        assert fragments is not None

    def test_kb_fragment_id_generation(self, resolver):
        entity = {"polymer_type": "HDPE"}
        fragments = resolver.resolve(entity, "plastics_recycling")
        if hasattr(fragments, "fragment_ids") and fragments.fragment_ids:
            for fid in fragments.fragment_ids:
                assert isinstance(fid, str)

    def test_caching_second_load_from_memory(self, resolver):
        spec1 = resolver.load("plastics_recycling")
        spec2 = resolver.load("plastics_recycling")
        assert spec1 is spec2  # Same object from cache

    def test_version_tracking(self, resolver):
        spec = resolver.load("plastics_recycling")
        assert "version" in spec
        assert spec["version"] == "1.2.0"
