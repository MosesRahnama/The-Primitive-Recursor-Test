# Normalized Scoring-Ready Data

This directory contains the cleaned, scoring-ready CSVs generated from
`results/final_extracted_data/*_master_output.csv`.
It contains no correctness scores and no manual scoring overrides.
Scoring copies these files into `results/final_scored_data` before adding verdict columns.

Run:

```powershell
python results\normalized_data\normalize_final_extracted_data.py
```

Key files:

- `normalize_final_extracted_data.py`: reproducible normalization driver.
- `SCORING_READY_COLUMN_PLAN.md`: human-readable transformation contract.
- `column_cleaning_ledger.csv`: one row per source/derived/dropped column.
- `normalization_run_report.json`: machine-readable run summary.
- `validate_normalized_data.py`: normalization-only validation gate.
- `normalization_validation_report.md` and `.csv`: generated validation results.
- `normalization_methods/`: method dictionaries and normalization provenance.
