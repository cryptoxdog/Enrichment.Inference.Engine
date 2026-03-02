"""
Schema Discovery — Proposes new fields + schema version evolution.

After convergence, analyzes what was discovered vs. what the original
schema defined, and produces PropertySpec proposals for schema evolution.

Aligned with L9 Contract Specifications domain spec versioning:
  0.1.0-seed → 0.2.0-discovered → 0.3.0-inferred → 0.4.0-proposed

Output is a SchemaProposal that can be:
  - Written back to Odoo as a schema evolution record
  - Emitted as PacketEnvelope(packettype="schema_proposal")
  - Fed to the graph engine's DomainPackLoader for next sync
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PropertySpec:
    """A proposed field addition to the domain schema."""
    name: str
    field_type: str  # "string" | "float" | "integer" | "boolean" | "enum" | "list"
    discovered_by: str  # "enrichment" | "inference"
    discovery_confidence: float
    managed_by: str = "enrichment"  # or "computed" for inferred
    derived_from: list[str] = field(default_factory=list)
    sample_values: list[Any] = field(default_factory=list)
    fill_rate: float = 0.0  # across batch: % of entities that have this field
    auto_proposed: bool = True


@dataclass
class SchemaProposal:
    """Proposed schema evolution from a convergence run."""
    current_version: str
    proposed_version: str
    stage: str  # "discovered" | "inferred" | "proposed"
    new_properties: list[PropertySpec] = field(default_factory=list)
    proposed_gates: list[dict] = field(default_factory=list)
    proposed_scoring: list[dict] = field(default_factory=list)
    entity_count: int = 0
    fill_rate_threshold: float = 0.75


class SchemaDiscoveryEngine:
    """
    Analyzes convergence results to propose schema evolution.
    """

    def __init__(self, current_schema: dict[str, str] | None = None, version: str = "0.1.0-seed"):
        self._current = current_schema or {}
        self._version = version

    def analyze(
        self,
        enriched_fields: dict[str, Any],
        inferred_fields: dict[str, Any],
        confidence_map: dict[str, float],
        batch_stats: dict[str, float] | None = None,
    ) -> SchemaProposal:
        """
        Compare enriched+inferred fields against current schema.
        Propose new fields that don't exist in the current schema.
        """
        fill_rates = batch_stats or {}
        new_props: list[PropertySpec] = []

        # Enrichment-discovered fields
        for fname, value in enriched_fields.items():
            if fname not in self._current:
                new_props.append(PropertySpec(
                    name=fname,
                    field_type=self._infer_type(value),
                    discovered_by="enrichment",
                    discovery_confidence=confidence_map.get(fname, 0.5),
                    managed_by="enrichment",
                    sample_values=[value] if value is not None else [],
                    fill_rate=fill_rates.get(fname, 0.0),
                ))

        # Inference-derived fields
        for fname, value in inferred_fields.items():
            if fname not in self._current:
                new_props.append(PropertySpec(
                    name=fname,
                    field_type=self._infer_type(value),
                    discovered_by="inference",
                    discovery_confidence=confidence_map.get(fname, 0.7),
                    managed_by="computed",
                    derived_from=self._find_dependencies(fname),
                    sample_values=[value] if value is not None else [],
                    fill_rate=fill_rates.get(fname, 0.0),
                ))

        # Propose gates for high-fill-rate fields
        proposed_gates = []
        for prop in new_props:
            if prop.fill_rate >= self.GATE_THRESHOLD and prop.field_type in ("float", "integer", "boolean"):
                proposed_gates.append({
                    "field": prop.name,
                    "gate_type": "boolean" if prop.field_type == "boolean" else "range",
                    "confidence": prop.discovery_confidence,
                })

        stage = "inferred" if any(p.discovered_by == "inference" for p in new_props) else "discovered"
        proposed_version = self._bump_version(stage)

        return SchemaProposal(
            current_version=self._version,
            proposed_version=proposed_version,
            stage=stage,
            new_properties=new_props,
            proposed_gates=proposed_gates,
            entity_count=1,
            fill_rate_threshold=self.GATE_THRESHOLD,
        )

    GATE_THRESHOLD = 0.75

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "float"
        if isinstance(value, list):
            return "list"
        return "string"

    def _find_dependencies(self, field_name: str) -> list[str]:
        """Placeholder — in production, traced from InferenceBridge rule_trace."""
        return []

    def _bump_version(self, stage: str) -> str:
        parts = self._version.split("-")[0].split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        return f"{major}.{minor + 1}.{patch}-{stage}"
