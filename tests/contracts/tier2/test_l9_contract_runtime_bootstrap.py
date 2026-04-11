from __future__ import annotations

from fastapi import FastAPI

from app.bootstrap.l9_contract_runtime import (
    get_l9_contract_runtime_state,
    install_l9_contract_controls,
)

pytest_plugins: list[str] = []


def test_install_l9_contract_controls_registers_attestation_route() -> None:
    app = FastAPI()
    install_l9_contract_controls(app)
    routes = {getattr(route, "path", None) for route in app.router.routes}
    assert "/v1/attestation" in routes


def test_get_l9_contract_runtime_state_reads_initialized_state() -> None:
    app = FastAPI()
    install_l9_contract_controls(app)
    app.state.l9_contract_control = {
        "node_id": "enrichment-engine",
        "node_version": "2.3.0",
        "contract_version": "1.0.0",
        "contract_digest": "abc123",
        "policy_mode": "enforced",
        "degraded_modes": [],
    }
    state = get_l9_contract_runtime_state(app)
    assert state["node_id"] == "enrichment-engine"
    assert state["policy_mode"] == "enforced"
