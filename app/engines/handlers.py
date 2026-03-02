"""
Chassis Handlers — register_handler("enrich", ...) bridge.

This is the ONLY file that touches the L9 chassis.
The engine never imports FastAPI, never creates routes, never touches auth.
It receives (tenant, payload), returns dict.
The chassis wraps it in the universal outbound envelope.

Handler signature (L9 contract):
    async def handle_<action>(tenant: str, payload: dict) -> dict

Registered actions:
    - enrich:    Single entity enrichment (single-pass)
    - enrichbatch: Batch enrichment
    - converge:  Multi-pass convergence loop
    - discover:  Schema discovery (Seed tier)
"""
from __future__ import annotations

from typing import Any

import structlog

from ..core.config import Settings, get_settings
from ..engines.convergence_controller import run_convergence_loop
from ..engines.enrichment_orchestrator import enrich_batch, enrich_entity
from ..engines.schema_discovery import SchemaDiscoveryEngine
from ..models.schemas import BatchEnrichRequest, EnrichRequest, EnrichResponse
from ..services.domain_yaml_reader import DomainYamlReader
from ..services.idempotency import IdempotencyStore
from ..services.kbresolver import KBResolver

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
            import yaml
            from pathlib import Path
            rules_path = Path(config.inference_rules_path)
            if rules_path.exists():
                with open(rules_path) as f:
                    inference_rules = yaml.safe_load(f) or []

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
        confidence_map={f: response.confidence for f in (response.fields or {})},
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


def get_handler_map() -> dict[str, Any]:
    """Return all handlers for chassis registration."""
    return {
        "enrich": handle_enrich,
        "enrichbatch": handle_enrichbatch,
        "converge": handle_converge,
        "discover": handle_discover,
    }
