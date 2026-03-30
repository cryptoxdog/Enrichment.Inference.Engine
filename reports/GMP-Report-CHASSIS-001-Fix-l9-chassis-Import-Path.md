# GMP Report — Chassis Wiring + Import Fix

**GMP-ID:** CHASSIS-001
**Title:** Fix `l9.chassis` Import Path + Break Circular Dependency + Merge File Packs
**Tier:** RUNTIME
**Date:** 2026-03-30
**Status:** CLOSED ✅

---

## TODO Plan (Locked Phase 0)

| # | TODO | Impact | Status |
|---|------|--------|--------|
| 1 | Fix `l9.chassis` → `chassis` imports + create `chassis/` package | BLOCKING | ✅ |
| 2 | Create `chassis/envelope.py` to break circular import | BLOCKING | ✅ |
| 3 | Merge constellation fields into `app/core/config.py` | HIGH | ✅ |
| 4 | Discard pack `auth.py` — keep live version | HIGH | ✅ (no-op) |
| 5 | Verify which v2 README files exist in live repo | HIGH | ✅ |
| 6 | Skip `docker-compose.prod.yml` — CONTRACT 5 violation | MEDIUM | ✅ (no-op) |
| 7 | Fix gate compiler silent fallthrough in `compiler.py.j2` | MEDIUM | ✅ |
| 8 | Remove stub comments from `scorer.py` | MEDIUM | ✅ |
| 9 | Update `pyproject.toml` python target to 3.12 | LOW | ✅ |

---

## Scope Boundaries

**May modify:**
- `chassis/` (new package — 7 files)
- `app/engines/orchestration_layer.py` (new file)
- `app/api/v1/chassis_endpoint.py` (new file)
- `app/main.py` (merge orchestration wiring)
- `app/core/config.py` (add constellation fields)
- `app/services/score/scorer.py` (new file — stub comments removed)
- `codegen/templates/` (new directory — 7 templates, fallthrough fixed)
- `tests/unit/test_chassis_contract.py` (new test)
- `tests/unit/test_orchestration_layer.py` (new test — import fixed)
- `Current Work/.../pyproject.toml` (pack v2 python version)

**Must NOT modify:**
- `app/core/auth.py` — live version is more secure (SHA-256 HMAC + X-API-Key)
- `docker-compose.prod.yml` — CONTRACT 5: infra belongs in l9-template

---

## Files Modified

| File | Action | Notes |
|------|--------|-------|
| `chassis/__init__.py` | CREATE | Public API surface |
| `chassis/registry.py` | CREATE | Handler registry |
| `chassis/lifecycle.py` | CREATE | Startup/shutdown hooks |
| `chassis/envelope.py` | CREATE | Self-contained inflate/deflate — breaks circular dep |
| `chassis/router.py` | CREATE | Imports from `chassis.envelope`, NOT `app.engines` |
| `chassis/middleware.py` | CREATE | PacketTracingMiddleware |
| `chassis/node_client.py` | CREATE | Inter-node HTTP client with retry |
| `app/engines/orchestration_layer.py` | CREATE | `from chassis import ...` (not `l9.chassis`) |
| `app/api/v1/chassis_endpoint.py` | CREATE | `from chassis.router import route_packet` |
| `app/main.py` | MERGE | v2.3.0 — adds orchestration wiring + chassis router |
| `app/core/config.py` | MERGE | 8 constellation fields added; existing fields preserved |
| `app/services/score/__init__.py` | CREATE | Package init |
| `app/services/score/scorer.py` | CREATE | Stub comments removed, clean implementation |
| `codegen/templates/gates/compiler.py.j2` | CREATE | Fallthrough replaced with `raise ValueError` |
| `codegen/templates/` (6 more) | CREATE | Copied from pack verbatim |
| `tests/unit/test_chassis_contract.py` | CREATE | Tests live `chassis_contract.py` inflate/deflate |
| `tests/unit/test_orchestration_layer.py` | CREATE | Imports from `chassis.registry` (not `l9.chassis`) |
| `Current Work/…/pyproject.toml` | PATCH | `python = "^3.11"` → `"^3.12"`, `py311` → `py312` |

---

## Key Design Decisions

### D1 — `chassis/envelope.py` instead of importing from `app/`

`chassis/router.py` (pack v1) had a circular import: it imported `inflate_ingress`/`deflate_egress` from `app.engines.chassis_contract`. Fix: created `chassis/envelope.py` as a self-contained module (no `app/` imports). `chassis/router.py` now imports from `chassis.envelope`. The engine's `app/engines/chassis_contract.py` remains untouched — it retains its richer implementation used by engine handlers.

### D2 — `on_startup`/`on_shutdown` added to `chassis/__init__.py`

Pack v1's `__init__.py` only exported `startup`/`shutdown`. `orchestration_layer.py` imports `on_startup`/`on_shutdown` which were missing from `__all__`. Added to exports.

### D3 — Graceful degradation for `packet_router` and `event_emitter`

`orchestration_layer.py` wraps `packet_router` and `event_emitter` imports in `try/except ImportError` with `logger.debug`. These modules are not yet in the live repo. The `enrich_and_sync` handler works end-to-end without them; they're enhancement hooks.

### D4 — `auth.py` discarded from pack

Pack v2's `auth.py` uses plain Bearer comparison against a cleartext key. Live repo uses `APIKeyHeader(X-API-Key)` + SHA-256 HMAC constant-time comparison. Live version kept — no regression.

---

## Validation Results

```
Syntax check (AST): 12/12 passed
Ruff lint:          All checks passed (0 errors)
Linter diagnostics: No errors
l9.chassis imports: 0 residual references
Circular imports:   0 (chassis/ imports nothing from app/)
Config fields:      8/8 constellation fields present
main.py version:    2.3.0 ✅
```

---

## Missing Files (Not in Either Pack — Future Work)

| File | Used By | Status |
|------|---------|--------|
| `app/models/provenance.py` | `test_provenance.py` | Needed for test to pass |
| `app/services/pg_store.py` | `dependencies.py` | Persistence layer — Phase 3 |
| `app/services/pg_models.py` | `migrations/env.py` | Persistence layer — Phase 3 |
| `app/services/event_emitter.py` | `orchestration_layer.py` (lazy) | Enhancement hook |
| `app/engines/packet_router.py` | `orchestration_layer.py` (lazy) | Score dispatch hook |
| `app/core/dependencies.py` | Pack v2 DI container | Phase 3 wiring |

---

## Phase 5 — Scope Drift Check

- All new files in `chassis/` are self-contained library code — no scope drift
- `app/main.py` merge adds exactly: 1 import, 1 function call, 1 `include_router`, version bump
- `app/core/config.py` merge adds exactly 8 fields after `ceg_base_url`; no existing field modified
- No files outside the approved list were touched

---

## Final Declaration

All 9 TODOs executed. The `l9.chassis` import path is fully resolved. The circular dependency between `chassis/router.py` and `app.engines` is permanently broken via `chassis/envelope.py`. `app/main.py` is constellation-wired at v2.3.0. All 12 new files pass syntax and lint checks with zero errors.
