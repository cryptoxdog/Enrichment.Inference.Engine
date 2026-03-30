"""Unit tests for KB resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.enrichment.kb_resolver import KBContext, KBResolver


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Create a temporary KB directory with test files."""
    kb_path = tmp_path / "kb"
    kb_path.mkdir()

    plastics_kb = kb_path / "plastics.yaml"
    plastics_kb.write_text("""
domain: plastics

preamble: |
  Plastics and polymer recycling knowledge base.

terminology:
  HDPE: High-Density Polyethylene
  PP: Polypropylene
  PCR: Post-Consumer Recycled

entity_hints:
  company:
    typical_fields:
      - company_name
      - polymer_types
    validation_focus:
      - polymer_expertise

default_hints:
  industry: plastics_recycling

validation_rules:
  polymer_type:
    pattern: "^(HDPE|PP|PET)$"

fragments:
  - id: plastics_polymers
    content: |
      Common polymer types: HDPE, PP, PET
    keywords:
      - polymer
      - HDPE
      - plastics
    entity_types:
      - company
    priority: 10

  - id: plastics_grades
    content: |
      Quality grades: Virgin, PCR, PIR
    keywords:
      - grade
      - quality
      - PCR
    entity_types:
      - company
      - product
    priority: 5
""")

    saas_kb = kb_path / "saas.yaml"
    saas_kb.write_text("""
domain: saas

preamble: |
  SaaS and technology company knowledge base.

terminology:
  ARR: Annual Recurring Revenue
  MRR: Monthly Recurring Revenue
  CAC: Customer Acquisition Cost

fragments:
  - id: saas_metrics
    content: |
      Key SaaS metrics: ARR, MRR, Churn, CAC, LTV
    keywords:
      - metrics
      - ARR
      - revenue
    entity_types:
      - company
    priority: 10
""")

    return kb_path


@pytest.fixture
def resolver(kb_dir: Path) -> KBResolver:
    """Create a KBResolver with the test KB directory."""
    return KBResolver(kb_dir=str(kb_dir))


class TestKBResolverLoad:
    """Tests for KBResolver loading."""

    def test_load_creates_cache(self, resolver: KBResolver) -> None:
        """Loading should populate the cache."""
        resolver.load()

        assert resolver.is_loaded
        assert "plastics" in resolver.domains
        assert "saas" in resolver.domains

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        """Loading from nonexistent directory should not raise."""
        resolver = KBResolver(kb_dir=str(tmp_path / "nonexistent"))
        resolver.load()

        assert resolver.is_loaded
        assert resolver.domains == []

    def test_lazy_load_on_resolve(self, resolver: KBResolver) -> None:
        """Resolve should trigger lazy load."""
        assert not resolver.is_loaded

        resolver.resolve(kb_context="plastics", entity={"name": "Test"})

        assert resolver.is_loaded


