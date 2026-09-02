# Test 04 (measure verification) Extraction

Structured extraction of the raw sessions in `..\test-sessions\`. One extractor per round, one output file per round (one agent, one output).

| File | Role |
|------|------|
| `TEST04_LEDGER.csv` | Session list and canonical row order for this surface (240 rows) |
| `TEST04_r1.csv`, `TEST04_r2.csv` | Per-round extraction CSVs (round N fills only round-N columns) |
| `combine_rounds.py` | Merges the round CSVs into the wide master (run from this folder) |
| `TEST04_master_output.csv` | Combined extraction master consumed by the publish step |

`combine_rounds.py` also writes `TEST04_master_output_audit.txt` (regenerated, excluded from version control). A `bad_sessions.md` file appears only when a raw session is mechanically unusable.

Downstream: `python scripts\publish_final_extracted_data.py` copies the master into `results\final_extracted_data\`.
