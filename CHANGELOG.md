# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `odoo_modules/plasticos_research_enrichment/` — Odoo module v19.0.2.0.0 with async
  Perplexity enrichment pipeline, entropy engine, synthesis engine, and inference bridge
- Repo foundation files: LICENSE, CHANGELOG, SECURITY, GUARDRAILS, ARCHITECTURE, TESTING

---

## [2.2.0] — 2026-03-30

### Added
- Universal domain-aware entity enrichment API (Salesforce + Odoo single ingress)
- Convergence controller with confidence tracking and cost tracking
- N-ary inference engine with rule engine and grade engine
- GDS scheduler integration
- OpenTelemetry instrumentation (OTLP/gRPC export)
- Waterfall enrichment pipeline with auto-register
- Schema proposer and uncertainty engine

### Changed
- Migrated to pydantic-settings v2
- Upgraded to FastAPI 0.115+

---

## [2.0.0] — 2026-01-15

### Added
- Initial enrichment orchestrator
- Perplexity sonar-reasoning integration
- Redis caching layer
- Graphiti knowledge graph sync client
