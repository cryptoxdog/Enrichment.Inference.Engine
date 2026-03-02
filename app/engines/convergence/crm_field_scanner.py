"""CRM field scanner — Seed tier trojan horse.

Day 0: customer connects CRM. The scanner reads their field schema,
maps it against the domain ontology, and generates the discovery report
that converts free → $500/mo.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FieldImpact(str, Enum):
    GATE_CRITICAL = "gate_critical"
    SCORING_DIMENSION = "scoring_dimension"
    ENRICHMENT_TARGET = "enrichment_target"
    NICE_TO_HAVE = "nice_to_have"


class CRMField(BaseModel):
    name: str
    type: str = "string"
    sample_values: list[Any] = Field(default_factory=list)
    fill_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class MappedField(BaseModel):
    crm_field: str
    domain_property: str
    type_match: bool = True
    fill_rate: float = 0.0


class MissingField(BaseModel):
    domain_property: str
    expected_type: str = "string"
    impact: FieldImpact = FieldImpact.ENRICHMENT_TARGET
    impact_reason: str = ""
    enrichment_cost_estimate: str = "low"


class UnmappedField(BaseModel):
    crm_field: str
    crm_type: str = "string"
    sample_values: list[Any] = Field(default_factory=list)
    potential_domain_mapping: str = ""


class ScanResult(BaseModel):
    domain: str = ""
    crm_field_count: int = 0
    domain_property_count: int = 0
    matched: list[MappedField] = Field(default_factory=list)
    unmapped: list[UnmappedField] = Field(default_factory=list)
    missing: list[MissingField] = Field(default_factory=list)
    coverage_pct: float = 0.0
    gate_coverage_pct: float = 0.0


class DiscoveryReport(BaseModel):
    scan_result: ScanResult
    headline: str = ""
    fields_you_have: int = 0
    fields_you_need: int = 0
    fields_missing: int = 0
    top_impact_missing: list[MissingField] = Field(default_factory=list)
    estimated_enrichment_passes: int = 1
    recommended_tier: str = "enrich"


def _extract_ontology_properties(domain_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract all node properties from the domain YAML ontology."""
    properties: dict[str, dict[str, Any]] = {}
    ontology = domain_spec.get("ontology", {})
    nodes = ontology.get("nodes", ontology.get("entities", {}))
    if isinstance(nodes, dict):
        for _node_type, node_def in nodes.items():
            node_props = node_def.get("properties", {})
            if isinstance(node_props, dict):
                for prop_name, prop_def in node_props.items():
                    if isinstance(prop_def, dict):
                        properties[prop_name] = prop_def
                    else:
                        properties[prop_name] = {"type": str(prop_def)}
    elif isinstance(nodes, list):
        for node_def in nodes:
            if isinstance(node_def, dict):
                node_props = node_def.get("properties", {})
                if isinstance(node_props, dict):
                    for prop_name, prop_def in node_props.items():
                        if isinstance(prop_def, dict):
                            properties[prop_name] = prop_def
                        else:
                            properties[prop_name] = {"type": str(prop_def)}
    return properties


def _extract_gate_fields(domain_spec: dict[str, Any]) -> set[str]:
    """Extract field names used in WHERE gates."""
    gate_fields: set[str] = set()
    gates = domain_spec.get("gates", domain_spec.get("where_gates", []))
    if isinstance(gates, list):
        for gate in gates:
            if isinstance(gate, dict):
                for key in ("field", "attribute", "property"):
                    val = gate.get(key)
                    if val:
                        gate_fields.add(str(val))
    elif isinstance(gates, dict):
        for _gate_name, gate_def in gates.items():
            if isinstance(gate_def, dict):
                for key in ("field", "attribute", "property"):
                    val = gate_def.get(key)
                    if val:
                        gate_fields.add(str(val))
    return gate_fields


