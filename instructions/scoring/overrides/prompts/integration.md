# Integration

There is no multi-reviewer integration step.

Each surface prompt is a complete single-agent assignment. Dispatch one agent per prompt file. That agent writes only its override CSV under:

`results\final_scored_data\overrides\`

| Prompt | Output file | Rows |
|--------|-------------|-----:|
| `schema_a.md` | `schema_a_method_review_overrides.csv` | 240 |
| `schema_a_new_system.md` | `schema_a_new_system_method_review_overrides.csv` | 240 |
| `test01.md` | `test01_method_review_overrides.csv` | 480 |
| `test03.md` | `test03_semantic_review_overrides.csv` | 240 |

Do not run collate scripts, override-build scripts, sync mirrors, adjudication ledgers, or any review machinery for this streamlined path. Do not create reports, decision CSVs, or configuration files beside those four override ledgers.

After all four override files are complete, scoring may consume them. Validation of scored outputs is a separate scoring step, not part of these override prompts.
