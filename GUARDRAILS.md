# Guardrails — AI Safety Constraints

**LAST_REVIEWED:** 2026-04-11

## Enrichment Pipeline

### Prompt construction
- Prompts built via `app/services/prompt_builder.py` should require structured JSON-style output as appropriate for the schema in use.
- Do not inject unsanitized free-text CRM fields into LLM prompts; bound what goes into provider payloads.
- Keep provider payloads within configured timeouts and variation limits (`Settings` / request caps).

### Output validation
- Orchestrator path validates/normalizes via `app/services/validation_engine.py` (`validate_response`) and consensus logic in `app/services/consensus_engine.py` / `app/engines/enrichment_orchestrator.py`.
- Consensus and variation counts follow `Settings` and per-request fields (e.g. `default_max_variations`, `default_consensus_threshold`) — do not silently weaken thresholds in product code without review.

### Field writes (Odoo / CRM integrations)
- When writing back to CRM systems, use explicitly allowlisted fields and governance-approved code paths only.
- No elevated/sudo-style writes without documented human approval.
- Writes must follow validated enrichment outputs and tenant/data rules.

## API Security

### Authentication
- **Enrichment and other protected routes** require the `X-API-Key` flow documented in `app/core/auth.py` (hash compared to `API_KEY_HASH`). **Health and some metadata routes may be unauthenticated** by design — do not add sensitive data to those responses.
- API key material lives in env vars via pydantic-settings — never in source code or logs.

### Input validation
- Partner IDs must be validated against the database before enrichment
- Reject enrichment requests for partners outside the allowlisted domain

### Rate limits
- Concurrency and backoff are enforced in the enrichment / provider layers (`Settings.max_concurrent_variations`, circuit breaker, middleware) — preserve those bounds when changing orchestration.

## AI Agent Constraints

### What agents MAY do autonomously
- Add tests for existing behaviour
- Fix lint/type errors
- Improve docstrings
- Add new enrichment signal extractors (with tests)

### What agents MUST NOT do without human review
- Modify authentication or authorization logic
- Change the signal schema contract
- Modify `.github/workflows/`
- Change default consensus / variation / timeout defaults in `Settings` without review
- Add new external API integrations
- Modify CODEOWNERS, AGENTS.md, CLAUDE.md, or this file

## Secrets
- Zero hardcoded credentials — no exceptions
- `.env` is gitignored — `.env.example` contains only placeholder values
- Perplexity API key: `PERPLEXITY_API_KEY` env var only
- Never log API keys, partner data, or LLM responses at INFO level or above
