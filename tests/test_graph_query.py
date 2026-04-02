# tests/test_graph_query.py
"""
Graph Query Test Suite

Coverage:
    - Parameterized query execution
    - GATE lookup
    - Error handling
"""

import pytest

from engine.traversal.graph_query import execute_gate_lookup, execute_match_query


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self, mock_results):
        self.mock_results = mock_results
        self.last_query = None
        self.last_params = None

    async def execute_query(self, query, params):
        self.last_query = query
        self.last_params = params
        return self.mock_results


class TestExecuteMatchQuery:
    """Test CEG match query execution."""

    @pytest.mark.asyncio
    async def test_parameterized_query(self):
        """Query uses parameters, not string interpolation."""
        mock_driver = MockNeo4jDriver(
            [
                {
                    "id": "M001",
                    "name": "HDPE Regrind",
                    "geo": 0.9,
                    "temporal": 0.85,
                }
            ]
        )

        results = await execute_match_query(
            mock_driver,
            entity_type="Material",
            entity_id="MAT_001",
            dimension_keys=["geo", "temporal"],
            limit=10,
        )

        # Verify parameterization
        assert "$entity_id" in mock_driver.last_query
        assert "$limit" in mock_driver.last_query
        assert mock_driver.last_params["entity_id"] == "MAT_001"
        assert mock_driver.last_params["limit"] == 10

        # Verify results
        assert len(results) == 1
        assert results[0]["id"] == "M001"

    @pytest.mark.asyncio
    async def test_dimension_keys_in_return(self):
        """Dimension keys included in RETURN clause."""
        mock_driver = MockNeo4jDriver([])

        await execute_match_query(
            mock_driver,
            entity_type="Material",
            entity_id="MAT_001",
            dimension_keys=["geo", "community", "temporal"],
            limit=5,
        )

        # Verify RETURN clause contains dimension keys
        query = mock_driver.last_query
        assert "r.geo AS geo" in query
        assert "r.community AS community" in query
        assert "r.temporal AS temporal" in query


class TestExecuteGateLookup:
    """Test GATE endpoint lookup."""

    @pytest.mark.asyncio
    async def test_gate_found(self):
        """Successful GATE lookup returns config."""
        mock_driver = MockNeo4jDriver(
            [
                {
                    "endpoint": "https://ceg-engine:8000/v1/execute",
                    "timeout_ms": 30000,
                }
            ]
        )

        config = await execute_gate_lookup(mock_driver, "ceg-engine", "match")

        assert config is not None
        assert config["endpoint"] == "https://ceg-engine:8000/v1/execute"
        assert config["timeout_ms"] == 30000

    @pytest.mark.asyncio
    async def test_gate_not_found(self):
        """GATE not found returns None."""
        mock_driver = MockNeo4jDriver([])

        config = await execute_gate_lookup(mock_driver, "unknown-service", "unknown-action")

        assert config is None
