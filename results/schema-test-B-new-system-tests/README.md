# Schema B New System Results

Fixed five-method menu (A-E) over the New System kernel, the all-methods-terminate control for Schema B. Two prompt variants: `regular` and the clarified `control` wording.

Original prompt file(s):

- `prompts\Schema-Test-B-New-System-prompt.txt (regular)`
- `prompts\Schema-Test-B-New-System-Control-Clarified-prompt.txt (control)`

| Subfolder | Contents |
|-----------|----------|
| `test-sessions\` | Raw model sessions, one folder per `session_slug` (source of truth) |
| `extraction\` | Per-round extraction CSVs, session ledger, round combiner, extraction master |

Sessions split by `prompt_variant`: 240 regular + 240 control.

Pipeline position: raw sessions here -> `extraction\SCHEMA_B_NEW_SYSTEM_master_output.csv` -> `results\final_extracted_data\` -> normalization -> scoring. See `results\results-docs\data_pipeline_overview.md`.
