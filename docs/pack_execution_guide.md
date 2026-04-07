# Pack Execution Guide

## Objective
Convert uploaded packs into clean pull requests for this repository.

## Rules
- One PR per pack
- Short descriptive PR note
- Split single-file AI dumps into real files
- Map files to correct repo paths

## Defaults
- `base_branch=main`
- `one_branch_per_pack`
- `one_pr_per_pack`
- `infer_paths_if_missing`

## Inputs
- Accepted: `zip`, `raw_files`, `ai_dump_single_file`
- Required: `pack_name`
- Optional: `base_branch`, `target_paths`, `notes`

## Classification
- `feature`
- `bugfix`
- `refactor`
- `tooling`
- `tests`
- `docs`
- `mixed`

## Process
1. Ingest pack and record metadata
2. Classify change type
3. Normalize: inspect files, remove wrappers, split AI dump, normalize structure
4. Map: assign repo paths and infer missing paths when justified
5. Branch using one of:
   - `pack/<slug>`
   - `feature/<slug>`
   - `fix/<slug>`
   - `chore/<slug>`
6. Commit using one of:
   - `feat: <summary>`
   - `fix: <summary>`
   - `chore: <summary>`
   - `test: <summary>`
7. Open PR:
   - title matches commit style
   - short body: adds `<x>`, updates `<y>`, includes `<z>`

## AI Dump Handling
- Parse the single-file dump
- Detect logical file boundaries
- Separate into multiple files
- Assign correct filenames
- Map to repo structure

## Validation
Run, as applicable:
- `pre-commit run --all-files`
- `ruff check --fix`
- `ruff format`
- `mypy`
- `pytest unit`
- custom audit scripts if present
- CI remains enforced by GitHub Actions

## Dependencies
Install runtime, lint, type-check, test, and pre-commit tooling as required.

## Outputs Per Pack
- branch created
- files committed
- PR opened
- PR note added

## Constraints
- Do not merge packs
- Do not leave AI dumps unsplit
- Do not assign arbitrary paths without reason
- Preserve intended structure

## Risks
- wrong path inference
- mixed changes in one pack
- AI structural errors
- dependency mismatch

## Execution Ready
`true`
