"""Shared fixtures for the docs/contracts/ test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
CONTRACTS_DIR = REPO_ROOT / "docs" / "contracts"
API_DIR = CONTRACTS_DIR / "api"
AGENTS_DIR = CONTRACTS_DIR / "agents"
DATA_DIR = CONTRACTS_DIR / "data"
EVENTS_DIR = CONTRACTS_DIR / "events"
CONFIG_DIR = CONTRACTS_DIR / "config"
DEPS_DIR = CONTRACTS_DIR / "dependencies"
TEMPLATES_DIR = CONTRACTS_DIR / "_templates"


@pytest.fixture(scope="session")
def contracts_root() -> Path:
    return CONTRACTS_DIR


@pytest.fixture(scope="session")
def api_dir() -> Path:
    return API_DIR


@pytest.fixture(scope="session")
def agents_dir() -> Path:
    return AGENTS_DIR


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def events_dir() -> Path:
    return EVENTS_DIR


@pytest.fixture(scope="session")
def config_dir() -> Path:
    return CONFIG_DIR


@pytest.fixture(scope="session")
def deps_dir() -> Path:
    return DEPS_DIR


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    return TEMPLATES_DIR


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def openapi_spec() -> dict:
    return load_yaml(API_DIR / "openapi.yaml")


@pytest.fixture(scope="session")
def asyncapi_spec() -> dict:
    return load_yaml(EVENTS_DIR / "asyncapi.yaml")


@pytest.fixture(scope="session")
def env_contract() -> dict:
    return load_yaml(CONFIG_DIR / "env-contract.yaml")


@pytest.fixture(scope="session")
def shared_models() -> dict:
    return load_yaml(API_DIR / "schemas" / "shared-models.yaml")


@pytest.fixture(scope="session")
def error_responses() -> dict:
    return load_yaml(API_DIR / "schemas" / "error-responses.yaml")


@pytest.fixture(scope="session")
def packet_envelope_contract() -> dict:
    return load_yaml(AGENTS_DIR / "protocols" / "packet-envelope.yaml")


@pytest.fixture(scope="session")
def tool_index() -> dict:
    return load_yaml(AGENTS_DIR / "tool-schemas" / "_index.yaml")


@pytest.fixture(scope="session")
def data_model_index() -> dict:
    return load_yaml(DATA_DIR / "models" / "_index.yaml")


@pytest.fixture(scope="session")
def deps_index() -> dict:
    return load_yaml(DEPS_DIR / "_index.yaml")


@pytest.fixture(scope="session")
def graph_schema() -> dict:
    return load_yaml(DATA_DIR / "graph-schema.yaml")


@pytest.fixture(scope="session")
def event_envelope() -> dict:
    return load_yaml(EVENTS_DIR / "schemas" / "event-envelope.yaml")
