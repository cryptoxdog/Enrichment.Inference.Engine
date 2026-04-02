"""
Integration test fixtures — Neo4j testcontainer + FastAPI test client.
Requires: testcontainers[neo4j], pytest-asyncio, httpx
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def neo4j_container():
    """Spin up Neo4j 5 Community (no license needed) for tests."""
    try:
        from testcontainers.neo4j import Neo4jContainer

        with Neo4jContainer(image="neo4j:5") as container:
            yield container
    except ImportError:
        pytest.skip("testcontainers not installed")


@pytest_asyncio.fixture
async def api_client():
    """AsyncClient pointed at FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
        headers={"Authorization": "Bearer test-key"},
    ) as client:
        yield client


@pytest.fixture
def sample_enrich_payload():
    return {
        "entity_id": "test-entity-001",
        "entity_type": "facility",
        "domain": "plasticos",
        "fields": {
            "company_name": "Alpha Recyclers LLC",
            "materials_handled": ["HDPE", "LDPE"],
            "city": "Charlotte",
            "state": "NC",
        },
    }
