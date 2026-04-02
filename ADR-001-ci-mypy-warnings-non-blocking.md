# ADR-001: Mypy Warnings Non-Blocking in CI

## Status
Accepted

## Context
The CI pipeline runs `mypy app` as part of the lint job. Mypy is a static type checker that can detect type errors in Python code.

**Current behavior:**
```yaml
- name: Run Mypy Type Checker
  run: |
    echo "Running type checks..."
    mypy ${{ env.SOURCE_DIR }} \
      --show-error-codes \
      --pretty \
      --install-types \
      --non-interactive \
      --ignore-missing-imports \
      || echo "⚠️  Type check warnings (non-blocking)"
```

**Evidence:** `.github/workflows/ci.yml` lines 201-210

## Decision
Mypy warnings are **non-blocking** in the CI pipeline.

- Mypy can fail (non-zero exit code) without failing the CI job
- The step continues with an informational message
- The lint job succeeds even if mypy finds type errors
- The ci-gate job (which depends on lint) allows merge to proceed

## Rationale

### 1. Type Hints Are Gradual
Python's type system is gradual — type hints can be added incrementally. Strict mypy enforcement would block all PRs that touch untyped code, creating a chicken-and-egg problem.

### 2. Third-Party Library Stubs
Many dependencies lack complete type stubs. `--ignore-missing-imports` helps but doesn't eliminate all issues. Blocking on this would prevent use of otherwise-valid libraries.

### 3. Pydantic v2 Runtime Behavior
Some Pydantic v2 validators require runtime imports (not typing-only). The `TC001`, `TC002`, `TC003` ruff ignores exist for this reason. Mypy's static analysis can't always infer these runtime needs correctly.

### 4. Aspirational Type Checking
Mypy with `--strict` is aspirational — it guides developers toward better-typed code without blocking progress. Warnings inform but don't prevent merge.

### 5. Developer Workflow
Developers can run `mypy app` locally to fix issues before pushing. The CI warning serves as a reminder, not a blocker.

## Consequences

### Positive
- PRs can merge even with type warnings
- Incremental type coverage improvement possible
- No sudden CI failures from upstream library type changes
- Developer friction reduced

### Negative
- Type errors can slip into main branch
- No hard enforcement of type coverage
- Manual code review must catch type issues

## Compliance

### Related CI Waivers
- **WAIVER-001:** Mypy Type Check Warnings (documented in `CI_WHITELIST_REGISTER.md`)

### Related Invariants
- **INVARIANT 11:** Python Version Constraint (3.12+, use modern type syntax)
- **INVARIANT 17:** Ruff Ignore List Immutability (TC001-TC003 for Pydantic runtime)

### Scanner Rules
None — mypy is informational, no contract scanner rule exists

## Alternatives Considered

### Alternative 1: Strict Mypy Enforcement
**Rejected:** Would block 90%+ of PRs until entire codebase is fully typed. Impractical for current state.

### Alternative 2: Mypy Coverage Threshold
**Rejected:** No reliable way to measure "type coverage %" in mypy. Would require custom tooling.

### Alternative 3: Per-File Mypy Enforcement
**Rejected:** Complex to configure, hard to maintain, creates inconsistent developer experience.

## Enforcement

### CI Pipeline
- Mypy runs in lint job (`.github/workflows/ci.yml`)
- Warnings logged, job continues
- ci-gate allows merge if lint job succeeds

### Pre-Commit
- `make agent-check` includes `mypy app` (gate 3 of 7)
- Pre-commit hook can catch errors locally
- Developers can fix before pushing

### Code Review
- Human reviewers should note type issues
- Comment on PRs with significant type problems
- Request fixes for critical type errors

## References
- `.github/workflows/ci.yml` (SHA: 028e64cfd5c584ba850cd6330c528c2b8a09b44e)
- `.cursorrules` CONTRACT 4 (observability, structlog usage)
- `pyproject.toml` [tool.mypy] configuration
- `CI_WHITELIST_REGISTER.md` WAIVER-001
