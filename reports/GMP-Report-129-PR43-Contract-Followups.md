# GMP Report 129 — PR #43 Contract Follow-ups

- Date: 2026-04-07
- Tier: RUNTIME_TIER
- Status: Completed locally, not committed
- Scope: Post-merge cleanup for PR #43 contract/test issues on `main`

## TODO Plan

| ID | File | Action | Intent |
| --- | --- | --- | --- |
| T1 | `tests/contracts/test_agent_tool_contracts.py` | Replace | Fix the live CodeQL alert with exact `$schema` hostname parsing. |
| T2 | `tests/contracts/tier2/test_enforcement_behavior.py` | Replace | Correct inverted state/failure_reason invariant tests. |
| T3 | `chassis/envelope.py` | Replace | Normalize ingress lineage so production matches the contract test assumptions. |
| T4 | `tests/contracts/tier2/test_enforcement_packet_runtime.py` | Replace | Align helper hop-trace and parent lineage semantics with `deflate_egress()`. |
| T5 | `tests/contracts/test_config_env_contract.py` | Replace | Make env-contract assertions key-aware and variable-scoped. |
| T6 | `tests/contracts/test_mcp_server_alignment.py` | Replace | Stop masking real MCP import regressions behind a broad `ImportError` skip. |
| T7 | `tests/contracts/test_shared_schema_contracts.py` | Replace | Tighten assertions to inspect actual shared/error schema structures and `$ref` usage. |
| T8 | `tests/contracts/test_template_contracts.py` | Replace | Make placeholder detection real and align endpoint template structure checks. |
| T9 | `docs/contracts/_templates/api-endpoint.template.yaml` | Replace | Make the endpoint template valid YAML with quoted placeholder values. |
| T10 | `docs/contracts/dependencies/openai.yaml` | Replace | Fix transport protocol and remove the unresolved role TODO using source-backed wording. |
| T11 | `docs/contracts/dependencies/clearbit.yaml` | Replace | Separate auth env from base URL and fix protocol to match the configured source. |
| T12 | `docs/contracts/README.md` | Replace | Correct AJV multi-schema validation guidance and markdown lint issues. |
| T13 | `.env.example` | Replace | Align the Odoo username env var with the established `app/core/config.py` setting name. |

## Files Modified

- `.env.example`
- `chassis/envelope.py`
- `docs/contracts/README.md`
- `docs/contracts/_templates/api-endpoint.template.yaml`
- `docs/contracts/api/openapi.yaml`
- `docs/contracts/dependencies/clearbit.yaml`
- `docs/contracts/dependencies/openai.yaml`
- `tests/contracts/test_agent_tool_contracts.py`
- `tests/contracts/test_config_env_contract.py`
- `tests/contracts/test_mcp_server_alignment.py`
- `tests/contracts/test_openapi_contract.py`
- `tests/contracts/test_shared_schema_contracts.py`
- `tests/contracts/test_template_contracts.py`
- `tests/contracts/tier2/test_enforcement_behavior.py`
- `tests/contracts/tier2/test_enforcement_packet_runtime.py`
- `workflow_state.md`

## Validation Results

- Command: `pytest --no-cov tests/contracts/test_agent_tool_contracts.py tests/contracts/tier2/test_enforcement_behavior.py tests/contracts/tier2/test_enforcement_packet_runtime.py tests/contracts/test_config_env_contract.py tests/contracts/test_mcp_server_alignment.py tests/contracts/test_shared_schema_contracts.py tests/contracts/test_template_contracts.py -q`
- Result: `210 passed`
- Command: `pytest --no-cov tests/contracts/test_openapi_contract.py tests/contracts/test_shared_schema_contracts.py -q`
- Result: `68 passed`
- Notes: Two existing `pytest.mark.enforcement` warnings remain; no functional test failures in the targeted slice.

## Phase 5 Recursive Verification

- CodeQL follow-up: the single open alert for `py/incomplete-url-substring-sanitization` at `tests/contracts/test_agent_tool_contracts.py` now has an exact URL parse/hostname check locally.
- Runtime/test drift: the packet runtime helper now matches `chassis/envelope.py`, and `chassis/envelope.py` now normalizes lineage fields defensively.
- Contract suite: the previously failing targeted tests on `main` now pass without relying on substring-based false positives.
- OpenAPI follow-up: reusable responses now live under `components.responses`, `/v1/converge` matches the live FastAPI request/response models, and stale `{id}` / `{field}` path names were corrected in the OpenAPI contract test.

## Outstanding Items

- GitHub review threads were not resolved remotely because the fixes exist only in the local working tree and have not yet been pushed in a follow-up branch/PR.
- No commit was created. No push was attempted.

## Final Declaration

This GMP completed the requested local cleanup scope for PR #43 follow-ups:
the live CodeQL test alert was fixed, the agreed production/test mismatches were aligned, the failing contract tests were repaired, and a narrow set of code-backed docs/contract nits were cleaned up. The work is validated locally and ready for user review or a follow-up commit/PR.
