"""
ZoomInfo enrichment source adapter.

Provides company and contact enrichment via the ZoomInfo API.
Maps ZoomInfo response fields to L9 canonical field names.

L9 Architecture Note:
    Chassis-agnostic. Implements BaseSource contract.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import BaseSource, EnrichmentResult

logger = logging.getLogger(__name__)


class ZoomInfoSource(BaseSource):
    """ZoomInfo enrichment source for company and contact domains."""

    async def enrich(self, domain: str, payload: dict[str, Any]) -> EnrichmentResult:
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

    async def _enrich_company(self, payload: dict[str, Any], start: int) -> EnrichmentResult:
        company_name = payload.get("company_name") or payload.get("entity_name", "")
        company_domain = payload.get("company_domain", "")

        search_body: dict[str, Any] = {}
        if company_domain:
            search_body["companyWebsite"] = company_domain
        elif company_name:
            search_body["companyName"] = company_name
        else:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="missing_identifier",
            )

        url = f"{self.config.api_endpoint}/search/company"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(url, json=search_body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("ZoomInfo company error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        records = data.get("data", [])
        if not records:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="no_results",
            )

        rec = records[0]
        mapped = {
            "company_name": rec.get("name"),
            "company_domain": rec.get("website"),
            "company_industry": rec.get("primaryIndustry"),
            "employee_count": rec.get("employeeCount"),
            "annual_revenue": rec.get("revenue"),
            "company_phone": rec.get("phone"),
            "company_location_city": rec.get("city"),
            "company_location_state": rec.get("state"),
            "company_location_country": rec.get("country"),
        }

        non_null = sum(1 for v in mapped.values() if v not in (None, ""))
        quality = non_null / len(mapped) if mapped else 0.0

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )

    async def _enrich_contact(self, payload: dict[str, Any], start: int) -> EnrichmentResult:
        email = payload.get("contact_email", "")
        search_body: dict[str, Any] = {}
        if email:
            search_body["emailAddress"] = email
        else:
            first = payload.get("contact_first_name", "")
            last = payload.get("contact_last_name", "")
            company = payload.get("company_name", "")
            if last and company:
                search_body["firstName"] = first
                search_body["lastName"] = last
                search_body["companyName"] = company
            else:
                return EnrichmentResult(
                    data={},
                    quality_score=0.0,
                    source_name=self.config.name,
                    latency_ms=self._now_ms() - start,
                    error="missing_identifier",
                )

        url = f"{self.config.api_endpoint}/search/contact"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(url, json=search_body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("ZoomInfo contact error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        records = data.get("data", [])
        if not records:
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="no_results",
            )

        rec = records[0]
        mapped = {
            "contact_first_name": rec.get("firstName"),
            "contact_last_name": rec.get("lastName"),
            "contact_title": rec.get("jobTitle"),
            "contact_email": rec.get("email"),
            "contact_phone": rec.get("directPhoneNumber"),
            "contact_mobile": rec.get("mobilePhoneNumber"),
            "contact_company_name": rec.get("companyName"),
            "contact_location_city": rec.get("city"),
            "contact_location_state": rec.get("state"),
            "contact_location_country": rec.get("country"),
        }

        non_null = sum(1 for v in mapped.values() if v not in (None, ""))
        quality = non_null / len(mapped) if mapped else 0.0

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )
