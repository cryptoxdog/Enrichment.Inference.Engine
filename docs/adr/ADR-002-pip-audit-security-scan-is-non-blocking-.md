# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, adr, ci, waiver]
# owner: platform
# status: active
# --- /L9_META ---

# ADR-002: pip-audit Security Scan is Non-Blocking in CI

**Date**: 2026-04-01 | **Status**: Accepted | **Author**: Platform Team | **Waiver**: WAIVER-002

## Context

pip-audit reports vulnerabilities from PyPA advisory database. Many advisories affect dev-only or transitive dependencies with no direct exploitation path. Automated blocking produces false-positive merge blocks that require human triage anyway.

## Decision

The `security-pip-audit` CI job is non-blocking. CVE reports are logged and reviewed weekly by the platform team. CRITICAL severity CVEs trigger an expedited manual merge block.

## Consequences

Positive: Eliminates false-positive blocks. Negative: Vulnerabilities require weekly manual review. Mitigation: CRITICAL CVE escalation procedure defined in platform runbook.

## Review Cadence

Monthly review. Policy decision — does not expire.
