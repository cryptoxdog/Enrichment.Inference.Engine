"""
End-to-end test: Odoo → Enrichment API → verify response structure.
Run with: pytest tests/test_e2e_odoo.py -v
Requires: enrichment-api running on localhost:8000
"""
import os
import requests
import pytest

API_URL = os.getenv("ENRICHMENT_API_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("ENRICHMENT_CLIENT_KEY", "test-key")


class TestEnrichmentE2E:
    """Simulate what the Odoo module sends."""

    def test_health(self):
        resp = requests.get(f"{API_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_enrich_single_lead(self):
        """Simulate a CRM lead enrichment request."""
        payload = {
            "entity": {
                "name": "Acme Corp Partnership",
                "partner_name": "Acme Corporation",
                "contact_name": "John Smith",
                "email_from": "john@acme.com",
            },
            "object_type": "Lead",
            "objective": (
                "Research this CRM lead. Find the company website, phone, "
                "key contact role, address, and expected revenue."
            ),
            "schema": {
                "website": "string",
                "phone": "string",
                "city": "string",
                "function": "string",
            },
        }

        resp = requests.post(
            f"{API_URL}/enrich",
            json=payload,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify response structure matches what Odoo module expects
        assert "state" in data
        assert data["state"] in ("completed", "failed")
        assert "confidence" in data
        assert "fields" in data

        if data["state"] == "completed":
            assert isinstance(data["fields"], dict)
            assert data["confidence"] > 0
            assert "variation_count" in data

    def test_enrich_batch(self):
        """Simulate the cron batch enrichment."""
        payload = {
            "entities": [
                {
                    "entity": {"partner_name": "Tesla Inc", "email_from": "info@tesla.com"},
                    "object_type": "Lead",
                    "objective": "Research this company.",
                    "max_variations": 2,
                },
                {
                    "entity": {"partner_name": "Unknown Startup XYZ"},
                    "object_type": "Lead",
                    "objective": "Research this company.",
                    "max_variations": 2,
                },
            ]
        }

        resp = requests.post(
            f"{API_URL}/enrich/batch",
            json=payload,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=300,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert "succeeded" in data
        assert "failed" in data

    def test_auth_required(self):
        """Verify that requests without API key are rejected."""
        resp = requests.post(
            f"{API_URL}/enrich",
            json={"entity": {"name": "test"}, "object_type": "Test", "objective": "test"},
        )
        assert resp.status_code in (401, 403)

    def test_idempotency(self):
        """Same idempotency key should return cached result."""
        payload = {
            "entity": {"partner_name": "Idempotency Test Corp"},
            "object_type": "Lead",
            "objective": "Test idempotency.",
            "idempotency_key": "test-idempotency-key-001",
        }
        headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

        resp1 = requests.post(f"{API_URL}/enrich", json=payload, headers=headers, timeout=120)
        resp2 = requests.post(f"{API_URL}/enrich", json=payload, headers=headers, timeout=120)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Second call should be faster (cached)
        # Both should return same data
        if resp1.json().get("state") == "completed":
            assert resp1.json()["fields"] == resp2.json()["fields"]
