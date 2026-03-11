"""Health endpoint tests."""

def test_health_returns_200(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.2.0"


def test_health_shows_circuit_state(client):
    resp = client.get("/api/v1/health")
    assert resp.json()["circuit"] in ("closed", "open")
