# AI_AGENT_REVIEW_CHECKLIST.md

## Purpose
Checklist for AI agents (CodeRabbit, Qodo, Claude, GitHub Copilot) when reviewing PRs or generating code.

## Scope
Code review, PR comments, code generation guidance

## Source Evidence
- `.cursorrules` (20 contracts)
- `.github/workflows/compliance.yml`
- `.github/workflows/ci.yml`
- `INVARIANTS.md`

## Pre-Review: Context Gathering

### [ ] Read PR Description
- What is the stated goal?
- What contract(s) might be affected?
- Are tests included?

### [ ] Identify Changed Files
- Which modules modified? (app/, engine/, tests/, etc.)
- Any new files created?
- Any deleted files?

### [ ] Check File Paths
- New top-level directory? → Flag (INVARIANT 16)
- Engine code in app/? → Flag (boundary violation)
- Test code in app/? → Flag (wrong location)

## Contract Violations (20 Contracts from .cursorrules)

### CONTRACT 1: Single HTTP Ingress
- [ ] Are new HTTP endpoints added? (allowed: POST /v1/execute, GET /v1/health only)
- [ ] Does engine/ import FastAPI/Starlette? (forbidden except app/api/, app/main.py, handlers.py)

### CONTRACT 2: Handler Interface
- [ ] Are handlers following signature: `async def handle_<action>(tenant: str, payload: dict) -> dict`?
- [ ] Is registration in engine/handlers.py via `chassis.router.register_handler()`?

### CONTRACT 3: Tenant Isolation
- [ ] Is tenant resolution happening in engine code? (forbidden, chassis-only)
- [ ] Are Neo4j queries scoped to tenant database?

### CONTRACT 4: Observability
- [ ] Is structlog.configure() called in engine/? (forbidden, chassis-only)
- [ ] Is logging.basicConfig() called in engine/? (forbidden, chassis-only)
- [ ] Are loggers using `structlog.get_logger(__name__)`?

### CONTRACT 6: PacketEnvelope Protocol
- [ ] Are inter-service payloads using PacketEnvelope?
- [ ] Is inflate_ingress() used at boundary entry?
- [ ] Is deflate_egress() used at boundary exit?

### CONTRACT 7: Immutability
- [ ] Is PacketEnvelope being mutated directly? (forbidden, use .derive())
- [ ] Are new packets created via .derive() or PacketEnvelope.create()?

### CONTRACT 9: Cypher Injection Prevention
- [ ] Are Cypher labels/types using sanitize_label()?
- [ ] Are Cypher values parameterized ($batch, $query)?
- [ ] Are there f-string Cypher queries without sanitize_label()? (SEC-001)

### CONTRACT 12: Domain Spec Source of Truth
- [ ] Is YAML being accessed directly? (forbidden, use DomainPackLoader → DomainConfig)
- [ ] Are raw dicts used instead of Pydantic models?

### CONTRACT 18: L9_META Headers
- [ ] Do new files have L9_META headers?
- [ ] Are headers injected via tools/l9_meta_injector.py?

## Banned Patterns (Contract Scanner)

### CRITICAL (Merge-Blocking)
- [ ] SEC-001: f-string Cypher MATCH without sanitize_label()
- [ ] SEC-002: eval()
- [ ] SEC-003: exec()
- [ ] SEC-006: pickle.load(s)
- [ ] SEC-007: yaml.load() without SafeLoader
- [ ] ARCH-001: from fastapi import (in engine/)
- [ ] ARCH-002: from starlette import (in engine/)
- [ ] DEL-001: httpx.post/get/etc (in engine/)
- [ ] STUB-001: raise NotImplementedError (outside tests/)

### HIGH (Merge-Blocking)
- [ ] ERR-001: bare except:
- [ ] ERR-002: except + pass (swallowed exception)
- [ ] OBS-001: structlog.configure() (in engine/)
- [ ] OBS-002: logging.basicConfig() (in engine/)

## Code Quality

### Type Hints
- [ ] All function signatures have type hints?
- [ ] Class attributes have type hints?
- [ ] Are `list[T]`, `dict[K,V]` used (not `List[T]`, `Dict[K,V]`)?

### Pydantic Models
- [ ] All structured data uses Pydantic v2 BaseModel?
- [ ] Are models frozen where appropriate?
- [ ] No Field(alias=...) usage?

### Logging
- [ ] Are print() statements removed? (forbidden in app/, engine/)
- [ ] Is structlog.get_logger(__name__) used?
- [ ] Do log statements include tenant, trace_id context?

### Naming Conventions
- [ ] snake_case for all identifiers?
- [ ] No camelCase or PascalCase (except class names)?

## Testing

### Test Presence
- [ ] Are new features covered by unit tests?
- [ ] Are new handlers covered by integration tests?
- [ ] Are architecture contracts covered by compliance tests?

### Test Markers
- [ ] Do tests have markers (@pytest.mark.unit, .integration, .slow)?
- [ ] Are unit tests in tests/unit/?
- [ ] Are integration tests in tests/integration/?
- [ ] Are compliance tests in tests/compliance/?

### Test Quality
- [ ] Do tests mock external services (not Neo4j)?
- [ ] Do integration tests use testcontainers-neo4j?
- [ ] Are tests isolated (no shared state)?

## Documentation

### Code Comments
- [ ] Are complex algorithms explained?
- [ ] Are contract citations included (e.g., "# CONTRACT 9: Cypher injection prevention")?

### PR Description
- [ ] Does it explain what changed?
- [ ] Does it reference relevant contracts/invariants?
- [ ] Does it include `make agent-check` confirmation?

## CI Awareness

### Pre-Commit
- [ ] Will `make agent-check` pass? (7 gates)
- [ ] Are there obvious lint errors?
- [ ] Are there obvious type errors?

### CI Workflows
- [ ] Will validate job pass? (Python syntax, YAML validation)
- [ ] Will lint job pass? (ruff, mypy)
- [ ] Will semgrep job pass? (policy rules)
- [ ] Will test job pass? (pytest with coverage ≥60%)
- [ ] Will compliance job pass? (terminology, chassis isolation, KB schema)

## Review Comments

### When Flagging Issues
- [ ] Cite specific contract number (CONTRACT 1-20)
- [ ] Cite specific invariant (INVARIANT 1-20)
- [ ] Cite specific banned pattern (SEC-001, ARCH-001, etc.)
- [ ] Provide exact file path + line number
- [ ] Suggest specific fix

### When Approving
- [ ] All contracts verified compliant
- [ ] All invariants upheld
- [ ] No banned patterns detected
- [ ] Tests present and sufficient
- [ ] CI will pass

## Agent-Specific Guidance

### CodeRabbit
- Focus on contract violations, banned patterns
- Use structured review format
- Cite exact rule violations

### Qodo
- Focus on test coverage, edge cases
- Suggest test scenarios
- Verify test markers

### Claude
- Provide comprehensive analysis
- Explain contract rationale
- Suggest architectural improvements

### GitHub Copilot
- When generating code: follow handler signature patterns
- When suggesting completions: avoid banned patterns
- Respect import restrictions per module
