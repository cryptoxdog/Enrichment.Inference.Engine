"""
Chassis Handlers — register_handler("enrich", ...) bridge.

This is the ONLY file that touches the L9 chassis.
The engine never imports FastAPI, never creates routes, never touches auth.
It receives (tenant, payload), returns dict.
The chassis wraps it in the universal outbound envelope.

Handler signature (L9 contract):
    async def handle_<action>(tenant: str, payload: dict) -> dict

Registered actions:
    - enrich:      Single entity enrichment (single-pass)
    - enrichbatch: Batch enrichment
    - converge:    Multi-pass convergence loop
    - discover:    Schema discovery (Seed tier)
    - simulate:    ROI simulation — ENRICH+GRAPH twin (Sonar-powered)
    - writeback:   CRM write-back (Odoo-first)
"""

from __future__ import annotations

from typing import Any

import aiofiles
import structlog

from ..core.config import get_settings
from ..engines.convergence_controller import run_convergence_loop
from ..engines.enrichment_orchestrator import enrich_batch, enrich_entity
from ..engines.schema_discovery import SchemaDiscoveryEngine
from ..models.schemas import BatchEnrichRequest, EnrichRequest
from ..services.crm.base import CRMType
from ..services.crm.writeback import WriteBackOrchestrator
from ..services.domain_yaml_reader import DomainYamlReader
from ..services.idempotency import IdempotencyStore
from ..services.kbresolver import KBResolver
from ..services.simulation_bridge import (
    analyze_leverage,
    brief_to_dict,
    generate_executive_brief,
    simulate,
)

logger = structlog.get_logger("handlers")

_kb: KBResolver | None = None
_idem: IdempotencyStore | None = None
_domain_reader: DomainYamlReader | None = None


def init_handlers(
    kb: KBResolver,
    idem: IdempotencyStore | None = None,
    domain_reader: DomainYamlReader | None = None,
) -> None:
    """Called at startup to inject dependencies."""
    global _kb, _idem, _domain_reader
    _kb = kb
    _idem = idem
    _domain_reader = domain_reader


