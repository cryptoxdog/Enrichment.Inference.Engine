"""
Knowledge Base resolver for enrichment context injection.

Loads and resolves domain-specific knowledge base fragments to provide
context for enrichment prompts. Supports YAML and JSON KB files.

L9 Architecture Note:
    This module is chassis-agnostic. It never imports FastAPI.
    It is called by WaterfallEngine and prompt builders for context injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


@dataclass
class KBContext:
    """Resolved knowledge base context for enrichment."""

    fragment_ids: list[str] = field(default_factory=list)
    context_text: str = ""
    domain: str = ""
    entity_hints: dict[str, Any] = field(default_factory=dict)
    terminology: dict[str, str] = field(default_factory=dict)
    validation_rules: dict[str, Any] = field(default_factory=dict)


@dataclass
class KBFragment:
    """A single knowledge base fragment."""

    id: str
    domain: str
    content: str
    keywords: list[str] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    priority: int = 0


class KBResolver:
    """
    Resolves knowledge base context for enrichment prompts.

    Loads KB fragments from YAML/JSON files and selects relevant
    fragments based on domain and entity characteristics.
    """

    def __init__(self, kb_dir: str = "config/kb") -> None:
        """
        Initialize the KB resolver.

        Args:
            kb_dir: Directory containing KB YAML/JSON files
        """
        self.kb_dir = Path(kb_dir)
        self._cache: dict[str, dict[str, Any]] = {}
        self._fragments: dict[str, list[KBFragment]] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all KB files from the configured directory."""
        if not self.kb_dir.exists():
            logger.warning("kb_dir_not_found", path=str(self.kb_dir))
            self._loaded = True
            return

        for kb_file in self.kb_dir.glob("*.yaml"):
            self._load_kb_file(kb_file)

        for kb_file in self.kb_dir.glob("*.yml"):
            self._load_kb_file(kb_file)

        for kb_file in self.kb_dir.glob("*.json"):
            self._load_kb_file(kb_file)

        self._loaded = True
        logger.info(
            "kb_loaded",
            domains=list(self._cache.keys()),
            total_fragments=sum(len(f) for f in self._fragments.values()),
        )

    def _load_kb_file(self, path: Path) -> None:
        """Load a single KB file."""
        try:
            with open(path) as f:
                if path.suffix == ".json":
                    import json

                    data = json.load(f)
                else:
                    data = yaml.safe_load(f) or {}

            domain = data.get("domain", path.stem)
            self._cache[domain] = data

            fragments = data.get("fragments", [])
            self._fragments[domain] = [
                KBFragment(
                    id=frag.get("id", f"{domain}_{i}"),
                    domain=domain,
                    content=frag.get("content", ""),
                    keywords=frag.get("keywords", []),
                    entity_types=frag.get("entity_types", []),
                    priority=frag.get("priority", 0),
                )
                for i, frag in enumerate(fragments)
            ]

            logger.debug(
                "kb_file_loaded",
                path=str(path),
                domain=domain,
                fragments=len(fragments),
            )

        except Exception as exc:
            logger.error("kb_file_load_error", path=str(path), error=str(exc))

    def resolve(
        self,
        kb_context: str | None,
        entity: dict[str, Any],
        max_fragments: int = 5,
    ) -> KBContext:
        """
        Resolve KB context for an entity.

        Selects relevant KB fragments based on domain and entity characteristics.

        Args:
            kb_context: KB identifier (e.g., "plastics", "saas") or None
            entity: Entity dict with name, type, domain, etc.
            max_fragments: Maximum number of fragments to include

        Returns:
            KBContext with relevant fragments, terminology, and hints
        """
        if not self._loaded:
            self.load()

        domain = kb_context or entity.get("domain", "")
        if not domain:
            return KBContext()

        kb_data = self._cache.get(domain, {})
        if not kb_data:
            logger.debug("kb_domain_not_found", domain=domain)
            return KBContext(domain=domain)

        fragments = self._select_fragments(domain, entity, max_fragments)

        context_text = self._build_context_text(fragments, kb_data)

        entity_hints = self._extract_entity_hints(kb_data, entity)

        terminology = kb_data.get("terminology", {})
        validation_rules = kb_data.get("validation_rules", {})

        logger.info(
            "kb_resolved",
            domain=domain,
            fragments_selected=len(fragments),
            hints_count=len(entity_hints),
        )

        return KBContext(
            fragment_ids=[f.id for f in fragments],
            context_text=context_text,
            domain=domain,
            entity_hints=entity_hints,
            terminology=terminology,
            validation_rules=validation_rules,
        )

    def _select_fragments(
        self,
        domain: str,
        entity: dict[str, Any],
        max_fragments: int,
    ) -> list[KBFragment]:
        """Select relevant fragments for an entity."""
        domain_fragments = self._fragments.get(domain, [])
        if not domain_fragments:
            return []

        entity_type = entity.get("type", entity.get("entity_type", ""))
        entity_name = str(entity.get("name", entity.get("entity_name", ""))).lower()

        scored: list[tuple[int, KBFragment]] = []

        for frag in domain_fragments:
            score = frag.priority

            if entity_type and entity_type in frag.entity_types:
                score += 10

            for keyword in frag.keywords:
                if keyword.lower() in entity_name:
                    score += 5

            scored.append((score, frag))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [frag for _, frag in scored[:max_fragments]]

    def _build_context_text(
        self,
        fragments: list[KBFragment],
        kb_data: dict[str, Any],
    ) -> str:
        """Build context text from fragments and KB data."""
        parts: list[str] = []

        preamble = kb_data.get("preamble", "")
        if preamble:
            parts.append(preamble)

        for frag in fragments:
            if frag.content:
                parts.append(frag.content)

        return "\n\n".join(parts)

    def _extract_entity_hints(
        self,
        kb_data: dict[str, Any],
        entity: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract entity-specific hints from KB data."""
        hints: dict[str, Any] = {}

        entity_type = entity.get("type", entity.get("entity_type", ""))
        type_hints = kb_data.get("entity_hints", {}).get(entity_type, {})
        hints.update(type_hints)

        default_hints = kb_data.get("default_hints", {})
        for key, value in default_hints.items():
            if key not in hints:
                hints[key] = value

        return hints

    def get_terminology(self, domain: str) -> dict[str, str]:
        """Get terminology dictionary for a domain."""
        if not self._loaded:
            self.load()

        kb_data = self._cache.get(domain, {})
        return dict(kb_data.get("terminology", {}))

    def get_validation_rules(self, domain: str) -> dict[str, Any]:
        """Get validation rules for a domain."""
        if not self._loaded:
            self.load()

        kb_data = self._cache.get(domain, {})
        return dict(kb_data.get("validation_rules", {}))

    @property
    def is_loaded(self) -> bool:
        """Check if KB has been loaded."""
        return self._loaded

    @property
    def domains(self) -> list[str]:
        """Get list of loaded domains."""
        return list(self._cache.keys())
