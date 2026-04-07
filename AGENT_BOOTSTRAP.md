# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, bootstrap, entrypoint]
# owner: platform
# status: active
# token_estimate: 520
# ssot_for: [agent-onboarding, context-loading-strategy, reading-order]
# load_when: [first_load, agent_init, new_agent]
# --- /L9_META ---

# AGENT_BOOTSTRAP.md — Enrichment.Inference.Engine

**VERSION**: 1.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

> **FIRST FILE TO LOAD.** Every agent reads this before anything else.

---

## What This Repo Is

Universal domain-aware entity enrichment API.
Stack: Python 3.12 / FastAPI chassis / Engine layer / Perplexity LLM / Neo4j graph / Redis cache / PostgreSQL state.

---

## Context Loading by Agent Type

### Coding Agent (Cursor / GitHub Copilot)

| Priority | File | Tokens | Load When |
|---|---|---|---|
| ALWAYS | AGENT.md | ~2,075 | Every session |
| ALWAYS | .cursorrules | ~6,500 | Every session |
| TRIGGER | REPO_MAP.md | ~1,217 | Creating a new file |
| TRIGGER | CONFIG_ENV_CONTRACT.md | ~1,556 | Touching env vars |
| TRIGGER | DEPENDENCY_SURFACE.md | ~1,171 | Adding/changing deps |

**Max budget: ~12,519 tokens (39% of 32K window)**

### Code Review Agent (CodeRabbit / Qodo)

| Priority | File | Tokens | Load When |
|---|---|---|---|
| ALWAYS | AI_AGENT_REVIEW_CHECKLIST.md | ~1,570 | Every PR |
| ALWAYS | AGENT.md | ~2,075 | Every PR |
| TRIGGER | CI_WHITELIST_REGISTER.md | ~1,485 | CI failure in PR |
| TRIGGER | DEPENDENCY_SURFACE.md | ~1,171 | Dep changes in PR |

**Max budget: ~7,766 tokens (24% of 32K window)**

### Claude Code (Refactoring / Architecture)

| Priority | File | Tokens | Load When |
|---|---|---|---|
| ALWAYS | AGENT.md | ~2,075 | Every session |
| ALWAYS | GUARDRAILS.md | ~600 | Every session |
| ALWAYS | ARCHITECTURE.md | ~800 | Every session |
| TRIGGER | EXECUTION_FLOWS.md | ~825 | Modifying control flow |
| TRIGGER | INVARIANTS.md | ~2,834 | Architectural questions |
| TRIGGER | CONFIG_ENV_CONTRACT.md | ~1,556 | Env/config changes |

**Max budget: ~10,843 tokens (34% of 32K window)**

---

## Bootstrap Reading Order (New Agent, First Session)

1. **This file** — context loading strategy (~520 tok)
2. **AGENT.md** — contracts, autonomy tiers, gate sequence (~2,075 tok)
3. **GUARDRAILS.md** — hard prohibitions (~600 tok)
4. **ARCHITECTURE.md** — system topology (~800 tok)
5. **REPO_MAP.md** — file locations and module ownership (~1,217 tok)

**Total bootstrap: ~5,212 tokens (16% of 32K window)**

---

## Three Rules Every Agent Must Know

1. **Run `make agent-check` before every commit** — all 7 gates must pass.
2. **Respect your Tier** — see AGENT.md Agent Autonomy Tiers. T4/T5 changes require human review.
3. **AGENT.md is law** — if you see a conflict between two documents, AGENT.md wins.

---

## Known-Unknown Protocol

If a rule references a tool or invariant marked "Unknown" or "if exists":
1. Log `structlog.warning(event="known_unknown", target="<tool_or_rule>")`
2. Skip the step
3. Add a comment to the PR body: `KNOWN UNKNOWN: <target> — skipped`
4. Do NOT treat it as a contract violation

---

## Quick Reference Table

| Question | File | Section |
|---|---|---|
| What can I do without human review? | AGENT.md | Agent Autonomy Tiers |
| What is forbidden? | GUARDRAILS.md | What agents MUST NOT do |
| Which files can I never modify? | AGENT.md | Protected Files (T4/T5) |
| What are the 7 gates? | AGENT.md | Mandatory Pre-Commit Command |
| Where is file X? | FILE_INDEX_FOR_AGENTS.md | File Directory |
| What invariants exist? | INVARIANTS.md | INV-1 through INV-20 |
| What CI checks run? | CI_WHITELIST_REGISTER.md | Merge-Blocking Gates |
| What are the env vars? | CONFIG_ENV_CONTRACT.md | Environment Variables |
| How do I fix a startup failure? | TROUBLESHOOTING.md | Startup Failures |
