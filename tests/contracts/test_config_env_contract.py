"""
Config / Env Contract Tests
Source: app/core/config.py Settings, .env.example
Markers: unit
"""
from __future__ import annotations
from pathlib import Path
import pytest
import yaml
from tests.contracts.conftest_contracts import CONFIG_DIR, REPO_ROOT, load_yaml

REQUIRED_ENV_VARS = {
    "ENRICHMENT_ENGINE_API_KEY": {"type": "secret", "required": True, "sensitive": True},
    "ENRICHMENT_ENGINE_MODE":    {"type": "string", "required": False, "default": "enrichment"},
    "HOST":       {"type": "string", "required": False, "default": "0.0.0.0"},
    "PORT":       {"type": "integer", "required": False, "default": "8000"},
    "LOG_LEVEL":  {"type": "string", "required": False, "default": "INFO"},
    "PERPLEXITY_API_KEY": {"type": "secret", "required": True, "sensitive": True},
    "CLEARBIT_API_KEY":   {"type": "secret", "required": False, "sensitive": True},
    "ZOOMINFO_API_KEY":   {"type": "secret", "required": False, "sensitive": True},
    "APOLLO_API_KEY":     {"type": "secret", "required": False, "sensitive": True},
    "HUNTER_API_KEY":     {"type": "secret", "required": False, "sensitive": True},
    "OPENAI_API_KEY":     {"type": "secret", "required": False, "sensitive": True},
    "ANTHROPIC_API_KEY":  {"type": "secret", "required": False, "sensitive": True},
    "REDIS_URL":          {"type": "url", "required": True, "sensitive": False},
    "NEO4J_URI":          {"type": "url", "required": False, "sensitive": False},
    "NEO4J_USERNAME":     {"type": "string", "required": False, "sensitive": False},
    "NEO4J_PASSWORD":     {"type": "secret", "required": False, "sensitive": True},
    "KB_FILES_PATH":      {"type": "string", "required": False},
    "CB_FAILURE_THRESHOLD": {"type": "integer", "required": False, "default": "5"},
    "CB_COOLDOWN_SECONDS":  {"type": "integer", "required": False, "default": "60"},
    "CONSENSUS_THRESHOLD":  {"type": "float", "required": False, "default": "0.7"},
    "ODOO_URL":             {"type": "url", "required": False, "sensitive": False},
    "ODOO_DB":              {"type": "string", "required": False},
    "ODOO_USERNAME":        {"type": "string", "required": False},
    "ODOO_API_KEY":         {"type": "secret", "required": False, "sensitive": True},
    "SALESFORCE_CLIENT_ID":     {"type": "secret", "required": False, "sensitive": True},
    "SALESFORCE_CLIENT_SECRET": {"type": "secret", "required": False, "sensitive": True},
    "SALESFORCE_USERNAME":      {"type": "string", "required": False},
    "SALESFORCE_PASSWORD":      {"type": "secret", "required": False, "sensitive": True},
    "SALESFORCE_DOMAIN":        {"type": "string", "required": False},
    "HUBSPOT_ACCESS_TOKEN":     {"type": "secret", "required": False, "sensitive": True},
    "DATABASE_URL":             {"type": "url", "required": False, "sensitive": False},
    "ASYNC_DATABASE_URL":       {"type": "url", "required": False, "sensitive": False},
    "DB_POOL_MIN_SIZE":         {"type": "integer", "required": False, "default": "2"},
    "DB_POOL_MAX_SIZE":         {"type": "integer", "required": False, "default": "10"},
    "ENABLE_GRAPH_MEMORY":      {"type": "boolean", "required": False, "default": "false"},
}


@pytest.fixture(scope="module")
def env_contract() -> dict:
    path = CONFIG_DIR / "env-contract.yaml"
    if not path.exists():
        pytest.skip("env-contract.yaml missing")
    return load_yaml(path)


@pytest.mark.unit
def test_env_contract_is_valid_yaml(env_contract: dict) -> None:
    assert isinstance(env_contract, dict)


@pytest.mark.unit
@pytest.mark.parametrize("var_name", REQUIRED_ENV_VARS.keys())
def test_env_var_documented(var_name: str, env_contract: dict) -> None:
    assert var_name in str(env_contract), (
        f"Env var '{var_name}' not documented in env-contract.yaml. "
        "Source: app/core/config.py Settings class"
    )


@pytest.mark.unit
@pytest.mark.parametrize("var_name,meta", REQUIRED_ENV_VARS.items())
def test_sensitive_vars_marked(var_name: str, meta: dict, env_contract: dict) -> None:
    if not meta.get("sensitive"):
        return
    s = str(env_contract)
    if var_name not in s:
        pytest.skip(f"{var_name} not in contract")
    assert "sensitive" in s.lower(), (
        f"env-contract.yaml must mark sensitive vars. {var_name} is sensitive — Phase 1.5"
    )


@pytest.mark.unit
def test_env_contract_has_source_annotation(env_contract: dict) -> None:
    s = str(env_contract).lower()
    assert "app/core/config.py" in s or "config.py" in s or "source" in s, (
        "env-contract.yaml must trace to app/core/config.py — Phase 3.6 Rule 1"
    )


@pytest.mark.unit
def test_env_contract_has_examples(env_contract: dict) -> None:
    s = str(env_contract)
    has_examples = "example" in s.lower()
    assert has_examples, "env-contract.yaml must include examples — Phase 3.6 Rule 3"


CRITICAL_REQUIRED_VARS = [
    "ENRICHMENT_ENGINE_API_KEY", "PERPLEXITY_API_KEY", "REDIS_URL",
]

@pytest.mark.unit
@pytest.mark.parametrize("var_name", CRITICAL_REQUIRED_VARS)
def test_critical_vars_marked_required(var_name: str, env_contract: dict) -> None:
    s = str(env_contract)
    if var_name not in s:
        pytest.skip(f"{var_name} not in contract")
    idx = s.find(var_name)
    surrounding = s[max(0, idx-20):idx+200]
    assert "required" in surrounding.lower() and (
        "true" in surrounding.lower() or ": true" in surrounding.lower()
    ), f"{var_name}: must be marked required: true in env-contract.yaml"


@pytest.mark.unit
def test_dotenv_example_aligns_with_contract() -> None:
    dotenv_path = REPO_ROOT / ".env.example"
    if not dotenv_path.exists():
        pytest.skip(".env.example not found at repo root")
    dotenv_vars = set()
    for line in dotenv_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            dotenv_vars.add(line.split("=")[0].strip())
    env_path = CONFIG_DIR / "env-contract.yaml"
    if not env_path.exists():
        pytest.skip("env-contract.yaml missing")
    contract_str = env_path.read_text()
    undocumented = [v for v in dotenv_vars if v not in contract_str and v.strip()]
    assert not undocumented, (
        f".env.example vars not in env-contract.yaml: {undocumented}. "
        "Every env var in .env.example must be documented."
    )
