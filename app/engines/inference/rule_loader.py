"""Domain-agnostic inference rule loader with hot-reload and O(1) trigger index."""

from __future__ import annotations

import enum
import logging
import threading
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class Operator(str, enum.Enum):
    CONTAINS = "CONTAINS"
    EQUALS = "EQUALS"
    GT = "GT"
    LT = "LT"
    GTE = "GTE"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_TRUE = "IS_TRUE"
    IS_FALSE = "IS_FALSE"
    EXISTS = "EXISTS"


class RuleCondition(BaseModel):
    field: str
    operator: Operator
    value: Any = None

    @field_validator("operator", mode="before")
    @classmethod
    def _normalise_operator(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.upper().replace(" ", "_")
        return v


class RuleOutput(BaseModel):
    field: str
    value_expr: Any
    derivation_type: str = "classification"
    confidence_override: float | None = None


class RuleDefinition(BaseModel):
    rule_id: str
    conditions: list[RuleCondition] = Field(min_length=1)
    outputs: list[RuleOutput] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.80)
    priority: int = Field(ge=0, default=0)
    domain: str = ""
    description: str = ""

    @property
    def trigger_fields(self) -> frozenset[str]:
        return frozenset(c.field for c in self.conditions)


class RuleRegistry:
    """Indexed rule store with O(1) candidate lookup by trigger field."""

    __slots__ = ("_rules", "_by_trigger", "_version")

    def __init__(self, rules: Sequence[RuleDefinition] | None = None) -> None:
        self._rules: list[RuleDefinition] = []
        self._by_trigger: dict[str, list[RuleDefinition]] = {}
        self._version: int = 0
        if rules:
            self._index(list(rules))

    def _index(self, rules: list[RuleDefinition]) -> None:
        self._rules = sorted(rules, key=lambda r: (-r.priority, -r.confidence))
        by_trigger: dict[str, list[RuleDefinition]] = {}
        for rule in self._rules:
            for field in rule.trigger_fields:
                by_trigger.setdefault(field, []).append(rule)
        self._by_trigger = by_trigger
        self._version += 1

    @property
    def version(self) -> int:
        return self._version

    @property
    def rules(self) -> list[RuleDefinition]:
        return list(self._rules)

    def candidates_for(self, available_fields: set[str]) -> list[RuleDefinition]:
        seen: set[str] = set()
        result: list[RuleDefinition] = []
        for field in available_fields:
            for rule in self._by_trigger.get(field, []):
                if rule.rule_id not in seen:
                    seen.add(rule.rule_id)
                    result.append(rule)
        return sorted(result, key=lambda r: (-r.priority, -r.confidence))

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"RuleRegistry(rules={len(self._rules)}, triggers={len(self._by_trigger)}, v={self._version})"


def _parse_rules(raw_rules: list[dict[str, Any]], domain: str) -> list[RuleDefinition]:
    parsed: list[RuleDefinition] = []
    for idx, entry in enumerate(raw_rules):
        entry.setdefault("domain", domain)
        entry.setdefault("rule_id", f"{domain}-auto-{idx}")
        try:
            parsed.append(RuleDefinition.model_validate(entry))
        except Exception as exc:
            raise ValueError(f"Rule #{idx} ({entry.get('rule_id', '?')}): {exc}") from exc
    return parsed


def load_rules(domain_yaml_path: str | Path) -> RuleRegistry:
    path = Path(domain_yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Domain YAML not found: {path}")
    with open(path, encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)
    if not isinstance(spec, dict):
        raise ValueError(f"Expected dict at top level, got {type(spec).__name__}")
    raw_rules = spec.get("inference_rules", [])
    if not raw_rules:
        logger.warning("No inference_rules in %s", path.name)
        return RuleRegistry()
    domain = spec.get("domain", spec.get("metadata", {}).get("domain", path.stem))
    return RuleRegistry(_parse_rules(raw_rules, domain))


class HotReloadableRegistry:
    """Thread-safe wrapper that supports atomic hot-reload."""

    def __init__(self, domain_yaml_path: str | Path) -> None:
        self._path = Path(domain_yaml_path)
        self._lock = threading.Lock()
        self._registry = load_rules(self._path)
        logger.info(
            "rule_loader.init: loaded %d rules from %s", len(self._registry), self._path.name
        )

    @property
    def registry(self) -> RuleRegistry:
        return self._registry

    def reload(self) -> RuleRegistry:
        new_registry = load_rules(self._path)
        with self._lock:
            self._registry = new_registry
        logger.info("rule_loader.reload: %d rules, v=%d", len(new_registry), new_registry.version)
        return new_registry
