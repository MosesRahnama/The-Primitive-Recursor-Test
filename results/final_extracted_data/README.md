# Final Extracted Data (Publish Staging)

Published copies of each test's extraction master, one CSV per surface: `SCHEMA_A`, `SCHEMA_A_NEW_SYSTEM`, `SCHEMA_B`, `SCHEMA_B_NEW_SYSTEM`, and `TEST01` through `TEST06` `_master_output.csv`.

Written by `python scripts\publish_final_extracted_data.py`, which verifies each copy is byte-identical to its per-test source `results\<test>\extraction\<PREFIX>_master_output.csv` and refuses stale masters. The publish run also writes `_publish_manifest.md` (regenerated, excluded from version control).

These files still have extraction-shaped columns and no scores. Downstream: `python results\normalized_data\normalize_final_extracted_data.py`.
