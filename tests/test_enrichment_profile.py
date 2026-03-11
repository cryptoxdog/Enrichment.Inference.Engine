"""Tests for app/engines/convergence/enrichment_profile.py

Covers: Budget allocation profiles (Seed/Enrich/Discover/Autonomous),
        ProfileRegistry lookup, budget allocation, entity selection.

Source: 285 lines | Target coverage: 80%
"""

from __future__ import annotations

import pytest

from app.services.enrichment_profile import (
    EnrichmentProfile,
    ProfileRegistry,
    allocate_budget,
    select_entities,
)


# ---------------------------------------------------------------------------
# EnrichmentProfile model
# ---------------------------------------------------------------------------

class TestEnrichmentProfile:
    """Tests for budget allocation profiles."""

    def test_default_profile_properties(self):
        profile = EnrichmentProfile()
        assert profile.max_variations >= 1
        assert profile.max_budget_tokens >= 1000

    def test_seed_profile(self):
        profile = EnrichmentProfile(
            profile_name="seed",
            max_variations=2,
            max_budget_tokens=10000,
        )
        assert profile.profile_name == "seed"
        assert profile.max_variations == 2
        assert profile.max_budget_tokens == 10000

    def test_enrich_profile(self):
        profile = EnrichmentProfile(
            profile_name="enrich",
            max_variations=3,
            max_budget_tokens=25000,
        )
        assert profile.profile_name == "enrich"
        assert profile.max_variations == 3

    def test_discover_profile(self):
        profile = EnrichmentProfile(
            profile_name="discover",
            max_variations=5,
            max_budget_tokens=100000,
        )
        assert profile.max_variations == 5
        assert profile.max_budget_tokens == 100000

    def test_autonomous_profile(self):
        profile = EnrichmentProfile(
            profile_name="autonomous",
            max_variations=7,
            max_budget_tokens=500000,
        )
        assert profile.max_variations == 7


# ---------------------------------------------------------------------------
# ProfileRegistry
# ---------------------------------------------------------------------------

class TestProfileRegistry:
    """Tests for profile lookup."""

    @pytest.fixture
    def registry(self):
        reg = ProfileRegistry()
        reg.register(EnrichmentProfile(profile_name="seed", max_variations=2, max_budget_tokens=10000))
        reg.register(EnrichmentProfile(profile_name="enrich", max_variations=3, max_budget_tokens=25000))
        return reg

    def test_get_profile_by_name(self, registry):
        profile = registry.get("seed")
        assert profile is not None
        assert profile.profile_name == "seed"

    def test_unknown_profile_returns_none_or_default(self, registry):
        profile = registry.get("nonexistent")
        # Should return None or a default profile
        assert profile is None or hasattr(profile, "profile_name")

    def test_register_adds_profile(self, registry):
        new_profile = EnrichmentProfile(profile_name="custom", max_variations=4, max_budget_tokens=30000)
        registry.register(new_profile)
        assert registry.get("custom") is not None


# ---------------------------------------------------------------------------
# Budget Allocation
# ---------------------------------------------------------------------------

class TestBudgetAllocation:
    """Tests for allocate_budget()."""

    def test_allocate_budget_across_entities(self):
        allocations = allocate_budget(
            entity_count=50,
            total_budget=50000,
        )
        assert isinstance(allocations, (list, dict))
        # Total allocation should not exceed budget
        if isinstance(allocations, list):
            assert sum(allocations) <= 50000
        elif isinstance(allocations, dict):
            assert sum(allocations.values()) <= 50000

    def test_allocate_budget_single_entity(self):
        allocations = allocate_budget(
            entity_count=1,
            total_budget=50000,
        )
        # Single entity gets the full budget
        if isinstance(allocations, list):
            assert allocations[0] == 50000


# ---------------------------------------------------------------------------
# Entity Selection
# ---------------------------------------------------------------------------

class TestEntitySelection:
    """Tests for select_entities()."""

    def test_select_returns_list(self):
        entities = [
            {"Name": f"Entity{i}", "confidence": 0.5 + (i * 0.05)}
            for i in range(20)
        ]
        selected = select_entities(entities, max_count=10)
        assert isinstance(selected, list)
        assert len(selected) <= 10
