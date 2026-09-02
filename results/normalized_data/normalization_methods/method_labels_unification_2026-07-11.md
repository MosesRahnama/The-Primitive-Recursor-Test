# Method-Label Dictionary Unification - 2026-07-11

The normalization dictionaries formerly split across `results/normalized_data`, `scoring/normalization`, and `instructions/normalization` were reconciled into this directory. No correctness score or scoring override is present in this dictionary.

## Result

- Canonical labels: 1205
- Active-source labels before merge: 470
- Reviewed scoring-source labels before merge: 1014
- Extraction-instructions labels before merge: 601
- Mapping conflicts: 1 (`natural-number interpretation`)
- Canonical dictionary SHA-256: `e32733b766c3b6b7f285e738ae7d0c2c9d769a662756143aec7266b71268b154`

## Resolution Rule

- Preserve the newer active mapping on overlap.
- Import reviewed labels absent from the active dictionary.
- Apply `method_renames.csv` so stored standardized names are canonical.
- Preserve every source value and decision in `method_labels_unification_2026-07-11.csv`.

## Method-Class Counts

- `direct_measure`: 620
- `objection`: 8
- `path_order`: 182
- `polynomial`: 118
- `structural_descent`: 137
- `structural_induction`: 123
- `transformed_calls`: 17

