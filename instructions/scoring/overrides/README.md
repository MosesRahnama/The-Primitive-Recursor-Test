# Override Audit Workflow

> **SUPERSEDED FOR METHOD-VALIDITY CELLS (2026-07-19).** The single-auditor override flow below is the HISTORICAL record of how the current scored data's method-validity and Test-03 semantic cells were produced. Going forward those cells are computed by the deterministic construction-checker pipeline: the R5 construction/stance transcription rounds (dual-pass, mechanically gated, transcribe-only) plus released checkers. No auditor agent writes method-validity or semantic overrides anymore. Policy of record: `scoring\R5_DETERMINISTIC_SCORING_POLICY.md`. This file is retained unchanged below because the historical override CSVs it produced remain the validation baseline for the checkers.

One agent per override surface. That agent reads every raw response and writes only the matching CSV under `results\final_scored_data\overrides\`. No dual reviewers, no adjudication ledgers, no construction/session decision files, no sync mirrors.

## Operator Steps

1. Open one prompt under `prompts\`: `schema_a.md`, `schema_a_new_system.md`, `test01.md`, or `test03.md`.
2. Paste the Auditor box into one agent. Do not split the work across reviewers.
3. Confirm the agent wrote only the named override CSV under `results\final_scored_data\overrides\`.
4. Repeat until all four override files are complete. See `prompts\integration.md` for the file map.

## Data Flow

```text
normalized CSVs + raw test-sessions
  -> one auditor per surface
  -> results\final_scored_data\overrides\*.csv
  -> scoring consumes those overrides
```

Policies under `policy_files\` are read-only mirrors of `scoring\`. Prefer the live files under `scoring\` when they differ.
