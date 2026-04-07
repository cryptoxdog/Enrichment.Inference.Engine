# Runtime Completeness Execution Guide

This pack wires the next runtime-facing L9 contract surfaces into repo-shaped modules and tier-2 tests.

## Milestone 1 — repo control plane fully live

### Files added
- `app/services/packet_enforcement.py`
- `app/services/dependency_enforcement.py`
- `app/services/action_authority.py`
- `app/services/event_contract_guard.py`
- `app/bootstrap/l9_contract_runtime.py`
- `tests/contracts/tier2/test_packet_enforcement_module.py`
- `tests/contracts/tier2/test_action_dependency_authority_module.py`
- `tests/contracts/tier2/test_event_contract_guard_module.py`
- `tests/contracts/tier2/test_l9_contract_runtime_bootstrap.py`

### Wiring points
1. Import `install_l9_contract_controls` in the FastAPI app factory.
2. Call `install_l9_contract_controls(app)` immediately after creating the app.
3. Keep existing routers and startup hooks intact; this layer is additive.
4. Keep `app/api/v1/attestation.py` unchanged; the bootstrap layer mounts it.

### Pass criteria
- `python scripts/l9_contract_control.py verify-constitution`
- `python scripts/l9_contract_control.py verify-attestation`
- `pytest tests/contracts/tier2/test_node_constitution_contract.py tests/contracts/tier2/test_runtime_attestation_contract.py -q`
- `pytest tests/contracts/tier2/test_l9_contract_runtime_bootstrap.py -q`

## Milestone 2 — runtime packet safety active

### Wiring points
1. Call `validate_ingress_packet(packet)` before dispatch in `/v1/execute` or the chassis ingress path.
2. Replace ad hoc packet hash and action validation with `validate_ingress_packet(...)`.
3. Build egress packets with `build_egress_packet(...)` before result emission.

### Blocks
- unknown actions
- tampered packets
- non-object payloads
- malformed lineage/hop trace
- writeback egress without explicit policy clearance

## Milestone 3 — authority + dependency gating active

### Wiring points
1. Call `authorize_action(...)` before business logic executes.
2. For MCP tools, resolve with `authorize_tool(tool_name)` then authorize the mapped action.
3. Feed writeback payloads directly to `authorize_action(...)` and use `writeback_evaluation` downstream.
4. Do not allow direct CRM mutation paths to bypass this service.

## Milestone 4 — event contract enforcement active

### Wiring points
1. Wrap event publishing with `emit_event(emitter_callable, event_payload, raise_on_failure=False)`.
2. If publishing through Redis `XADD`, wrap the lower-level publisher as `emitter_callable`.
3. Remove duplicate manual event base-field and wire-shape logic once inserted.

## Milestone 5 — integrated CI / review / agent flow fully operational

### Required existing surfaces
- `docs/contracts/node.constitution.yaml`
- `docs/contracts/runtime-attestation.schema.json`
- `scripts/verify_node_constitution.py`
- `scripts/l9_contract_control.py`
- `.github/workflows/l9-constitution-gate.yml`
- `.github/workflows/l9-contract-control.yml`
- `.github/copilot-instructions.md`
- `docs/contracts/enforcement/*.yaml`

### Dependency order
1. Milestone 1 before all others
2. Milestone 2 after Milestone 1
3. Milestone 3 after Milestones 1 and 2
4. Milestone 4 after Milestone 1
5. Milestone 5 after Milestones 1–4 are merged and green