def _extract_scoring_fields(domain_spec: dict[str, Any]) -> set[str]:
    """Extract field names used in scoring dimensions."""
    scoring_fields: set[str] = set()
    scoring = domain_spec.get("scoring", domain_spec.get("scoring_dimensions", []))
    if isinstance(scoring, list):
        for dim in scoring:
            if isinstance(dim, dict):
                for key in ("field", "attribute", "property", "source_field"):
                    val = dim.get(key)
                    if val:
                        scoring_fields.add(str(val))
    elif isinstance(scoring, dict):
        for _dim_name, dim_def in scoring.items():
            if isinstance(dim_def, dict):
                for key in ("field", "attribute", "property", "source_field"):
                    val = dim_def.get(key)
                    if val:
                        scoring_fields.add(str(val))
    return scoring_fields


def _normalise_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def scan_crm_fields(
    fields: list[CRMField],
    domain_spec: dict[str, Any],
) -> ScanResult:
    """Map CRM fields against the domain ontology."""
    domain_name = domain_spec.get("domain", domain_spec.get("metadata", {}).get("domain", "unknown"))
    ontology_props = _extract_ontology_properties(domain_spec)
    gate_fields = _extract_gate_fields(domain_spec)
    scoring_fields = _extract_scoring_fields(domain_spec)

    crm_by_norm: dict[str, CRMField] = {_normalise_name(f.name): f for f in fields}
    domain_by_norm: dict[str, str] = {_normalise_name(k): k for k in ontology_props}

    matched: list[MappedField] = []
    unmapped: list[UnmappedField] = []
    matched_domain_keys: set[str] = set()

    for norm_crm, crm_field in crm_by_norm.items():
        if norm_crm in domain_by_norm:
            orig_domain = domain_by_norm[norm_crm]
            domain_def = ontology_props[orig_domain]
            expected_type = domain_def.get("type", "string")
            type_match = _types_compatible(crm_field.type, expected_type)
            matched.append(MappedField(
                crm_field=crm_field.name,
                domain_property=orig_domain,
                type_match=type_match,
                fill_rate=crm_field.fill_rate,
            ))
            matched_domain_keys.add(norm_crm)
        else:
            unmapped.append(UnmappedField(
                crm_field=crm_field.name,
                crm_type=crm_field.type,
                sample_values=crm_field.sample_values[:5],
            ))

    missing: list[MissingField] = []
    for norm_domain, orig_domain in domain_by_norm.items():
        if norm_domain not in matched_domain_keys:
            domain_def = ontology_props[orig_domain]
            expected_type = domain_def.get("type", "string")
            impact = _classify_impact(orig_domain, gate_fields, scoring_fields)
            reason = _impact_reason(orig_domain, impact)
            missing.append(MissingField(
                domain_property=orig_domain,
                expected_type=expected_type,
                impact=impact,
                impact_reason=reason,
                enrichment_cost_estimate=_cost_estimate(impact),
            ))

    missing.sort(key=lambda m: _impact_sort_key(m.impact))

    total_domain = len(ontology_props)
    coverage = len(matched) / total_domain if total_domain > 0 else 0.0
    gate_matched = sum(1 for m in matched if _normalise_name(m.domain_property) in {_normalise_name(g) for g in gate_fields})
    gate_total = len(gate_fields)
    gate_cov = gate_matched / gate_total if gate_total > 0 else 1.0

    return ScanResult(
        domain=domain_name,
        crm_field_count=len(fields),
        domain_property_count=total_domain,
        matched=matched,
        unmapped=unmapped,
        missing=missing,
        coverage_pct=round(coverage * 100, 1),
        gate_coverage_pct=round(gate_cov * 100, 1),
    )


def _types_compatible(crm_type: str, domain_type: str) -> bool:
    crm_norm = crm_type.strip().lower()
    dom_norm = domain_type.strip().lower()
    if crm_norm == dom_norm:
        return True
    compat_map: dict[str, set[str]] = {
        "string": {"text", "varchar", "char", "str"},
        "float": {"number", "decimal", "double", "numeric", "real"},
        "integer": {"int", "number", "bigint"},
        "boolean": {"bool", "checkbox"},
        "list": {"array", "multi_select", "multiselect"},
    }
    for canonical, aliases in compat_map.items():
        group = aliases | {canonical}
        if crm_norm in group and dom_norm in group:
            return True
    return False


