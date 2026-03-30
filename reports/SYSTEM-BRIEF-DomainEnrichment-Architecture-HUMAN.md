# What Are These Two Things and How Do They Connect?

**Date:** 2026-03-30
**Plain English — No Jargon**

---

## The Short Version

You have one enrichment system split across two platforms. The Python codebase is the brain. The Salesforce package is the hands. Neither works without the other.

---

## What is `domain-enrichment-api` (the egg-info)?

This is your Python application — the intelligence engine.

It does all the heavy lifting:
- Takes a CRM record (Account, Lead, etc.)
- Figures out what fields are missing
- Looks up your domain knowledge base (plastics recycling KB)
- Runs it through multiple AI variations (Perplexity) to get consensus answers
- Scores confidence, tracks uncertainty, returns enriched field values
- Can write those values back to Salesforce directly over the internet

The `domain_enrichment_api.egg-info` folder is just a technical side-effect of installing it — like a receipt. It's auto-generated and doesn't contain your actual code. The code lives in the `app/` folder. You can safely ignore the egg-info folder itself; it just tells Python's packaging tools what the project is called and what it depends on.

**Current version:** 2.2.0

**What it's built with:** Python, FastAPI (HTTP server), Perplexity AI, Redis, Pydantic

---

## What is `2GP-domain-enrichment-engine`?

This is your Salesforce package — the thin client that lives inside a customer's Salesforce org.

It does only what Salesforce needs to do:
- Runs a nightly scheduled job
- Picks up records that need enriching (based on profiles you configure)
- Sends each record to your Python API over HTTP
- Takes the response and writes the enriched fields back into Salesforce
- Creates an audit trail record (`Enrichment_Run__c`) for every enrichment attempt

It has zero intelligence of its own. All the smarts are in your Python API. The Salesforce package is intentionally thin — this is the right design because Salesforce has strict limits (timing, memory, concurrent jobs) that would make running AI logic inside it impossible.

**Package type:** Salesforce 2GP Managed Package (AppExchange-ready format)
**Status:** Scaffolded and functional, but not yet registered as a real package — it can't be published yet (see issues below)

---

## Are They Related? Yes — Here's How

```
Every night (or on-demand):

Salesforce picks up records  →  sends them to your Python API
                                        ↓
                            Python figures out the answers
                                        ↓
                            Sends enriched data back to Salesforce
                                        ↓
Salesforce writes fields back  +  logs what happened
```

Think of it like a restaurant kitchen (Python) and a waiter (Salesforce). The waiter takes the order from the customer (CRM record), hands it to the kitchen, and brings back the food (enriched fields). The kitchen never needs to know anything about Salesforce. The waiter never needs to know how to cook.

---

## What's Working Well

- The Salesforce package correctly calls your Python API over HTTP using Named Credentials (secure, passes AppExchange review)
- Every enrichment attempt is logged with full metadata: confidence score, which KB version was used, how many AI variations ran, how long it took — excellent audit trail
- The package is designed so all Salesforce governor limits are respected — batch sizes, callout limits, timeouts are all handled
- The Python API already has a `SalesforceClient` that can write data back independently, giving you flexibility
- Test coverage exists for the main happy path and failure scenarios

---

## What's Not Working / What's Missing

### Blockers — Must Fix Before Launch

**1. Two things can write to the same Salesforce field at the same time.**
Your Salesforce package (`EnrichmentWriteBack`) writes fields back from inside Salesforce. Your Python app (`SalesforceClient`) can also write fields back from outside. There's nothing preventing both from running on the same record. The last one to write wins, and there's no record of which path made the change. This needs a clear decision: pick one path and disable the other.

**2. Security vulnerability in how Salesforce queries are built.**
When a profile admin defines which fields to enrich, those field names get inserted directly into a database query without proper validation. A malicious field name in the profile configuration could manipulate what data gets queried. This would be caught and rejected during Salesforce's AppExchange security review.

**3. The Salesforce package hasn't been registered yet.**
The scaffolding is there, but the package doesn't formally exist in Salesforce's system yet. It needs to be registered against a Developer Hub org before any version can be created or installed anywhere. Without this step, nothing can be packaged or distributed.

**4. Python API blocks itself during Salesforce login.**
When the Python app connects to Salesforce to write data back, it uses a connection method that pauses the entire server while it waits for Salesforce to respond to the login request. In a busy server, this would cause slowdowns for all other requests happening at the same time.

### Important — Degrades Quality

**5. "Only enrich missing fields" doesn't actually work.**
There's a setting on the profile called "Missing Fields Only" but the code doesn't use it properly. Instead of checking whether the target fields are blank, it checks whether the record was modified recently. These are not the same thing.

**6. Python package has stale metadata.**
The egg-info was generated with older development tool versions than what's currently listed in the project configuration. Running `pip install -e ".[dev]"` will fix this automatically.

**7. Three Python files exist but aren't included in the package.**
Three source files (`inference_unlock_scorer.py`, `confidence_tracker.py`, `convergence_config.py`) exist in the codebase but are missing from the package manifest. They won't be included when the package is built for deployment.

**8. Test coverage is set too low.**
The Python project only requires 60% test coverage to pass. The project standard requires 85%. The current setting means the CI pipeline will pass even when large portions of the engine are untested.

**9. No automated build pipeline for the Salesforce package.**
There's no CI workflow that automatically creates new package versions, runs Salesforce's code scanner, or verifies coverage thresholds. Everything has to be done manually.

---

## Priority Order to Fix

| # | What | Why It Matters |
|---|---|---|
| 1 | Decide on one write-back path and remove the other | Data integrity — two writers = unpredictable CRM data |
| 2 | Fix the SOQL field name injection | AppExchange security review will reject the package |
| 3 | Register the package against Dev Hub | Nothing can be packaged or shipped without this |
| 4 | Fix the blocking Salesforce login in Python | Server performance under real load |
| 5 | Implement Missing Fields Only properly | The feature doesn't do what the name says |
| 6 | Add the 3 missing files to the package manifest | They exist but won't ship |
| 7 | Raise coverage threshold to 85% | Current threshold hides untested engine code |
| 8 | Build a CI pipeline for the Salesforce package | Required for sustainable version management |

---

## One-Line Summary

The Python app is the AI brain; the Salesforce package is the delivery mechanism. They work together correctly in concept but have two blockers that need to be resolved before the Salesforce package can be submitted to AppExchange, and one data integrity issue (dual write-back) that needs a decision regardless of platform.
