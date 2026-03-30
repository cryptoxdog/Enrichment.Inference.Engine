# CODEX PROMPT (STRICT)

## Cursor (C) — Odoo 19 Compliance Audit + Repo-Wide Remediation

---

## OBJECTIVE

Use Odoo 19 official documentation (`@Odoo_19`) as the authoritative reference to execute a full repository audit and remediation pass.

Goal:

* Identify all non–Odoo 19 compliant code patterns
* Replace them with Odoo 19 native equivalents
* Ensure all modules load successfully
* Ensure modules behave as designed (no unintended semantic drift)

---

## SCOPE

* Entire repository (all modules, all Python, all XML, all JS, all manifest files)
* All custom modules (`plasticos_*`, any legacy `plasticos_*`)
* All migrations and hooks
* All data/seed XML
* All views/templates/security definitions

---

## REQUIRED INPUTS

* `@Odoo_19` documentation (must be read first)
* Repo index artifacts under `reports/repo-index/` (if available)
* Git working tree access (prefer git grep, git diff)
* Current install logs / error traces (if present)

---

## EXECUTION REQUIREMENTS

### STEP 0 — DOC PRIMING (MANDATORY)

Read and cache relevant Odoo 19 pages from `@Odoo_19`:

* ORM API changes
* Model constraints (Constraint definitions)
* Field definitions + compute/onchange patterns
* Manifest conventions
* Security (access rules, record rules, groups)
* XML data loading rules + external IDs
* Views + QWeb syntax changes
* Cron/jobs
* Tests framework + tagging
* Migration guidelines

Output:

```
DOC_PRIMED: true
DOC_TOPICS: [list]
```

---

### STEP 1 — REPO-WIDE PATTERN AUDIT

Search repo for deprecated / non-native patterns including (not limited to):

* `_sql_constraints`
* legacy API decorators / patterns
* deprecated context usage
* invalid field params
* legacy view inheritance syntax
* broken external ID patterns
* unsafe XML `noupdate` usage
* outdated security definitions
* manifest incompatibilities
* deprecated JS/QWeb directives

Build an issue catalog:

```
ISSUE_CATALOG:
  - issue_type:
    occurrences:
    files:
    severity: [BLOCKER|WARNING]
    odoo19_reference:
```

---

### STEP 2 — REMEDIATION PATCHES

For each issue type:

* Apply Odoo 19 native replacement
* Preserve semantic behavior
* Avoid schema drift unless explicitly required for compliance
* Avoid introducing new models unless unavoidable
* Normalize namespace to `plasticos_*` where applicable
* Resolve external ID collisions deterministically

Generate unified diff patches per issue class.

---

### STEP 3 — LOADABILITY + INTEGRITY VALIDATION

Validate that:

* Registry loads
* All modules install on fresh DB
* Upgrade path does not break migrations
* No external ID model collisions remain
* No duplicated models introduced
* No duplicate external IDs introduced
* All views render
* Security loads without access errors

Output:

```
VALIDATION:
  registry_load: PASS|FAIL
  fresh_install: PASS|FAIL
  upgrade_install: PASS|FAIL
  external_id_integrity: PASS|FAIL
  namespace_integrity: PASS|FAIL
```

---

## CONSTRAINTS

* Odoo 19 documentation is the source of truth.
* Replace non-native patterns rather than patch around them.
* Do not change business logic unless required to restore designed behavior.
* No manual UI steps.
* Fix root causes globally (repo-wide), not one-off.
* Prefer git-based search and patching.

---

## FAILURE CONDITIONS (REPORT, DO NOT HIDE)

If any remediation cannot be completed deterministically:

Output:

```
BLOCKER:
  issue_type:
  file:
  reason:
  required_action:
  suggested_patch:
```

Continue auditing remaining issues.

---

## EXPECTED OUTPUT

1. `DOC_PRIMED` declaration
2. Full `ISSUE_CATALOG`
3. Unified diff patches grouped by issue type
4. `VALIDATION` matrix
5. List of remaining blockers (if any)

---

## END_STATE

```
