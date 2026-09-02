<!-- HAND-AUTHORED folder guide; not a generated analysis artifact. -->

# Analysis Layer

Pure-Python generated analytics over the camera-ready CSVs in `results\final_scored_data\`. Every analysis is a same-stem pair: the `.py` computes and the `.md` is its rendered report. Rebuild everything with:

```powershell
python results\analysis\build_all_analysis.py
python results\analysis\validate_analysis.py
```

| Path | Contents |
|------|----------|
| `_analysis_runtime.py` / `.md` | Shared runtime: readers, derived fields, renderers, consolidators, validators |
| `_roadmap_runtime.py` / `.md` | Runtime for the roadmap-numbered analyses |
| `build_all_analysis.py` / `.md` | Full-regeneration entry point and its run report |
| `validate_analysis.py` / `.md` | Generated-artifact validator and its report |
| `all_tests_statistics.py` / `.md` | Root master ledger aggregating every folder summary |
| `ANALYSIS_ROADMAP_2026-07-11.md` | Hand-authored roadmap of the analysis suite |
| `schema-a\` ... `test-06\` | Per-surface analyses (one folder per test) |
| `cross-test\` | Analyses combining multiple surfaces |
| `MASTER_SCHEMAS\` | Generated column dictionaries for the scored CSVs |

Generated `.md` files carry a generation marker; hand-authored files (like this one) are marked HAND-AUTHORED. `validate_analysis.py` enforces that convention.
