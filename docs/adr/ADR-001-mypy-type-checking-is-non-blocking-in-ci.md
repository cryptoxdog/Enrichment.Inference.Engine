# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-001: MyPy Type Checking is Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-001

## Context

The codebase is undergoing progressive type annotation adoption. At the time of this decision, mypy reports errors due to incomplete annotations in legacy modules and third-party stubs. Making mypy blocking would prevent all PRs from merging during the rollout period.

## Decision

The `lint-mypy` CI job is non-blocking. Mypy failures are reported as informational output. PRs may merge when all other blocking gates pass.

## Consequences

Positive: Unblocks development during annotation rollout. Negative: Type errors may accumulate. Mitigation: mypy error count tracked in CI output. Gate converts to blocking when annotation coverage reaches 80%.

## Review Cadence

Quarterly review of mypy error count. Convert to blocking when coverage >= 80%.
