"""Business logic services: Perplexity client, validation, consensus, KB resolver."""

from .crm_field_scanner import (
    CRMField,
    DiscoveryReport,
    DiscoveryReportEntry,
    DomainProperty,
    FieldMapping,
    FieldMatchStatus,
    ImpactTier,
    ScanResult,
    discovery_report_to_dict,
    generate_discovery_report,
    generate_seed_yaml,
    scan_crm_fields,
    scan_result_to_dict,
)
from .enrichment_profile import (
    DEFAULT_PROFILES,
    EnrichmentProfile,
    EntityBudget,
    EntityRef,
    EntityStore,
    ProfileRegistry,
    SelectionCriteria,
    SelectionMode,
    allocate_budget,
    select_entities,
)

__all__ = [
    # crm_field_scanner.py
    "FieldMatchStatus",
    "ImpactTier",
    "CRMField",
    "DomainProperty",
    "FieldMapping",
    "ScanResult",
    "DiscoveryReportEntry",
    "DiscoveryReport",
    "scan_crm_fields",
    "generate_seed_yaml",
    "generate_discovery_report",
    "scan_result_to_dict",
    "discovery_report_to_dict",
    # enrichment_profile.py
    "SelectionMode",
    "SelectionCriteria",
    "EnrichmentProfile",
    "EntityRef",
    "EntityBudget",
    "EntityStore",
    "select_entities",
    "allocate_budget",
    "DEFAULT_PROFILES",
    "ProfileRegistry",
]