async def handle_enrich(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Single entity enrichment — single pass."""
    settings = get_settings()
    request = EnrichRequest.model_validate(payload)
    response = await enrich_entity(request, settings, _kb, _idem)
    return response.model_dump()


async def handle_enrichbatch(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Batch enrichment — up to 50 entities."""
    settings = get_settings()
    batch_req = BatchEnrichRequest.model_validate(payload)
    results = await enrich_batch(batch_req.entities, settings, _kb, _idem)
    succeeded = sum(1 for r in results if r.state == "completed")
    failed = sum(1 for r in results if r.state == "failed")
    return {
        "results": [r.model_dump() for r in results],
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
    }


async def handle_converge(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Multi-pass convergence loop — enrichment→inference→enrichment."""
    settings = get_settings()
    request = EnrichRequest.model_validate(payload)

    domain_hints: dict[str, Any] = {}
    inference_rules: list[dict] = []

    domain_id = payload.get("domain_id")
    node_label = payload.get("node_label")
    if domain_id and node_label and _domain_reader:
        domain_hints = _domain_reader.get_enrichment_hints(domain_id, node_label)
        config = _domain_reader.load(domain_id)
        if config.inference_rules_path:
            from pathlib import Path

            import yaml

            rules_path = Path(config.inference_rules_path)
            if rules_path.exists():
                async with aiofiles.open(rules_path) as f:
                    content = await f.read()
                    inference_rules = yaml.safe_load(content) or []

    response = await run_convergence_loop(
        request=request,
        settings=settings,
        kb_resolver=_kb,
        idem_store=_idem,
        inference_rules=inference_rules,
        domain_hints=domain_hints,
    )
    return response.model_dump()


async def handle_discover(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Schema discovery — Seed tier. Returns what fields are missing."""
    settings = get_settings()
    request = EnrichRequest.model_validate(payload)

    response = await enrich_entity(request, settings, _kb, _idem)

    current_schema = payload.get("current_schema", {})
    version = payload.get("schema_version", "0.1.0-seed")

    engine = SchemaDiscoveryEngine(current_schema=current_schema, version=version)
    proposal = engine.analyze(
        enriched_fields=response.fields or {},
        inferred_fields={},
        confidence_map=dict.fromkeys(response.fields or {}, response.confidence),
    )

    return {
        "enrichment": response.model_dump(),
        "schema_proposal": {
            "current_version": proposal.current_version,
            "proposed_version": proposal.proposed_version,
            "stage": proposal.stage,
            "new_properties": [
                {
                    "name": p.name,
                    "type": p.field_type,
                    "discovered_by": p.discovered_by,
                    "confidence": p.discovery_confidence,
                }
                for p in proposal.new_properties
            ],
            "proposed_gates": proposal.proposed_gates,
        },
    }


async def handle_simulate(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    ROI simulation — ENRICH+GRAPH deterministic twin, now Sonar-powered.

    Payload keys:
        crm_field_names : list[str]   — customer's current CRM field names
        domain_id       : str         — domain YAML identifier (e.g. "plastics")
        customer_name   : str         — for executive brief attribution
        query_profile   : dict | None — optional GRAPH query override
        entity_count    : int         — number of entities to simulate (default 20)
        seed            : int         — RNG seed for static fallback (default 42)
        use_sonar       : bool        — use Sonar enrichment (default True)
        company_names   : list[str] | None — override company names for Sonar research
    """
    settings = get_settings()

    crm_field_names: list[str] = payload.get("crm_field_names", [])
    domain_id: str = payload.get("domain_id", "plastics")
    customer_name: str = payload.get("customer_name", tenant)
    query_profile: dict[str, Any] | None = payload.get("query_profile")
    entity_count: int = int(payload.get("entity_count", 20))
    seed: int = int(payload.get("seed", 42))
    use_sonar: bool = bool(payload.get("use_sonar", True))
    company_names: list[str] | None = payload.get("company_names")

    if not crm_field_names:
        raise ValueError("simulate: crm_field_names is required and must be non-empty")

    domain_spec: dict[str, Any] = {}
    if _domain_reader:
        try:
            config = _domain_reader.load(domain_id)
            domain_spec = config.raw_spec if hasattr(config, "raw_spec") else {}
        except Exception as exc:
            logger.warning(
                "simulate_domain_spec_load_failed",
                domain_id=domain_id,
                error=str(exc),
            )

    logger.info(
        "simulate_start",
        tenant=tenant,
        domain_id=domain_id,
        crm_fields=len(crm_field_names),
        entity_count=entity_count,
        use_sonar=use_sonar,
    )

    seed_stats, enriched_stats, _seed_ents, _enr_ents = simulate(
        crm_field_names=crm_field_names,
        domain_spec=domain_spec,
        query_profile=query_profile,
        entity_count=entity_count,
        seed=seed,
        use_sonar=use_sonar,
        sonar_api_key=settings.perplexity_api_key,
        company_names=company_names,
    )

    leverage_points = analyze_leverage(seed_stats, enriched_stats)
    brief = generate_executive_brief(
        customer_name=customer_name,
        domain_id=domain_id,
        seed_stats=seed_stats,
        enriched_stats=enriched_stats,
        leverage_points=leverage_points,
    )

    logger.info(
        "simulate_complete",
        tenant=tenant,
        domain_id=domain_id,
        gate_pass_rate_seed=seed_stats.gate_pass_rate,
        gate_pass_rate_enriched=enriched_stats.gate_pass_rate,
        communities=enriched_stats.communities_found,
        recommended_tier=brief.recommended_tier,
    )

    return brief_to_dict(brief)


async def handle_writeback(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    CRM write-back — push enriched data back to originating CRM.

    Payload:
        domain       : str  — entity domain (company, contact, account, opportunity)
        canonical    : dict — canonical enrichment fields to write
        crm_type     : str  — CRM platform (default: "odoo")
        credentials  : dict — CRM connection credentials
        mapping_path : str  — path to CRM field mapping YAML
    """
    settings = get_settings()
    domain = payload.get("domain", "company")
    canonical = payload.get("canonical", {})
    crm_type_str = payload.get("crm_type", "odoo")
    credentials = payload.get(
        "credentials",
        {
            "url": settings.odoo_url,
            "db": settings.odoo_db,
            "username": settings.odoo_username,
            "password": settings.odoo_password,
        },
    )
    mapping_path = payload.get("mapping_path", "config/crm/odoo_mapping.yaml")

    crm_type = CRMType(crm_type_str)
    orchestrator = WriteBackOrchestrator(
        crm_type=crm_type,
        credentials=credentials,
        mapping_path=mapping_path,
    )

    result = await orchestrator.async_write_back(domain, canonical)

    logger.info(
        "writeback_completed",
        tenant=tenant,
        domain=domain,
        crm_type=crm_type_str,
        success=result.success,
        record_id=result.record_id,
    )

    return {
        "success": result.success,
        "record_id": result.record_id,
        "fields_written": result.fields_written,
        "error": result.error,
    }


def get_handler_map() -> dict[str, Any]:
    """Return all handlers for chassis registration."""
    return {
        "enrich": handle_enrich,
        "enrichbatch": handle_enrichbatch,
        "converge": handle_converge,
        "discover": handle_discover,
        "simulate": handle_simulate,
        "writeback": handle_writeback,
    }
