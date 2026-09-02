# Test 03 (completion, ordinal) Extraction

Structured extraction of the raw sessions in `..\test-sessions\`. One extractor per round, one output file per round (one agent, one output).

| File | Role |
|------|------|
| `TEST03_LEDGER.csv` | Session list and canonical row order for this surface (240 rows) |
| `TEST03_r1.csv`, `TEST03_r2.csv` | Per-round extraction CSVs (round N fills only round-N columns) |
| `TEST03_r3_extractor_01.csv`, `TEST03_r3_extractor_02.csv` | Round-3 obligation-stance dual-pass CSVs (two independent extractors; see `instructions\extraction	est-03-completion-tests-ordinal\TEST03_ROUND3_PROMPTS.md`) |
| `TEST03_r3.csv` (generated) | Gated round-3 CSV written by `scripts\r5_construction_gate.py`; disagreements become `stance_unresolved`; the only round-3 file `combine_rounds.py` consumes |
| `TEST03_r3_gate_report.json` / `.md` (generated) | Published gate report |
| `combine_rounds.py` | Merges the round CSVs into the wide master (run from this folder) |
| `TEST03_master_output.csv` | Combined extraction master consumed by the publish step |

`combine_rounds.py` also writes `TEST03_master_output_audit.txt` (regenerated, excluded from version control). A `bad_sessions.md` file appears only when a raw session is mechanically unusable.

Downstream: `python scripts\publish_final_extracted_data.py` copies the master into `results\final_extracted_data\`.
