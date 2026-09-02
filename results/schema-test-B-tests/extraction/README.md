# Schema B Extraction

Structured extraction of the raw sessions in `..\test-sessions\`. One extractor per round, one output file per round (one agent, one output).

| File | Role |
|------|------|
| `SCHEMA_B_LEDGER.csv` | Session list and canonical row order for this surface (480 rows) |
| `SCHEMA_B_r1.csv`, `SCHEMA_B_r2.csv` | Per-round extraction CSVs (round N fills only round-N columns) |
| `combine_rounds.py` | Merges the round CSVs into the wide master (run from this folder) |
| `SCHEMA_B_master_output.csv` | Combined extraction master consumed by the publish step |

`combine_rounds.py` also writes `SCHEMA_B_master_output_audit.txt` (regenerated, excluded from version control). A `bad_sessions.md` file appears only when a raw session is mechanically unusable.

Downstream: `python scripts\publish_final_extracted_data.py` copies the master into `results\final_extracted_data\`.
