"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def api_key() -> str:
    return "test-client-api-key"


@pytest.fixture(scope="session")
def api_key_hash() -> str:
    import hashlib

    return hashlib.sha256(b"test-client-api-key").hexdigest()


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, api_key_hash):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY_HASH", api_key_hash)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("KB_DIR", "tests/fixtures/kb")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
