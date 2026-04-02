# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [governance]
# tags: [L9_TEMPLATE, agent, file-index, lookup]
# owner: platform
# status: active
# token_estimate: 1465
# ssot_for: [file-lookup, file-modification-rules, token-budgets]
# load_when: [new_file_creation, file_lookup, onboarding]
# references: [AGENT.md, REPO_MAP.md]
# --- /L9_META ---

# FILE_INDEX_FOR_AGENTS.md — File Lookup Index

**VERSION**: 2.0.0 | **SHA_BASELINE**: 358d15d | **LAST_REVIEWED**: 2026-04-01

---

## Bootstrap Reading Order (New Agent)

| Step | File | Tokens | Purpose |
|---|---|---|---|
| 1 | AGENT_BOOTSTRAP.md | ~520 | Context loading strategy |
| 2 | AGENT.md | ~2,075 | Contracts, tiers, gates, patterns |
| 3 | GUARDRAILS.md | ~600 | Hard prohibitions |
| 4 | ARCHITECTURE.md | ~800 | System topology |
| 5 | REPO_MAP.md | ~1,217 | File locations and module ownership |
| Total | | ~5,212 | 16% of 32K window |

---

## Governance Pack — Token Budget

| File | Est. Tokens | Load Priority |
|---|---|---|
| AGENT_BOOTSTRAP.md | ~520 | ALWAYS (first) |
| AGENT.md | ~2,075 | ALWAYS |
| CLAUDE.md | ~210 | Claude only |
| INVARIANTS.md | ~2,834 | On-demand |
| REPO_MAP.md | ~1,217 | Trigger: new file |
| EXECUTION_FLOWS.md | ~825 | Trigger: control flow |
| DEPENDENCY_SURFACE.md | ~1,171 | Trigger: dep change |
| CONFIG_ENV_CONTRACT.md | ~1,556 | Trigger: env vars |
| CI_WHITELIST_REGISTER.md | ~1,485 | Trigger: CI failure |
| AI_AGENT_REVIEW_CHECKLIST.md | ~1,570 | Always (PR review) |
| TROUBLESHOOTING.md | ~680 | Trigger: errors |
| .cursorrules (adjacent) | ~6,500 | Cursor/Copilot always |
| GUARDRAILS.md (adjacent) | ~600 | ALWAYS |
| Pack Total | ~16,354 | — |

---

## File Directory (Structured Lookup)

| Need | File | Section |
|---|---|---|
| What can I do without human review? | AGENT.md | Agent Autonomy Tiers |
| What is forbidden? | GUARDRAILS.md | What agents MUST NOT do |
| Which files can I never modify? | AGENT.md | Protected Files (T4/T5) |
| What are the 7 gates? | AGENT.md | Mandatory Pre-Commit Command |
| All env variables | CONFIG_ENV_CONTRACT.md | Environment Variables |
| Handler signature pattern | AGENT.md | C-02 |
| Canonical import patterns | AGENT.md | Canonical Import Patterns |
| Forbidden code patterns | AGENT.md | Forbidden Patterns |
| Module boundary rules | AGENT.md | C-01 |
| Directory structure | REPO_MAP.md | Directory Map |
| All invariants | INVARIANTS.md | INV-1 through INV-20 |
| CI gate details + waivers | CI_WHITELIST_REGISTER.md | Merge-Blocking Gates |
| Dependency versions | DEPENDENCY_SURFACE.md | Version Table |
| Runtime control flow | EXECUTION_FLOWS.md | Flows |
| Contract-invariant mapping | INVARIANTS.md | Contract to Invariant Cross-Reference |
| PR review process | AI_AGENT_REVIEW_CHECKLIST.md | Phase 1-5 |
| Review comment templates | AI_AGENT_REVIEW_CHECKLIST.md | Review Comment Templates |
| Test marker requirements | INVARIANTS.md | INV-18 |
| Error/failure flows | EXECUTION_FLOWS.md | Failure Flows |
| Startup failure diagnosis | TROUBLESHOOTING.md | Startup Failures |
| Common agent mistakes | TROUBLESHOOTING.md | Common Agent Mistakes |

---

## File Modification Rules

### NEVER Modify Without T4/T5 Human Review
- app/engines/chassis_contract.py
- app/engines/handlers.py
- app/engines/graph_sync_client.py
- app/models/ (any file)
- kb/ (any rule file)
- .github/workflows/ (any workflow)
- GUARDRAILS.md, AGENTS.md, CLAUDE.md
- Dockerfile, docker-compose.yml, docker-compose.prod.yml

### ALWAYS Create With L9_META Header
Files managed by L9 templates must include the L9_META header block. Copy from any existing file in app/ or tools/.

### Safe to Modify at T1/T2
- tests/ (all test files)
- docs/ (documentation)
- tools/audit_engine.py, tools/verify_contracts.py (with T2 PR)
- README.md, CHANGELOG.md
- .env.example (never .env itself)

---

## Generated / Artifact Files (Do Not Edit Directly)

| File | Generator | Purpose |
|---|---|---|
| coverage.xml | pytest --cov-report=xml | CI coverage report |
| htmlcov/ | pytest --cov-report=html | Human-readable coverage |
| sbom.spdx.json | anchore/sbom-action | Software Bill of Materials |
| scorecard.sarif | ossf/scorecard-action | OpenSSF scorecard |
| reports/ | Various tools | Audit and scan reports |

---

## Undiscovered Files Protocol

If you encounter a file not listed in this index:
1. Check if it has an L9_META header — if yes, treat as governed code.
2. Check REPO_MAP.md for its directory ownership tier.
3. Apply the most restrictive tier for the containing directory until confirmed otherwise.
4. File a GitHub issue with label docs-gap to add it to this index.
