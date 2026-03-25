
# Odoo Workspace Kernel v2 — Deterministic + Repo + Doc Verified

## Kernel ID

`workspace.odoo19.repo_doc_verified.v1`

---

## ACTIVATION REQUIREMENTS

This kernel is ACTIVE by default.

Before any code generation, the agent MUST:

1. Authenticate GitHub MCP.
2. Locate target repo + branch.
3. Attempt recursive tree enumeration.
4. Build module registry index (manifests + models + XML).
5. Scan for existing external IDs.
6. Detect namespace usage.
7. Read relevant Odoo 19 documentation pages:

   * ORM reference
   * Constraints
   * Manifest format
   * Security
   * Views
   * Testing
   * Migration notes
8. Validate against Odoo 19 migration matrix .
9. Cross-check ontology boundaries .
10. Validate compatibility with existing workspace capsule .
11. Confirm compatibility with migration test expectations .

If any step fails → ABORT.

No partial compliance allowed.

---

## REPO INDEXING MODE

If full tree access available:

* Build complete model registry map.
* Build external ID registry map.
* Detect namespace drift.
* Detect duplicate model definitions.

If recursive tree access unavailable:

* Switch to branch-isolated generation mode.
* Create new feature branch.
* Generate module in isolation.
* Let PR diff reveal collisions.
* Do not guess existing XML IDs.

If neither possible → ABORT.

---

## DOCUMENTATION INVARIANT

Before generating code:

Agent must confirm reading relevant pages at:
[https://www.odoo.com/documentation/19.0/]

Specifically:

* ORM API changes
* Constraint syntax
* Testing patterns
* Manifest structure
* Security groups
* Field renames
* XML view changes

Code must reflect documented behavior.

If documentation cannot be accessed → ABORT.

---

## ODOO 19 HARD RULES

Enforce migration reference :

* No `_sql_constraints = []` lists.
* Use `models.Constraint`.
* No deprecated field names.
* No `self._context`.
* Use `self.env.context`.
* Correct `group_ids`.
* Correct `product_uom_id`, `tax_ids`.
* Use correct cursor fetch pattern.
* Use updated QWeb syntax.

Any violation → ABORT.

---

## ONTOLOGY BOUNDARY ENFORCEMENT

Layer rules per ontology map :

Material:
* Identity only.
Capability:
* Mechanical only.
Commercial:
* Economic only.
Compliance:
* Gating only.
Transaction:
* Accounting spine only.
Cross-layer contamination → ABORT.

---

## MIGRATION TEST COMPATIBILITY

Generated code must not break deterministic migration tests :

* Idempotent behavior.
* Replay safety.
* Closed transaction immutability.
* Margin integrity.
* Dry-run mode integrity.
* Deterministic partner + product resolution.

If new code risks breaking test suite → ABORT.

---

## SEED DETERMINISM RULE

All seed data must:

* Be XML-only.
* Use stable external IDs.
* Be idempotent.
* Use correct noupdate discipline.
* Emit 100% of CSV embedded values.
* Avoid duplication.
* Avoid runtime file reads.
* Avoid Python bootstrap logic.

If any populated CSV value not emitted → ABORT.

---

## NAMESPACE POLICY

Allowed prefix:
`plasticos_*`

Disallowed:
`plasticos_*`

Mixed usage → ABORT.

---

## QUALITY STANDARD

Top Frontier AI Lab requirements:

* Enterprise-grade
* Production-ready
* Repo-aligned
* Deterministic
* Odoo 19 compliant
* Ontology-aligned
* Idempotent
* Upgrade-safe
* Fail-closed

No speculative code.
No best-guess scaffolding.
No partial implementation.

---

## EXECUTION ORDER BEFORE CODE

1. Repo index
2. Doc review
3. Migration validation
4. Ontology validation
5. Namespace validation
6. Seed determinism validation
7. Test compatibility validation
8. Only then generate code

---

## ABORT CONDITIONS

* Repo not indexable
* Documentation not accessible
* Namespace drift detected
* Duplicate model risk
* Duplicate XML ID risk
* Layer boundary violation
* Odoo 19 deprecation detected
* Migration tests at risk
* Runtime file reads detected
* Boolean explosion detected
* Non-idempotent seed logic detected

Abort state must be explicit.

---

## END CONDITION

When all invariants satisfied:

```
ODOO19_REPO_DOC_VERIFIED_READY_FOR_CODE
```

---