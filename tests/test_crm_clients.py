"""
Tests for CRM client implementations.

Validates that Salesforce and HubSpot clients:
1. Implement CRMClientBase contract
2. Are registered in CLIENT_REGISTRY
3. Handle initialization correctly
"""
from __future__ import annotations

import pytest

from app.services.crm.base import CRMClientBase, CRMCredentials, CRMType
from app.services.crm.salesforce_client import SalesforceClient
from app.services.crm.hubspot_client import HubSpotClient
from app.services.crm import CLIENT_REGISTRY


class TestClientRegistry:
    """Verify all CRM clients are registered."""

    def test_registry_has_odoo(self) -> None:
        assert CRMType.ODOO in CLIENT_REGISTRY

    def test_registry_has_salesforce(self) -> None:
        assert CRMType.SALESFORCE in CLIENT_REGISTRY

    def test_registry_has_hubspot(self) -> None:
        assert CRMType.HUBSPOT in CLIENT_REGISTRY

    def test_all_registry_values_are_crm_client_base(self) -> None:
        for crm_type, cls in CLIENT_REGISTRY.items():
            assert issubclass(cls, CRMClientBase), f"{crm_type} is not a CRMClientBase"


class TestSalesforceClient:
    """Salesforce client unit tests."""

    def test_init(self) -> None:
        creds = CRMCredentials(
            crm_type=CRMType.SALESFORCE,
            credentials={
                "client_id": "test",
                "client_secret": "test",
                "username": "test@test.com",
                "password": "test",
                "security_token": "tok",
            },
        )
        client = SalesforceClient(creds)
        assert client._api_version == "v59.0"
        assert client._access_token == ""

    def test_test_connection_without_auth(self) -> None:
        creds = CRMCredentials(
            crm_type=CRMType.SALESFORCE,
            credentials={},
        )
        client = SalesforceClient(creds)
        assert client.test_connection() is False

    def test_custom_api_version(self) -> None:
        creds = CRMCredentials(
            crm_type=CRMType.SALESFORCE,
            credentials={"api_version": "v58.0"},
        )
        client = SalesforceClient(creds)
        assert client._api_version == "v58.0"


class TestHubSpotClient:
    """HubSpot client unit tests."""

    def test_init(self) -> None:
        creds = CRMCredentials(
            crm_type=CRMType.HUBSPOT,
            credentials={"access_token": "test-token"},
        )
        client = HubSpotClient(creds)
        assert client._access_token == "test-token"
        assert client._base_url == "https://api.hubapi.com"

    def test_test_connection_without_auth(self) -> None:
        creds = CRMCredentials(
            crm_type=CRMType.HUBSPOT,
            credentials={},
        )
        client = HubSpotClient(creds)
        # Will fail because no valid token
        assert client.test_connection() is False