def _classify_impact(field: str, gate_fields: set[str], scoring_fields: set[str]) -> FieldImpact:
    norm = _normalise_name(field)
    if norm in {_normalise_name(g) for g in gate_fields}:
        return FieldImpact.GATE_CRITICAL
    if norm in {_normalise_name(s) for s in scoring_fields}:
        return FieldImpact.SCORING_DIMENSION
    return FieldImpact.ENRICHMENT_TARGET


def _impact_reason(field: str, impact: FieldImpact) -> str:
    if impact is FieldImpact.GATE_CRITICAL:
        return f"'{field}' is used in a WHERE gate — without it, entities cannot pass matching filters"
    if impact is FieldImpact.SCORING_DIMENSION:
        return f"'{field}' is a scoring dimension — without it, match quality scores are incomplete"
    return f"'{field}' enriches the entity profile for deeper analysis"


def _cost_estimate(impact: FieldImpact) -> str:
    return {"gate_critical": "high", "scoring_dimension": "medium", "enrichment_target": "low", "nice_to_have": "low"}[impact.value]


def _impact_sort_key(impact: FieldImpact) -> int:
    return {FieldImpact.GATE_CRITICAL: 0, FieldImpact.SCORING_DIMENSION: 1, FieldImpact.ENRICHMENT_TARGET: 2, FieldImpact.NICE_TO_HAVE: 3}[impact]


def generate_seed_yaml(scan_result: ScanResult, domain_template: dict[str, Any]) -> str:
    """Produce a v0.1.0-seed domain YAML containing only the customer's current fields."""
    seed = dict(domain_template)
    seed["version"] = "0.1.0-seed"
    seed["metadata"] = seed.get("metadata", {})
    seed["metadata"]["generated_by"] = "crm_field_scanner"
    seed["metadata"]["source_fields"] = len(scan_result.matched)

    matched_props = {m.domain_property for m in scan_result.matched}
    ontology = seed.get("ontology", {})
    nodes = ontology.get("nodes", ontology.get("entities", {}))
    if isinstance(nodes, dict):
        for _node_type, node_def in nodes.items():
            if isinstance(node_def, dict) and "properties" in node_def:
                node_def["properties"] = {
                    k: v for k, v in node_def["properties"].items() if k in matched_props
                }

    return yaml.dump(seed, default_flow_style=False, sort_keys=False, allow_unicode=True)


def generate_discovery_report(scan_result: ScanResult) -> DiscoveryReport:
    """Build the sales conversion document."""
    gate_missing = [m for m in scan_result.missing if m.impact is FieldImpact.GATE_CRITICAL]
    scoring_missing = [m for m in scan_result.missing if m.impact is FieldImpact.SCORING_DIMENSION]
    top_impact = gate_missing + scoring_missing
    top_impact = top_impact[:10]

    total_missing = len(scan_result.missing)
    passes = 1
    if total_missing > 15:
        passes = 3
    elif total_missing > 8:
        passes = 2

    tier = "enrich"
    if total_missing > 15 and len(gate_missing) > 3:
        tier = "discover"
    elif total_missing > 25:
        tier = "autonomous"

    headline = (
        f"You have {len(scan_result.matched)} of {scan_result.domain_property_count} domain fields. "
        f"{total_missing} are missing — {len(gate_missing)} are gate-critical."
    )

    return DiscoveryReport(
        scan_result=scan_result,
        headline=headline,
        fields_you_have=len(scan_result.matched),
        fields_you_need=scan_result.domain_property_count,
        fields_missing=total_missing,
        top_impact_missing=top_impact,
        estimated_enrichment_passes=passes,
        recommended_tier=tier,
    )
