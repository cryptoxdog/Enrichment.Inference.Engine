# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-004: Bandit Static Security Analysis is Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-004

## Context

Bandit B1xx findings (assert statements, hardcoded bind addresses, try/except pass) are common false positives in this codebase due to test code and intentional patterns. The rule set has not been tuned to zero false-positives yet.

## Decision

The `security-bandit` CI job is non-blocking. HIGH severity findings are flagged in PR comments for manual review. LOW/MEDIUM findings are informational.

## Consequences

Positive: Eliminates false-positive blocks. Negative: HIGH findings require manual review discipline. Mitigation: PR template includes a bandit findings acknowledgment section.

## Review Cadence

Quarterly review. Convert to blocking when rule set tuned to zero false-positives.
