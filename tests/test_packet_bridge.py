# tests/test_packet_bridge.py
"""
PacketEnvelope Bridge Test Suite

Coverage:
    - Packet validation
    - Response wrapping
    - Lineage preservation
    - Content-hash integrity
"""

import pytest

from engine.gates.packet_bridge import validate_packet, wrap_response


class TestValidatePacket:
    """Test incoming packet validation."""

    def test_valid_packet(self):
        """Valid packet passes validation."""
        packet = {
            "header": {
                "packet_id": "pkt_123",
                "tenant_id": "tenant_1",
                "action": "enrich",
                "timestamp": "2026-03-28T22:00:00Z",
            },
            "content_hash": "abc123",
            "payload": {"entity_id": "E001"},
        }
        is_valid, error = validate_packet(packet)
        assert is_valid
        assert error is None

    def test_missing_header(self):
        """Missing header → validation fails."""
        packet = {"payload": {}}
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "Missing 'header'" in error

    def test_missing_packet_id(self):
        """Missing packet_id → validation fails."""
        packet = {
            "header": {
                "tenant_id": "tenant_1",
                "action": "enrich",
                "timestamp": "2026-03-28T22:00:00Z",
            },
            "content_hash": "abc",
            "payload": {},
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "packet_id" in error

    def test_missing_content_hash(self):
        """Missing content_hash → validation fails."""
        packet = {
            "header": {
                "packet_id": "pkt_123",
                "tenant_id": "tenant_1",
                "action": "enrich",
                "timestamp": "2026-03-28T22:00:00Z",
            },
            "payload": {},
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "content_hash" in error


class TestWrapResponse:
    """Test response envelope wrapping."""

    def test_tenant_id_preserved(self):
        """tenant_id copied from request."""
        request = {
            "header": {
                "packet_id": "req_001",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
            }
        }
        result = {"data": "value"}
        response = wrap_response(result, request)
        assert response["header"]["tenant_id"] == "tenant_alpha"

    def test_lineage_appended(self):
        """Request packet_id appended to lineage."""
        request = {
            "header": {
                "packet_id": "req_001",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
                "lineage": ["pkt_000"],
            }
        }
        result = {"data": "value"}
        response = wrap_response(result, request)
        assert response["header"]["lineage"] == ["pkt_000", "req_001"]

    def test_new_packet_id_generated(self):
        """New packet_id generated for response."""
        request = {
            "header": {
                "packet_id": "req_001",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
            }
        }
        result = {"data": "value"}
        response = wrap_response(result, request)
        assert response["header"]["packet_id"] != "req_001"
        assert response["header"]["packet_id"].startswith("pkt_")

    def test_content_hash_computed(self):
        """content_hash computed from payload."""
        request = {
            "header": {
                "packet_id": "req_001",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
            }
        }
        result = {"data": "value"}
        response = wrap_response(result, request)
        assert "content_hash" in response
        assert len(response["content_hash"]) == 64  # SHA-256 hex

    def test_intelligence_quality_included(self):
        """intelligence_quality metadata included when provided."""
        request = {
            "header": {
                "packet_id": "req_001",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
            }
        }
        result = {"data": "value"}
        intelligence_quality = {"method": "belief_propagation"}
        response = wrap_response(result, request, intelligence_quality)
        assert (
            response["payload"]["intelligence_quality"]["method"]
            == "belief_propagation"
        )
