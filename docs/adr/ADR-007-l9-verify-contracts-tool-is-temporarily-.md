# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-007: L9 Verify Contracts Tool is Temporarily Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-007

## Context

tools/verify_contracts.py is under active development alongside the L9_META template system. Premature blocking on this tool would block all PRs during template rollout.

## Decision

TEMPORARY: The `verify-l9-verify-tool` CI job is non-blocking until tools/verify_contracts.py reaches a stable contract. This waiver expires at milestone 2.0.

## Consequences

Positive: Decouples tool rollout from PR velocity. Negative: L9_META violations may slip through. Mitigation: Developers run `make verify` locally as part of agent-check.

## Review Cadence

Review at milestone 2.0. Convert to blocking when tool is stable. This is a TODO, not permanent policy.
