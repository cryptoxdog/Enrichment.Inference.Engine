# Copilot Instructions

For this repository, treat `docs/contracts/node.constitution.yaml` as the source of truth for:
- action inventory
- tool inventory
- event inventory
- dependency readiness semantics
- runtime attestation shape

When changing contract-bound runtime files under `app/`, `chassis/`, or contract documents under `docs/contracts/`, also update the relevant tests under `tests/contracts/`.

Do not introduce:
- uncontracted actions
- uncontracted tools
- uncontracted event types
- runtime attestation fields not reflected in `docs/contracts/runtime-attestation.schema.json`

Prefer additive, test-backed changes that keep the constitution, attestation builder, and Tier 2 contract tests aligned.
