# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, review, checklist, pr]
# owner: platform
# status: active
# token_estimate: 1570
# ssot_for: [pr-review-protocol, review-decision-matrix, comment-templates]
# load_when: [pr_review, code_review]
# references: [AGENTS.md, CI_WHITELIST_REGISTER.md, INVARIANTS.md]
# --- /L9_META ---

# AI_AGENT_REVIEW_CHECKLIST.md — PR Review Checklist

**VERSION**: 2.1.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-11

> Load [AGENTS.md](AGENTS.md) before this file for contracts, tiers, and patterns.

---

## Review Decision Matrix

Apply this verdict BEFORE writing any inline comments.

| CRITICAL violations | HIGH violations | Verdict |
|---|---|---|
| 0 | 0 | APPROVE (add suggestions as non-blocking comments) |
| 0 | 1-2 | REQUEST_CHANGES — must fix before merge |
| 0 | 3+ | REQUEST_CHANGES — tag @platform-team |
| 1+ | any | REQUEST_CHANGES — tag @platform-team |
| SEC-001 or ARCH-001 | any | REQUEST_CHANGES — tag @platform-team + add security label |

---

## Phase 1 — STOP: Merge-Blocking Violations (Check First)

- [ ] C-01 / ARCH-001: `from fastapi import` outside allowed modules ([AGENTS.md](AGENTS.md) C-01: typically `app/api/`, `app/main.py`, `app/engines/handlers.py`)?
- [ ] C-06 / SEC-002/003: eval(, exec(, compile(, pickle.loads( present?
- [ ] C-07 / SEC-001: Cypher f-string without sanitize_label()?
- [ ] C-08 / SEC-007: yaml.load( without Loader=yaml.SafeLoader?
- [ ] C-10: Hardcoded API key, token, or credential?
- [ ] C-13: Transport/dispatch contract drift — changes to envelope ingress/egress or action registration without paired updates in the same PR? (Canonical modules include `chassis/envelope.py`, `app/services/chassis_handlers.py`, `app/api/v1/chassis_endpoint.py`, and `app/engines/handlers.py` / orchestration; see [AGENTS.md](AGENTS.md) C-13 intent.)
- [ ] C-11: `TransportPacket` / chassis wire envelope mutated in place after construction?
- [ ] C-16: Python less than 3.12 syntax or backport import present?

---

## Phase 2 — STOP: Contract Violations

- [ ] C-02: Handler signatures match the contract in [AGENTS.md](AGENTS.md) C-02 (`async def handle_*(tenant, payload, settings, neo4j, redis)` or documented SDK handler shape)?
- [ ] C-03: All Neo4j queries include WHERE n.tenant_id = $tenant?
- [ ] C-04: No print() in app/ or engine/ (structlog only)?
- [ ] C-05: No Optional[, List[, Dict[ — use T or None, list[T], dict[K,V]?
- [ ] C-09: New env vars use L9_ prefix?
- [ ] C-12: No Field(alias=...) in Pydantic models?
- [ ] C-14: New ACTION_REGISTRY entry has handler + test in same PR?
- [ ] C-17: No camelCase Python field names?
- [ ] C-20: New template-managed files have L9_META header?

---

## Phase 3 — WARN: Code Quality

- [ ] All new public functions have type annotations and docstrings?
- [ ] No bare except: clauses?
- [ ] No pass or ... as function bodies in non-test, non-protocol files?
- [ ] No hardcoded magic numbers (use named constants)?
- [ ] structlog used correctly (key=value pairs, not positional args)?

---

## Phase 4 — VERIFY: Tests

- [ ] Tests added/updated for all changed logic?
- [ ] All tests have at least one pytest marker (unit, integration, slow)?
- [ ] Integration tests do not depend on external services without mocking?
- [ ] Coverage does not drop below 60%?

---

## Phase 5 — INFORM: PR-Type-Specific Checks

### New Feature PR
- [ ] T-tier assessed and appropriate reviewers assigned?
- [ ] New env vars documented in [`docs/contracts/config/env-contract.yaml`](docs/contracts/config/env-contract.yaml) and summarized in [CONFIG_ENV_CONTRACT.md](CONFIG_ENV_CONTRACT.md) / `.env.example`?
- [ ] New files listed in FILE_INDEX_FOR_AGENTS.md?

### Bug Fix PR
- [ ] Root cause identified in PR description?
- [ ] Regression test added for the exact failure case?

### Dependency Update PR
- [ ] License compatibility verified (no GPL-only deps in MIT-licensed module)?
- [ ] Import restriction compliance preserved (C-01 chassis boundary)?

### CI Workflow Change PR
- [ ] No merge-blocking gate converted to non-blocking without new WAIVER in CI_WHITELIST_REGISTER.md?

### Documentation-Only PR
- [ ] No doc changes contradict INVARIANTS.md rules?
- [ ] No doc changes contradict CONFIG_ENV_CONTRACT.md variable list?

### Config Change PR (pyproject.toml, .env.example)
- [ ] Ruff ignore list unchanged (INV-17)?
- [ ] New env vars follow L9_ prefix (INV-20)?
- [ ] Coverage threshold not lowered (INV-9)?

---

## Review Comment Templates

### Contract Violation
```
CONTRACT C-{N} VIOLATION — {rule-name}
File: {path} Line: {line}
Found: {offending_code}
Required: {corrected_code}
Evidence: [AGENTS.md](AGENTS.md) Forbidden Patterns / Architectural Contracts (C-{N})
```

### Tier Escalation Required
```
TIER ESCALATION — T{N} change requires {0/1/2} reviewer(s)
File: {path}
Reason: Modifying {file} is a T{N} operation per AGENTS.md Autonomy Tiers.
Action: Add [NEEDS-2-REVIEWERS] to PR title and request additional review.
```

### Non-Blocking Suggestion
```
SUGGESTION (non-blocking) — {title}
File: {path} Line: {line}
Consider: {suggestion}
Reference: {contract_or_invariant_id}
```

### Approve Comment
```
All 20 contracts verified — no violations found.
Tier assessment: T{N} — {0/1/2} reviewer(s) required.
make agent-check gates: [confirmed passing / please confirm before merge].
```
