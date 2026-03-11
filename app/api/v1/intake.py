"""
Intake API Handler — Wires CRM Field Scanner to HTTP endpoints.

Endpoints:
  POST /v1/scan          — Scan CRM fields, return DiscoveryReport + seed YAML
  GET  /v1/scan/report   — Retrieve cached discovery report by scan_hash

This is the Seed tier entry point (File 12's POST /v1/scan delegates here).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from ...services.crm_field_scanner import (
    CRMField,
    discovery_report_to_dict,
    generate_discovery_report,
    generate_seed_yaml,
    scan_crm_fields,
    scan_result_to_dict,
)

logger = logging.getLogger(__name__)


# ── Request / Response Models ────────────────────────────────


class CRMFieldInput(BaseModel):
    name: str
    field_type: str = "string"
    sample_values: list[Any] = Field(default_factory=list)
    fill_rate: float | None = None


class ScanRequest(BaseModel):
    crm_fields: list[CRMFieldInput]
    domain: str = Field(..., description="Domain YAML identifier (e.g., 'plastics-recycling')")
    entity_count: int = Field(
        default=1, ge=1, description="Number of CRM entities for cost estimation"
    )


class ScanResponse(BaseModel):
    scan: dict[str, Any]
    discovery_report: dict[str, Any]
    seed_yaml: dict[str, Any]


# ── Handler ──────────────────────────────────────────────────


async def handle_scan(
    request: ScanRequest,
    domain_spec: dict[str, Any],
) -> ScanResponse:
    """
    Full intake pipeline:
      1. Convert request to CRMField list
      2. Scan against domain YAML
      3. Generate discovery report
      4. Generate seed YAML
      5. Return all three
    """
    crm_fields = [
        CRMField(
            name=f.name,
            field_type=f.field_type,
            sample_values=f.sample_values,
            fill_rate=f.fill_rate,
        )
        for f in request.crm_fields
    ]

    scan_result = scan_crm_fields(crm_fields, domain_spec)
    report = generate_discovery_report(scan_result, domain_spec, request.entity_count)
    seed = generate_seed_yaml(scan_result, domain_spec)

    logger.info(
        "intake_scan_complete",
        extra={
            "domain": request.domain,
            "crm_fields": len(crm_fields),
            "coverage": scan_result.coverage_ratio,
            "missing": scan_result.missing_count,
            "gate_blocked": report.gate_blocked_count,
        },
    )

    return ScanResponse(
        scan=scan_result_to_dict(scan_result),
        discovery_report=discovery_report_to_dict(report),
        seed_yaml=seed,
    )
