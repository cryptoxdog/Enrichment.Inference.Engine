"""Auth tests — ensure enrich rejects bad/missing keys."""


def test_enrich_rejects_no_key(client):
    resp = client.post("/api/v1/enrich", json={"entity": {"name": "test"}})
    assert resp.status_code in (401, 403)


def test_enrich_rejects_bad_key(client):
    resp = client.post(
        "/api/v1/enrich",
        json={"entity": {"name": "test"}},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code in (401, 403)


def test_enrich_accepts_valid_key(client, api_key):
    """With a valid key the request reaches the pipeline (may fail on Perplexity mock)."""
    resp = client.post(
        "/api/v1/enrich",
        json={"entity": {"name": "test"}},
        headers={"X-API-Key": api_key},
    )
    # 200 or 500 (Perplexity not mocked) — but NOT 401/403
    assert resp.status_code != 401
    assert resp.status_code != 403