class TestKBResolverResolve:
    """Tests for KBResolver.resolve()."""

    def test_resolve_known_domain(self, resolver: KBResolver) -> None:
        """Resolving a known domain should return context."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "Acme Plastics", "type": "company"},
        )

        assert isinstance(result, KBContext)
        assert result.domain == "plastics"
        assert len(result.fragment_ids) > 0
        assert "plastics_polymers" in result.fragment_ids
        assert result.context_text != ""
        assert "HDPE" in result.terminology

    def test_resolve_unknown_domain(self, resolver: KBResolver) -> None:
        """Resolving an unknown domain should return empty context."""
        result = resolver.resolve(
            kb_context="unknown_domain",
            entity={"name": "Test"},
        )

        assert result.domain == "unknown_domain"
        assert result.fragment_ids == []
        assert result.context_text == ""

    def test_resolve_no_domain(self, resolver: KBResolver) -> None:
        """Resolving with no domain should return empty context."""
        result = resolver.resolve(
            kb_context=None,
            entity={"name": "Test"},
        )

        assert result.domain == ""
        assert result.fragment_ids == []

    def test_resolve_uses_entity_domain(self, resolver: KBResolver) -> None:
        """Entity domain should be used if kb_context is None."""
        result = resolver.resolve(
            kb_context=None,
            entity={"name": "Test", "domain": "saas"},
        )

        assert result.domain == "saas"
        assert "saas_metrics" in result.fragment_ids

    def test_resolve_max_fragments(self, resolver: KBResolver) -> None:
        """max_fragments should limit returned fragments."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "Test", "type": "company"},
            max_fragments=1,
        )

        assert len(result.fragment_ids) == 1
        assert result.fragment_ids[0] == "plastics_polymers"

    def test_resolve_entity_type_priority(self, resolver: KBResolver) -> None:
        """Fragments matching entity type should have higher priority."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "Test Product", "type": "product"},
            max_fragments=1,
        )

        assert "plastics_grades" in result.fragment_ids

    def test_resolve_keyword_matching(self, resolver: KBResolver) -> None:
        """Fragments with matching keywords should have higher priority."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "HDPE Recycler", "type": "company"},
            max_fragments=1,
        )

        assert "plastics_polymers" in result.fragment_ids

    def test_resolve_includes_entity_hints(self, resolver: KBResolver) -> None:
        """Entity hints should be included in context."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "Test", "type": "company"},
        )

        assert "typical_fields" in result.entity_hints
        assert "company_name" in result.entity_hints["typical_fields"]

    def test_resolve_includes_validation_rules(self, resolver: KBResolver) -> None:
        """Validation rules should be included in context."""
        result = resolver.resolve(
            kb_context="plastics",
            entity={"name": "Test"},
        )

        assert "polymer_type" in result.validation_rules


class TestKBResolverHelpers:
    """Tests for KBResolver helper methods."""

    def test_get_terminology(self, resolver: KBResolver) -> None:
        """get_terminology should return domain terminology."""
        terminology = resolver.get_terminology("plastics")

        assert "HDPE" in terminology
        assert terminology["HDPE"] == "High-Density Polyethylene"

    def test_get_terminology_unknown_domain(self, resolver: KBResolver) -> None:
        """get_terminology for unknown domain should return empty dict."""
        terminology = resolver.get_terminology("unknown")

        assert terminology == {}

    def test_get_validation_rules(self, resolver: KBResolver) -> None:
        """get_validation_rules should return domain rules."""
        rules = resolver.get_validation_rules("plastics")

        assert "polymer_type" in rules

    def test_get_validation_rules_unknown_domain(self, resolver: KBResolver) -> None:
        """get_validation_rules for unknown domain should return empty dict."""
        rules = resolver.get_validation_rules("unknown")

        assert rules == {}


class TestKBContextDataclass:
    """Tests for KBContext dataclass."""

    def test_default_values(self) -> None:
        """KBContext should have sensible defaults."""
        ctx = KBContext()

        assert ctx.fragment_ids == []
        assert ctx.context_text == ""
        assert ctx.domain == ""
        assert ctx.entity_hints == {}
        assert ctx.terminology == {}
        assert ctx.validation_rules == {}

    def test_with_values(self) -> None:
        """KBContext should store provided values."""
        ctx = KBContext(
            fragment_ids=["frag1", "frag2"],
            context_text="Test context",
            domain="plastics",
            entity_hints={"key": "value"},
            terminology={"HDPE": "High-Density Polyethylene"},
            validation_rules={"field": {"type": "string"}},
        )

        assert ctx.fragment_ids == ["frag1", "frag2"]
        assert ctx.context_text == "Test context"
        assert ctx.domain == "plastics"
        assert ctx.entity_hints == {"key": "value"}
        assert ctx.terminology == {"HDPE": "High-Density Polyethylene"}
        assert ctx.validation_rules == {"field": {"type": "string"}}
