# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-005: Codecov Upload is Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-005

## Context

Codecov upload failures occur due to token expiry, network timeouts, and third-party service outages. These are infrastructure failures unrelated to code quality. The blocking coverage gate (60% threshold) is already enforced in the `test` job via `--cov-fail-under=60`.

## Decision

The `coverage-codecov-upload` CI job is non-blocking. Coverage enforcement happens in the blocking `test` job. Codecov is a reporting surface only.

## Consequences

Positive: Eliminates spurious CI blocks from Codecov outages. Negative: Coverage trend dashboards may have gaps during outages.

## Review Cadence

No scheduled review. Policy decision — does not expire.
