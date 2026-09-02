# Scoring-Ready Normalization and Column-Cleaning Plan

> Generated 2026-07-16 16:36 UTC by `normalize_final_extracted_data.py`.

## Pipeline

```text
results/final_extracted_data/*_master_output.csv
  -> keep consolidated rN__* fields (including legacy rN__final_*)
  -> drop extractor1/extractor2 duplicates and extraction_notes
  -> strip round and legacy final prefixes
  -> add model/provider/prompt_variant identity fields
  -> add method and selection normalization columns
  -> results/normalized_data/final_<PREFIX>_consolidation.csv
```

## Source Script

- `scripts/publish_final_extracted_data.py` populated the input folder: `results\final_extracted_data`.
- This script produced the normalized outputs in: `results\normalized_data`.
- Method dictionary: `results\normalized_data\normalization_methods\method_labels.csv` (1205 rows).

## Mechanical Rules

- Keep `session_slug` as the primary key.
- Add `model` and `provider` from `roster/roster.json` using the session slug (no MASTER_STATUS).
- Add `prompt_variant` only for surfaces where it is a real experimental axis: Schema-B, Schema-B-New, and Test-01 (from the session slug).
- Drop every `rN__extractor1_*` and `rN__extractor2_*` column.
- Keep every consolidated `rN__*` column except extraction notes.
- Rename kept columns by removing `rN__` and any legacy `final_` prefix.
- Rename Schema-A and Schema-A-New `r1__final_primary_method` to `turn1_primary_method` for scoring compatibility.
- Add method normalization columns by exact lookup in `normalization_methods/method_labels.csv`.
- Add Schema-B winner-set normalization columns by parsing `both_methods`.
- Fail hard if any method label is not covered by the dictionary.
- Fail hard if any correctness, score, or manual-review column enters normalized output.

## Output Summary

| Surface | Input rows | Output rows | Input cols | Output cols | Dropped | Renamed | Derived | Output file |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SCHEMA_A | 240 | 240 | 34 | 34 | 4 | 29 | 4 | `final_SCHEMA_A_consolidation.csv` |
| SCHEMA_A_NEW_SYSTEM | 240 | 240 | 34 | 34 | 4 | 29 | 4 | `final_SCHEMA_A_NEW_SYSTEM_consolidation.csv` |
| SCHEMA_B | 480 | 480 | 36 | 43 | 2 | 33 | 9 | `final_SCHEMA_B_consolidation.csv` |
| SCHEMA_B_NEW_SYSTEM | 480 | 480 | 36 | 43 | 2 | 33 | 9 | `final_SCHEMA_B_NEW_SYSTEM_consolidation.csv` |
| TEST01 | 480 | 480 | 23 | 25 | 3 | 19 | 5 | `final_TEST01_consolidation.csv` |
| TEST02 | 240 | 240 | 7 | 7 | 2 | 4 | 2 | `final_TEST02_consolidation.csv` |
| TEST03 | 240 | 240 | 12 | 12 | 2 | 9 | 2 | `final_TEST03_consolidation.csv` |
| TEST04 | 240 | 240 | 11 | 11 | 2 | 8 | 2 | `final_TEST04_consolidation.csv` |
| TEST05 | 240 | 240 | 16 | 16 | 2 | 13 | 2 | `final_TEST05_consolidation.csv` |
| TEST06 | 240 | 240 | 14 | 14 | 2 | 11 | 2 | `final_TEST06_consolidation.csv` |

## Reproduce

```powershell
python results\normalized_data\normalize_final_extracted_data.py
```

Column-level actions are recorded in `column_cleaning_ledger.csv`.
Validate the normalization-only outputs with:

```powershell
python results\normalized_data\validate_normalized_data.py
```
