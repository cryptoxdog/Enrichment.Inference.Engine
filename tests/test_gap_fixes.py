"""Gap-pack regression checks adapted to repo reality."""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_RESET_ENV_KEYS = {
    "PERPLEXITY_API_KEY",
    "MAX_BUDGET_TOKENS",
    "MAX_BUDGET_TOKENS_DEFAULT",
    "MAX_TOKENS",
    "TOKEN_BUDGET",
}


def _fresh_settings(**env_overrides):
    for key in list(os.environ):
        if key in _RESET_ENV_KEYS:
            del os.environ[key]
    for key, value in env_overrides.items():
        os.environ[key] = str(value)

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.core.config import Settings

    return Settings()


def test_t01_perplexity_api_key_defaults_empty_string():
    settings = _fresh_settings()
    assert isinstance(settings.perplexity_api_key, str)
    assert settings.perplexity_api_key == ""


def test_t02_max_budget_tokens_exists_with_default():
    settings = _fresh_settings()
    assert settings.max_budget_tokens == 50_000


@pytest.mark.parametrize(
    ("env_name", "expected"),
    [
        ("MAX_TOKENS", 12_000),
        ("TOKEN_BUDGET", 16_000),
        ("MAX_BUDGET_TOKENS", 20_000),
    ],
)
def test_t03_budget_aliases_sync_to_canonical_field(env_name: str, expected: int):
    settings = _fresh_settings(**{env_name: expected})
    assert settings.max_budget_tokens == expected
    assert settings.max_tokens == expected
    assert settings.token_budget == expected


def test_t04_handlers_imports_use_repo_correct_modules():
    source = pathlib.Path("app/engines/handlers.py").read_text(encoding="utf-8")
    assert "services.kb_resolver" in source
    assert "engines.domain_yaml_reader" in source
    assert "services.kbresolver" not in source
    assert "services.domain_yaml_reader" not in source


def test_t05_orchestration_register_has_domain_reader_param():
    from app.engines.orchestration_layer import register

    assert "domain_reader" in inspect.signature(register).parameters


def test_t06_orchestration_register_wraps_graph_client_init():
    source = pathlib.Path("app/engines/orchestration_layer.py").read_text(encoding="utf-8")
    assert "try:" in source
    assert "GraphSyncClient" in source
    assert "graph_client_init_failed" in source


@pytest.mark.asyncio
async def test_t07_persist_and_sync_calls_result_store():
    from app.engines.handlers import _persist_and_sync

    mock_store = AsyncMock()
    mock_store.persist_enrich_response = AsyncMock()
    mock_router = MagicMock()
    mock_router.notify_graph_sync = AsyncMock()
    mock_router.route_fire_and_forget = MagicMock()
    response = {
        "fields": {"name": "Acme"},
        "confidence": 0.9,
        "state": "completed",
        "tokens_used": 100,
        "processing_time_ms": 50,
        "pass_count": 1,
        "uncertainty_score": 0.1,
        "quality_tier": "gold",
        "inferences": [],
        "kb_fragment_ids": [],
        "feature_vector": {},
        "failure_reason": None,
        "inference_version": "v1",
        "variation_count": 1,
        "consensus_threshold": 0.65,
        "kb_content_hash": "",
        "enrichment_payload": None,
        "grade_matches": [],
    }
    result_store_module = importlib.import_module("app.services.result_store")
    packet_router_module = importlib.import_module("app.engines.packet_router")
    with (
        patch.object(result_store_module, "ResultStore", return_value=mock_store),
        patch.object(packet_router_module, "get_router", return_value=mock_router),
    ):
        await _persist_and_sync("t1", {"entity_id": "e1", "domain": "company"}, response, "Company")

    mock_store.persist_enrich_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_t08_persist_and_sync_calls_graph_sync_and_score_invalidate():
    from app.engines.handlers import _persist_and_sync

    mock_store = AsyncMock()
    mock_store.persist_enrich_response = AsyncMock()
    mock_router = MagicMock()
    mock_router.notify_graph_sync = AsyncMock()
    mock_router.route_fire_and_forget = MagicMock()
    response = {
        "fields": {"industry": "Mfg"},
        "confidence": 0.85,
        "state": "completed",
        "tokens_used": 300,
        "processing_time_ms": 95,
        "pass_count": 1,
        "uncertainty_score": 0.15,
        "quality_tier": "silver",
        "inferences": [],
        "kb_fragment_ids": [],
        "feature_vector": {},
        "failure_reason": None,
        "inference_version": "v1",
        "variation_count": 1,
        "consensus_threshold": 0.65,
        "kb_content_hash": "",
        "enrichment_payload": None,
        "grade_matches": [],
    }
    result_store_module = importlib.import_module("app.services.result_store")
    packet_router_module = importlib.import_module("app.engines.packet_router")
    with (
        patch.object(result_store_module, "ResultStore", return_value=mock_store),
        patch.object(packet_router_module, "get_router", return_value=mock_router),
    ):
        await _persist_and_sync("t2", {"entity_id": "e2", "domain": "company"}, response, "Company")

    mock_router.notify_graph_sync.assert_awaited_once()
    assert mock_router.route_fire_and_forget.called


def test_t09_app_main_wires_domain_reader_and_warn_missing_keys():
    source = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    assert "settings.warn_missing_keys()" in source
    assert "DomainYamlReader" in source
    assert (
        "register_orchestration(kb=_kb, idem_store=_idem, domain_reader=_domain_reader)" in source
    )


@pytest.mark.parametrize(
    "module_path",
    [
        "app.core.config",
        "app.engines.handlers",
        "app.engines.orchestration_layer",
        "app.api.v1.converge",
        "app.main",
    ],
)
def test_t10_critical_module_paths_import(module_path: str):
    importlib.import_module(module_path)


def test_t11_migration_0003_has_upgrade_downgrade():
    path = pathlib.Path("alembic/versions/0003_config_max_budget_tokens.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert {"upgrade", "downgrade"}.issubset(names)
    assert "max_budget_tokens" in source
