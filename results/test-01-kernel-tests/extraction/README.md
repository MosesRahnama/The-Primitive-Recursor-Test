# Test 01 (KO7 kernel) Extraction

Structured extraction of the raw sessions in `..\test-sessions\`. One extractor per round, one output file per round (one agent, one output).

| File | Role |
|------|------|
| `TEST01_LEDGER.csv` | Session list and canonical row order for this surface (480 rows) |
| `TEST01_r1.csv`, `TEST01_r2.csv`, `TEST01_r3.csv` | Per-round extraction CSVs (round N fills only round-N columns) |
| `TEST01_r4_extractor_01.csv`, `TEST01_r4_extractor_02.csv` | Round-4 construction-transcription dual-pass CSVs (two independent extractors; see `instructions\extraction	est-01-kernel-tests\TEST01_ROUND4_PROMPTS.md`) |
| `TEST01_r4.csv` (generated) | Gated round-4 CSV written by `scripts\r5_construction_gate.py`; disagreements become `construction_unresolved`; the only round-4 file `combine_rounds.py` consumes |
| `TEST01_r4_gate_report.json` / `.md` (generated) | Published gate report |
| `combine_rounds.py` | Merges the round CSVs into the wide master (run from this folder) |
| `TEST01_master_output.csv` | Combined extraction master consumed by the publish step |

`combine_rounds.py` also writes `TEST01_master_output_audit.txt` (regenerated, excluded from version control). A `bad_sessions.md` file appears only when a raw session is mechanically unusable.

Downstream: `python scripts\publish_final_extracted_data.py` copies the master into `results\final_extracted_data\`.
