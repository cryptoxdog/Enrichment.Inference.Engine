# L9 Constitution-First Coding Rules

For this repository, the source of truth for contract-bound development is the generated contract pack plus the constitution and corresponding tests.

## Mandatory read order for contract-bound changes

When editing any of the following surfaces:

- app/api/v1/**
- app/agents/**
- app/engines/**
- app/services/**
- chassis/**

you must read, in this order:

1. `docs/contracts/node.constitution.yaml`
2. The directly relevant contract file under `docs/contracts/`
3. The corresponding Tier 1 and Tier 2 tests under `tests/contracts/`

## Constitution-preserving rules

Do not introduce a new:

- chassis action
- MCP tool
- event type
- persisted semantic field
- request/response field
- dependency requirement

unless the same change also updates:

- the relevant contract file under `docs/contracts/`
- the corresponding test coverage under `tests/contracts/`
- the constitution when inventories, policies, or attestation semantics change

## Required co-change matrix

### API handler or schema change
Must update:
- relevant OpenAPI or schema contracts
- relevant request/response fixtures
- Tier 1 API tests
- Tier 2 behavior or provenance tests

### Packet or chassis change
Must update:
- packet protocol contract
- Tier 1 packet tests
- Tier 2 packet runtime tests

### MCP tool change
Must update:
- specific tool schema
- MCP alignment tests
- Tier 2 authority tests

### Event change
Must update:
- event channel or envelope contracts
- Tier 1 event tests
- Tier 2 event tests

### Persistence or convergence change
Must update:
- data model schema under `docs/contracts/data/`
- migration policy if applicable
- the constitution if semantic behavior changes
- Tier 1 data model tests
- Tier 2 behavior or provenance tests

## Stop conditions

Stop and require a contract update if the code change would alter:

- the action inventory
- the tool inventory
- the event inventory
- the dependency readiness behavior
- the runtime attestation shape
- the mutation class or approval mode of an action

## Output requirements for agent-generated changes

For every contract-bound code change, include:

- contract files changed
- constitution fields changed
- tests added or updated
- fixtures added or updated
- runtime guard behavior changed
- degraded-mode or provenance impact
