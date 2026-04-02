# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-003: safety-check Security Scan is Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-003

## Context

The `safety check` tool overlaps significantly with `pip-audit` on the same PyPA advisory database. Running both provides marginal additional signal while doubling triage burden.

## Decision

The `security-safety-check` CI job is non-blocking. It serves as a secondary signal layer. pip-audit (WAIVER-002) is the primary security scan.

## Consequences

Positive: Reduces triage noise. Negative: None material — pip-audit covers the same advisory set.

## Review Cadence

Monthly review alongside pip-audit. Policy decision — does not expire.
