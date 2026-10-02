<!-- HAND-AUTHORED folder guide. -->

# Test 04 Analysis

Rebuild with `python results/analysis/build_all_analysis.py`; score definitions and reported values are unchanged by folder consolidation.

| Files | Contents |
|---|---|
| [analysis.md](analysis.md), [analysis.csv](analysis.csv) | Per-surface findings |
| [analysis.py](analysis.py) | Computes the per-surface findings |
| `python scripts/test_test04_analysis.py` (from the repository root) | Checks the rule explanation, existing scores and unchanged finding rows |
| `build_test-04_analysis` | builder that regenerates every analysis in this folder |
| `evidence_or_localization_profile` | descriptive profile over the scored columns |
| `manuscript_test04_detail` | recomputation of a manuscript-facing table from the scored CSV |
| `model_instability_profile` | descriptive profile over the scored columns |
| `model_provider_profile` | descriptive profile over the scored columns |
| `overview_counts` | row, verdict, and field counts |
| `test-04-statistical_summary` | combined statistical summary for this surface |
| `verdict_profile` | descriptive profile over the scored columns |
