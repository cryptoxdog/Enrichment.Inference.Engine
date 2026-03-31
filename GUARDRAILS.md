# Guardrails — AI Safety Constraints

## Enrichment Pipeline

### Prompt construction
- All prompts to Perplexity must include: `"Return strictly valid JSON only."`
- Partner name and country are the only fields injected into prompts — no free-text field values
- Never inject raw CRM field content into LLM prompts without sanitization
- Prompt length cap: 2,000 tokens

### Output validation
- All LLM responses MUST pass `ExtractionEngine.validate()` before use
- Minimum valid responses required before synthesis: 2 (configurable via `MIN_VALID`)
- Synthesis threshold: 0.6 weighted confidence (cross-source agreement × avg confidence)
- Never write to partner fields unless `synthesis["confidence"] >= 0.5`

### Field writes
- Only write to explicitly allowlisted fields: `x_material_grade`, `x_material_tier`, `x_enrichment_confidence`
- Use `partner.write({...})` — never `partner.sudo().write({...})` without documented justification
- All field writes must be preceded by a schema-valid synthesis result

## API Security

### Authentication
- All endpoints require authentication — no anonymous enrichment triggers
- API keys stored in env vars via pydantic-settings — never in source code or logs

### Input validation
- Partner IDs must be validated against the database before enrichment
- Reject enrichment requests for partners outside the allowlisted domain

### Rate limits
- Perplexity concurrency: max 3 simultaneous requests per enrichment run (semaphore)
- Retry limit: 3 attempts with exponential backoff + jitter
- Per-partner enrichment cooldown: 24 hours (prevent redundant API spend)

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
- Change synthesis threshold or MIN_VALID constants
- Add new external API integrations
- Modify CODEOWNERS, AGENTS.md, CLAUDE.md, or this file

## Secrets
- Zero hardcoded credentials — no exceptions
- `.env` is gitignored — `.env.example` contains only placeholder values
- Perplexity API key: `PERPLEXITY_API_KEY` env var only
- Never log API keys, partner data, or LLM responses at INFO level or above
