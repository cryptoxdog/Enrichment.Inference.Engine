# tests/test_handlers_integration.py
"""
Handler Integration Test Suite

Coverage:
    - End-to-end handler flow
    - Belief propagation integration
    - PacketEnvelope protocol
"""

import pytest

from engine.compliance.validator import validate_enrichment_request
from engine.gates.packet_bridge import validate_packet, wrap_response
from engine.scoring.belief_propagation import rescore_candidates


class TestEnrichmentFlow:
    """Test full enrichment request flow."""

    def test_valid_request_validated(self):
        """Valid enrichment request passes validation."""
        payload = {
            "entity_id": "MAT_001",
            "entity_type": "Material",
            "convergence_depth": 2,
        }
        is_valid, error = validate_enrichment_request(payload)
        assert is_valid
        assert error is None

    def test_invalid_entity_type(self):
        """Invalid entity_type rejected."""
        payload = {
            "entity_id": "MAT_001",
            "entity_type": "InvalidType",
        }
        is_valid, error = validate_enrichment_request(payload)
        assert not is_valid
        assert "Invalid entity_type" in error

    def test_rescoring_integration(self):
        """Belief rescoring works in handler context."""
        candidates = [
            {"id": "A", "geo": 0.9, "temporal": 0.85, "confidence": 0.7},
            {"id": "B", "geo": 0.95, "temporal": 0.9, "confidence": 0.5},
        ]
        rescored = rescore_candidates(candidates, ["geo", "temporal"])
        assert "belief_score" in rescored[0]
        assert rescored[0]["belief_score"] > 0.0


class TestPacketProtocol:
    """Test PacketEnvelope protocol compliance."""

    def test_end_to_end_packet_flow(self):
        """Complete packet ingress → handler → response → egress."""
        # Step 1: Incoming packet
        request_packet = {
            "header": {
                "packet_id": "req_123",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
                "timestamp": "2026-03-28T22:00:00Z",
            },
            "content_hash": "abc123",
            "payload": {
                "entity_id": "MAT_001",
                "entity_type": "Material",
            },
        }

        # Step 2: Validate ingress
        is_valid, error = validate_packet(request_packet)
        assert is_valid

        # Step 3: Validate payload
        is_valid, error = validate_enrichment_request(
            request_packet["payload"]
        )
        assert is_valid

        # Step 4: Simulate handler response
        handler_result = {
            "matches": [
                {"id": "M001", "belief_score": 0.85},
                {"id": "M002", "belief_score": 0.78},
            ]
        }

        intelligence_quality = {
            "method": "entropy_penalized_composite",
            "dimensions_used": ["geo", "temporal"],
        }

        # Step 5: Wrap response
        response_packet = wrap_response(
            handler_result, request_packet, intelligence_quality
        )

        # Step 6: Verify response structure
        assert "header" in response_packet
        assert "payload" in response_packet
        assert "content_hash" in response_packet
        assert response_packet["header"]["tenant_id"] == "tenant_alpha"
        assert "req_123" in response_packet["header"]["lineage"]
        assert (
            response_packet["payload"]["intelligence_quality"]["method"]
            == "entropy_penalized_composite"
        )
