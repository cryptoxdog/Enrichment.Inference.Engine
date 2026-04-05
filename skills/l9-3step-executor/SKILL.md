---
name: l9-3step-executor
description: >
  Determines the 3 highest-leverage next steps from current L9 RevOpsOS system state,
  sequences them into a dependency-correct execution plan respecting PacketEnvelope
  contracts and the ENRICH→GRAPH→ENRICH bidirectional loop, and generates all required
  files and changes in strict order. Invoked via /autonomous_skill_orchestrator.
argument-hint: "<system_state> block with BUILT, BLOCKED, MISSING, NOW_POSSIBLE, REPO, ARTIFACTS, GAPS"
allowed-tools:
  - Read
  - Write
  - Bash(find *)
  - Bash(cat *)
  - Bash(ls *)
  - Bash(grep *)
---

# L9 RevOpsOS — 3-Step Strategic Executor

## Input Contract

Require a single `<system_state>` block with all 7 fields present:

```text
<system_state>
BUILT: [what exists and works — include convergence loop status, registered inference rules, active PacketEnvelope enforcement]
BLOCKED: [what is stuck and why — reference gap numbers and severity tiers]
MISSING: [what does not exist yet — e.g., return channel, rule registry, audit pool]
NOW_POSSIBLE: [what was previously blocked but is now unlocked — e.g., Gap 1 closed → Gap 2 executable]
REPO: [current repo/file state summary across Enrichment.Inference.Engine, Cognitive.Engine.Graphs, Constellation.Gate.Node]
ARTIFACTS: [prior outputs, open PRs, deployed assets, gap-fix bundles]
GAPS: [open gap numbers with severity — e.g., Gap 2 🔴, Gap 5 🟠, Gap 6 🟡]
</system_state>
```

If `<system_state>` is absent, malformed, or any required field is missing, refuse execution immediately. Do not infer, backfill, summarize, or hallucinate state.

## L9 Architectural Invariants

- The ENRICH→GRAPH→ENRICH bidirectional loop is the primary system differentiator. Any step that does not advance loop closure, loop fidelity, or loop throughput ranks below any step that does.
- PacketEnvelope is the immutable inter-service contract. No step may emit or consume bare dicts across service boundaries.
- Schema discovery (SchemaProposal emission) is categorically different from field-filling. Steps that enable schema discovery outrank steps that fill known fields.
- All inference must execute through the DerivationGraph DAG engine (`inference_bridge_v2`). Any path through `inference_bridge` v1 is a defect, not a gap.
- Downstream services (SCORE, ROUTE, FORECAST, SIGNAL, HEALTH, HANDOFF) depend on ENRICH + GRAPH output fidelity. Steps that raise output fidelity unlock multiple downstream services and outrank isolated local improvements.

## Global Rules

- Single-path execution only. No branching, no alternatives, no “you could also.”
- Operate only in Layer 2 (ENRICH) or Layer 3 (GRAPH). Do not target Layer 1 infrastructure.
- No speculative expansion, cleanup, refactor, rename, abstraction, or opportunistic improvement.
- No placeholders, TODOs, pseudocode, dead paths, or partial implementations.
- Every generated output must be production-ready, import-resolved, testable, repo-aligned, and validated before being written.
- Every file must pass L9 contract validation before it is considered complete.

## Phase 0 — Locked Planning

Before writing any file:

1. Verify the current repo/file baseline from `REPO` and `ARTIFACTS`.
2. Verify current gap status from `BUILT`, `BLOCKED`, `MISSING`, `NOW_POSSIBLE`, and `GAPS`.
3. Build an atomic TODO map of every file to create or modify.
4. Confirm the TODO map stays within the intended execution scope.
5. If any ambiguity remains after reading the provided state, refuse execution.

Refuse immediately if:
- the target repo or path is ambiguous
- any prerequisite needed for a candidate step is absent from `BUILT`
- the TODO map would touch unplanned files
- fewer than 3 executable candidates exist after filtering

## Phase 1 — Select

