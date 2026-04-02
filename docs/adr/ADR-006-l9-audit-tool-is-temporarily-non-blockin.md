# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-006: L9 Audit Tool is Temporarily Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-006

## Context

tools/audit_engine.py CLI interface is under active development. Breaking changes to the CLI contract occur frequently during tool development. Blocking the CI pipeline on a tool that is itself unstable creates a circular dependency.

## Decision

TEMPORARY: The `audit-l9-audit-tool` CI job is non-blocking until tools/audit_engine.py reaches a stable CLI contract. This waiver expires at milestone 2.0.

## Consequences

Positive: Decouples tool development from PR velocity. Negative: Audit violations may slip through. Mitigation: Developers run `make audit` locally as part of agent-check.

## Review Cadence

Review at milestone 2.0. Convert to blocking when CLI is stable. This is a TODO, not permanent policy.
