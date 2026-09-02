# Schema A New System (SANS) Extraction

Structured extraction of the raw sessions in `..\test-sessions\`. One extractor per round, one output file per round (one agent, one output).

| File | Role |
|------|------|
| `SCHEMA_A_NEW_SYSTEM_LEDGER.csv` | Session list and canonical row order for this surface (240 rows) |
| `SCHEMA_A_NEW_SYSTEM_r1.csv`, `SCHEMA_A_NEW_SYSTEM_r2.csv`, `SCHEMA_A_NEW_SYSTEM_r3.csv`, `SCHEMA_A_NEW_SYSTEM_r4.csv` | Per-round extraction CSVs (round N fills only round-N columns) |
| `SCHEMA_A_NEW_SYSTEM_r5_extractor_01.csv`, `SCHEMA_A_NEW_SYSTEM_r5_extractor_02.csv` | Round-5 construction-transcription dual-pass CSVs (two independent extractors; see `instructions\extraction\schema-test-A-new-system-tests\SCHEMA_A_NEW_SYSTEM_ROUND5_PROMPTS.md`) |
| `SCHEMA_A_NEW_SYSTEM_r5.csv` (generated) | Gated round-5 CSV written by `scripts\r5_construction_gate.py`; disagreements become `construction_unresolved`; the only round-5 file `combine_rounds.py` consumes |
| `SCHEMA_A_NEW_SYSTEM_r5_gate_report.json` / `.md` (generated) | Published gate report |
| `combine_rounds.py` | Merges the round CSVs into the wide master (run from this folder) |
| `SCHEMA_A_NEW_SYSTEM_master_output.csv` | Combined extraction master consumed by the publish step |

`combine_rounds.py` also writes `SCHEMA_A_NEW_SYSTEM_master_output_audit.txt` (regenerated, excluded from version control). A `bad_sessions.md` file appears only when a raw session is mechanically unusable.

Downstream: `python scripts\publish_final_extracted_data.py` copies the master into `results\final_extracted_data\`.
