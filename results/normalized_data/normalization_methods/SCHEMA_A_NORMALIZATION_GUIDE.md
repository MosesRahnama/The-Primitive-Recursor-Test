# Schema A Normalization Guide

## Input And Output

- Input: `results/final_extracted_data/SCHEMA_A_master_output.csv`.
- Output: `results/normalized_data/final_SCHEMA_A_consolidation.csv`.
- Identity fields `model` and `provider` come from
  `roster/roster.json` via the session slug (not from MASTER_STATUS).

## Transformations

- Remove the `rN__` round prefix and any legacy `final_` prefix.
- Drop extractor-specific fields and every `extraction_notes` field.
- Rename Round-1 `primary_method` to `turn1_primary_method`.
- Preserve all adjudicated answer, flag, and verbatim-evidence fields.
- Map `turn1_primary_method` by exact lookup in `method_labels.csv` to:
  - `turn1_norm_primary_method_standardized_method_name`
  - `turn1_norm_primary_method_method_class`

The normalized name and class describe the method proposed by the response.
They do not grade mathematical validity, termination correctness, or boundary
admissibility. No scoring override is read or written during normalization.
