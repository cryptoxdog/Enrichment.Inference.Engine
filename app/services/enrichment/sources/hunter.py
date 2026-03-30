"""
Hunter.io enrichment source adapter.

Provides contact email verification and discovery via the Hunter.io API.
Maps Hunter response fields to L9 canonical field names.

L9 Architecture Note:
    Chassis-agnostic. Implements BaseSource contract.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import BaseSource, EnrichmentResult

logger = logging.getLogger(__name__)


class HunterSource(BaseSource):
    """Hunter.io enrichment source for contact email verification."""

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

        if domain != "contact":
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="unsupported_domain",
            )

        email = payload.get("contact_email", "")
        first_name = payload.get("contact_first_name", "")
        last_name = payload.get("contact_last_name", "")
        company_domain = payload.get("company_domain", "")

        if email:
            return await self._verify_email(email, start)
        if first_name and last_name and company_domain:
            return await self._find_email(first_name, last_name, company_domain, start)

        return EnrichmentResult(
            data={},
            quality_score=0.0,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
            error="missing_identifier",
        )

    async def _verify_email(self, email: str, start: int) -> EnrichmentResult:
        """Verify an email address via Hunter email-verifier."""
        url = f"{self.config.api_endpoint}/v2/email-verifier"
        params = {"email": email, "api_key": self.config.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json().get("data", {})
        except Exception as exc:
            logger.warning("Hunter verify error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        status = data.get("status", "unknown")
        score = data.get("score", 0)
        quality = score / 100.0 if score else 0.0

        mapped = {
            "contact_email": email,
            "contact_email_valid": status == "valid",
            "contact_email_status": status,
            "contact_email_score": score,
            "contact_first_name": data.get("first_name"),
            "contact_last_name": data.get("last_name"),
        }

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )

    async def _find_email(
        self,
        first_name: str,
        last_name: str,
        company_domain: str,
        start: int,
    ) -> EnrichmentResult:
        """Find an email address via Hunter email-finder."""
        url = f"{self.config.api_endpoint}/v2/email-finder"
        params = {
            "domain": company_domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": self.config.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json().get("data", {})
        except Exception as exc:
            logger.warning("Hunter finder error: %s", exc)
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=self.config.name,
                latency_ms=self._now_ms() - start,
                error="network_error",
            )

        email = data.get("email", "")
        score = data.get("score", 0)
        quality = score / 100.0 if score else 0.0

        mapped = {
            "contact_email": email,
            "contact_email_score": score,
            "contact_first_name": data.get("first_name") or first_name,
            "contact_last_name": data.get("last_name") or last_name,
        }

        return EnrichmentResult(
            data={k: v for k, v in mapped.items() if v not in (None, "")},
            quality_score=quality,
            source_name=self.config.name,
            latency_ms=self._now_ms() - start,
        )
