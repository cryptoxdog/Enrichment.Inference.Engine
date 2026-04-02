# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, coderabbit, delta]
# owner: platform
# status: active
# token_estimate: 150
# ssot_for: [coderabbit-specific-delta]
# load_when: [coderabbit_review]
# references: [AGENT.md, .coderabbit.yaml, AI_AGENT_REVIEW_CHECKLIST.md]
# --- /L9_META ---

# CODERABBIT.md — CodeRabbit-Specific Delta

**VERSION**: 1.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> Delta-only file. Load AGENT.md first. This file contains ONLY CodeRabbit-specific overrides.

## Primary Configuration

`.coderabbit.yaml` in repository root is the primary CodeRabbit configuration.
This file provides governance-layer context that supplements it.

## Review Behavior

- **Auto-approve**: PRs where all phases of AI_AGENT_REVIEW_CHECKLIST.md pass with 0 CRITICAL, 0 HIGH violations.
- **Request changes**: Any CRITICAL violation (SEC-001, ARCH-001, C-10).
- **Escalation**: Tag `@cryptoxdog` on any C-01 chassis violation or credential exposure.

## Output Format

Use review comment templates from AI_AGENT_REVIEW_CHECKLIST.md.
Do NOT emit free-form prose for contract violations — always use the structured template.

## Paths to Skip

Skip review on: `docs/`, `readme/`, `reports/`, `*.json` (generated), `htmlcov/`, `coverage.xml`.
