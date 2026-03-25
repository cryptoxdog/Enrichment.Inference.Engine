"""
Clearbit enrichment source adapter.

Provides company and contact enrichment via the Clearbit Enrichment API.
Maps Clearbit response fields to L9 canonical field names.

L9 Architecture Note:
    Chassis-agnostic. Implements BaseSource contract.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import BaseSource, EnrichmentResult, SourceConfig

logger = logging.getLogger(__name__)


class ClearbitSource(BaseSource):
    """Clearbit enrichment source for company and contact domains."""

    async def enrich(
        self, domain: str, payload: dict[str, Any]
    ) -> EnrichmentResult:
        start = self._now_ms()

        if not self.config.enabled:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="source_disabled",
            )

        if not self.config.api_key:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="missing_api_key",
            )

        if domain == "company":
            return await self._enrich_company(payload, start)
        if domain == "contact":
            return await self._enrich_contact(payload, start)

        return EnrichmentResult(
            data={},
            quality_score=0.0,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
            error="unsupported_domain",
        )

    async def _enrich_company(
        self, payload: dict[str, Any], start: int
    ) -> EnrichmentResult:
        company_domain = payload.get("company_domain", "")
        if not company_domain:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="missing_company_domain",
            )

        url = f"{self.config.api_endpoint}/v2/companies/find"
        params = {"domain": company_domain}
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout
            ) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Clearbit company error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        mapped = self._map_company(data)
        non_null = sum(1 for v in mapped.values() if v not in (None, ""))
        quality = non_null / len(mapped) if mapped else 0.0

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )

    async def _enrich_contact(
        self, payload: dict[str, Any], start: int
    ) -> EnrichmentResult:
        email = payload.get("contact_email", "")
        if not email:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="missing_contact_email",
            )

        url = f"{self.config.api_endpoint}/v2/people/find"
        params = {"email": email}
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout
            ) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Clearbit contact error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        mapped = self._map_contact(data)
        non_null = sum(1 for v in mapped.values() if v not in (None, ""))
        quality = non_null / len(mapped) if mapped else 0.0

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )

    @staticmethod
    def _map_company(raw: dict[str, Any]) -> dict[str, Any]:
        """Map Clearbit company response to L9 canonical fields."""
        return {
            "company_name": raw.get("name"),
            "company_domain": raw.get("domain"),
            "company_industry": raw.get("category", {}).get("industry"),
            "company_description": raw.get("description"),
            "employee_count": raw.get("metrics", {}).get("employees"),
            "annual_revenue": raw.get("metrics", {}).get("estimatedAnnualRevenue"),
            "company_location_city": raw.get("geo", {}).get("city"),
            "company_location_state": raw.get("geo", {}).get("state"),
            "company_location_country": raw.get("geo", {}).get("country"),
            "company_linkedin_url": raw.get("linkedin", {}).get("handle"),
            "company_phone": raw.get("phone"),
            "company_founded_year": raw.get("foundedYear"),
            "company_tech_stack": raw.get("tech", []),
        }

    @staticmethod
    def _map_contact(raw: dict[str, Any]) -> dict[str, Any]:
        """Map Clearbit person response to L9 canonical fields."""
        return {
            "contact_first_name": raw.get("name", {}).get("givenName"),
            "contact_last_name": raw.get("name", {}).get("familyName"),
            "contact_title": raw.get("employment", {}).get("title"),
            "contact_company_name": raw.get("employment", {}).get("name"),
            "contact_linkedin_url": raw.get("linkedin", {}).get("handle"),
            "contact_location_city": raw.get("geo", {}).get("city"),
            "contact_location_state": raw.get("geo", {}).get("state"),
            "contact_location_country": raw.get("geo", {}).get("country"),
        }
