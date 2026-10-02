# Trace statistics

Written for a reviewer who has this repository and has seen none of the working materials behind the paper.

This folder reproduces the paper's numbers that come from word lists and word positions in the returned reasoning traces, from a manual reading of the traces that name the recursive-call route, and from the exploratory prediction of missing proof credit. Every script reads only the benchmark's own files: the session folders under `results/`, `results/final_scored_data`, and the payload arm's pilot coding in `results/payload-scaling-tests/pilot-coding`. `scripts/paper_numbers.py` recomputes each of these numbers and compares it with the value printed in the paper; `paper_numbers.csv` lists all 33. On the scores republished on 2026-09-26 from the code-only rulebook construction/1, 22 match and 11 differ (`match` is `no`): the Schema A and Test 01 rates of correct proofs with and without a refutation, the area under the curve of answer hedge density, the entropy of the proof score, the two joint mutual-information values, the count of the 34 route traces without rule-derived credit, the three held-out-model areas, and the risk-coverage pair.

## Analyses

| Script | Reads | Writes | In the paper |
|---|---|---|---|
| `layer1_trace_analysis.py` | `final_scored_data/thinking_files_inventory.csv`, the traces and responses it lists, and `final_scored_data` | `data/thinking_trace_analysis.csv`, one row per trace | appendix: hedging in reasoning and in final answers; the 285 first-turn records |
| `aggregate_stats.py` | `data/thinking_trace_analysis.csv` | `data/stats_console.txt`, `data/stats_summary.json` | the hedge rates 0.850 and 0.010 |
| `trace_flow.py` | Test 07 extraction files, `payload-scaling-tests/pilot-coding/FINDINGS.csv`, and their traces | `data/trace_flow_sessions.json` | the factorial onset 0.20 |
| `trace_flow_core.py` | Schema A, copy-removed, and Test 01 traces, and `final_scored_data` | `data/trace_flow_core.json` | Section 4 and appendix: the 339-record vocabulary sample |
| `omega_boundary.py` | the two JSON files above, `../external-benchmarks/data/corpus_features.csv`, `payload-scaling-tests/pilot-coding/K_SERIES.csv` | `data/omega_boundary.json` | appendix: entropy and mutual information |
| `proof_review_prediction.py` | `final_scored_data` | `data/proof_review_prediction/` | appendix: exploratory within-benchmark prediction |
| `paper_numbers.py` | the outputs above, `records/strict_route_release_audit.csv`, `final_scored_data` | `paper_numbers.csv` | every number above |

`records/strict_route_release_audit.csv` is a manual reading. Each of the 36 traces in which the trace analysis found the recursive-call route had its final response read in full, and its row records whether that response delivers the route as the boundary-compliant proof. 34 of the traces are in this repository; the other 2 come from the submitted-era corpus, which is outside it. In that reading 33 of the 34 traces in this repository release a different proof. In `final_scored_data` all 34 lack rule-derived credit: construction/1 scores the one delivery the reading found, `kimi-k2.5__2026-06-25T01-14-35-00003`, Incorrect.

## Reproduce

Python 3.10 or later with `numpy`, `pandas`, `scipy`, `scikit-learn`, and `tabulate`. Run from `scripts/`, in this order:

1. `python layer1_trace_analysis.py`, then `python aggregate_stats.py`.
2. `python trace_flow.py`, `python trace_flow_core.py`, then `python omega_boundary.py`. The last one also reads `../external-benchmarks/data/corpus_features.csv`, which `../external-benchmarks/scripts/transport_features.py` rebuilds.
3. `python proof_review_prediction.py`.
4. `python paper_numbers.py`.

`aggregate_stats.py` also writes its printed tables to `data/stats_console.txt`.

## Facts to hold while reading

- The word lists for hedges, refutations, and method families are regular expressions in `trace_flow.py` and `layer1_trace_analysis.py`. They count words, not meaning.
- A position is a character offset divided by the length of the trace.
- `layer1_trace_analysis.py` first ran on 2026-07-27 against the scoring of 2026-07-25. Against the build of 2026-09-12, the 2026-09-26 scores change 96 validity fields, 85 rule-derived fields, 6 Test 03 fields and 2 method-class fields in the 1,430 rows of `data/thinking_trace_analysis.csv`. 79 of the rule-derived changes are in the copy-removed control: `layer1_trace_analysis.py` and `trace_flow_core.py` now read its credit from `turn1_method_correct_and_admissible_strict_policy`, the column `final_scored_data/MANIFEST.csv` counts (27 of 240). Every word-list count is unchanged. The manual reading in `records/` was made against the 2026-07-25 scoring.
- The 2026-07-27 run was followed by a manual pass that filled the `discard_category` column; here that column holds only the placeholder `needs_read` (57 rows), and the paper uses none of it.
- The prediction features include manual annotations chosen after collection, so the prediction is exploratory.
