# Override Auditor Prompts

Copy-paste dispatch boxes for the four override audits. One agent per prompt, one output file per agent.

| File | Audits | Writes |
|------|--------|--------|
| `schema_a.md` | Schema A method axes (240 responses) | `schema_a_method_review_overrides.csv` |
| `schema_a_new_system.md` | Schema A New System method axes (240) | `schema_a_new_system_method_review_overrides.csv` |
| `test01.md` | Test 01 method axes, regular + fruit (480) | `test01_method_review_overrides.csv` |
| `test03.md` | Test 03 semantic correctness (240) | `test03_semantic_review_overrides.csv` |
| `integration.md` | Nothing (file map; states there is no multi-reviewer integration step) | - |

All output paths are under `results\final_scored_data\overrides\`. See `..\README.md` and `..\INFRASTRUCTURE_MAP.md`.