1. Inventory `<system_state>` in this order: `BUILT` → `BLOCKED` → `MISSING` → `NOW_POSSIBLE` → `GAPS`.
2. Generate candidate next steps from the delta between current state and highest-value system outcomes.
3. Discard any candidate that does not directly advance the ENRICH↔GRAPH loop or a direct prerequisite of that loop.
4. Discard any candidate whose prerequisites are not explicitly present in `BUILT`.
5. Score each remaining candidate on 5 equally weighted axes:
   - **Immediate impact** — closes a 🔴 or 🟠 gap within this run
   - **Dependencies unlocked** — number of other gaps or downstream services unlocked
   - **Rework avoided** — prevents future work from being invalidated
   - **Execution readiness** — all prerequisites confirmed present
   - **Loop contribution** — direct contribution to ENRICH↔GRAPH loop closure
6. Apply this deterministic tiebreaker cascade:
   1. higher severity gap wins
   2. more downstream services unlocked wins
   3. lexicographic order on gap number wins
7. If fewer than 3 candidates survive, refuse execution and report the surviving count and reason.
8. Rank by composite score and select exactly 3 steps.

Output for each selected step:
- step name
- gap(s) closed
- why it wins now
- downstream services unlocked
- binary success criteria

## Phase 2 — Sequence

1. Analyze the 3 selected steps for:
   - dependency order
   - shared prerequisites
   - PacketEnvelope chain continuity
   - fail-fast risk reduction
   - loop proof value
2. Detect circular dependencies. If any cycle exists, refuse execution and report the cycle exactly.
3. Determine one exact execution sequence.
4. Define binary transition triggers between steps:
   - Step N must pass all success criteria
   - Step N must pass L9 contract validation
   - Step N+1 cannot begin until both are true
5. Record deferred items that scored but were not selected.

Output:
- ordered plan
- rationale for the order
- prerequisites per step
- workstreams per step
- validation criteria per step
- binary transition trigger per step
- deferred items

## Phase 3 — Execute

For each step in order:

1. Generate the smallest complete change set that closes the target gap.
2. Enforce these L9 contract checks on every generated file:
   - all inter-service payloads use PacketEnvelope
   - all inference routes through `inference_bridge_v2`
   - all convergence calls include `domain_spec`
   - all confidence values are per-field dicts, never a flat top-level float
   - all audit calls route through a wired `db_pool`
3. Validate the step against its binary success criteria.
4. Confirm the transition trigger before continuing.
5. Update carried-forward state:
   - append completed items to `BUILT`
   - remove closed items from `GAPS`
   - note newly unblocked downstream services
6. If validation fails, halt immediately. Do not execute Step N+1 and do not partially apply Step N+2.

Output per step:
- files generated or modified
- L9 contract check result
- validation result
- transition confirmation

Final output:
- execution summary
- full system-state delta
- updated `BUILT`
- updated `GAPS`
- newly unblocked downstream services

## Anti-Patterns — Reject on Sight

- selecting a step whose prerequisites are absent from `BUILT`
- introducing scope not present in `<system_state>`
- generating Step N+1 before Step N validates
- offering alternatives, commentary, or side paths
- unresolved import or broken reference in generated code
- bare dict emitted across any service boundary
- `from engine.inference_bridge import` or any v1 bridge import
- `convergence_controller.run(..., domain_spec=None)` or equivalent null-domain execution
- `confidence: float` without `per_field_confidence: dict`
- any generated file that touches Layer 1 infrastructure
- `db_pool=None` audit flows

## Refusal Conditions

Refuse execution if any of the following is true:

- `<system_state>` is incomplete
- fewer than 3 viable candidates survive filtering
- a selected candidate depends on a missing prerequisite
- a circular dependency exists in sequencing
- a required contract check cannot be satisfied
- execution scope expands beyond the requested change set

## Output Requirements

- Produce deterministic, enforceable outputs only.
- Do not create commentary, explanation, or extra plans outside the execution outputs.
- Keep all actions traceable to the supplied `<system_state>`.
- Halt instead of guessing.

## Validation Checklist

- `SKILL.md` parses as valid YAML frontmatter + Markdown body
- all 7 input fields are required
- all 3 phases are present
- all 5 L9 architectural invariants are present
- loop contribution is an explicit scoring axis
- tie handling is fully specified
- circular dependency refusal is explicit
- binary transition triggers are explicit
- halt behavior on failed validation is explicit
- anti-patterns cover: v1 bridge import, bare dict emission, flat confidence, null `domain_spec`, null `db_pool`
