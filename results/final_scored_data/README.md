# Camera-ready numerical basis of record

The author approved this 3,120-row scoring generation on 2026-08-08 as the numerical basis for the overhauled PRT manuscript. The ten scored CSVs retain the original session identifiers and the applicable review fields. `MANIFEST.csv` records current counts and file hashes. `validation_report.csv` preserves the generating pipeline's 40 passed checks.

## Headline counts

| File | n | Termination | Validity | Primary boundary or overall result |
|---|---:|---:|---:|---:|
| Schema A, duplicating | 240 | 215 (89.6%) | 111 (46.3%) | 13 (5.4%) |
| Schema A, copy removed | 240 | 218 (90.8%) | 144 (60.0%) | 49 (20.4%), strict primary |
| Schema B | 480 | | | Method D 445 (92.7%); all five methods 0 |
| Schema B, copy removed | 480 | | | Method D 452 (94.2%); all five methods 24 (5.0%) |
| Test 01 | 480 | 358 (74.6%) | 112 (23.3%) | 1 (0.2%) |
| Test 02 | 240 | | | 77 (32.1%) |
| Test 03 | 240 | | | 23 (9.6%), corrected Lean target |
| Test 04 | 240 | | | 174 (72.5%) |
| Test 05 | 240 | | | 232 (96.7%) |
| Test 06 | 240 | | | 168 (70.0%) |

The copy-removed file also contains a harmonized cross-generation field, `turn1_method_correct_and_admissible`, with 106/240 positive rows. That field answers a different scoring question and is reported only as a sensitivity analysis. The strict field, `turn1_method_correct_and_admissible_strict_policy`, is the primary within-generation boundary outcome.

## Integrity and scope

The generating pipeline reports 40 passed checks across 3,120 rows, including source preservation, unique session identifiers, review-ledger gates, score recomputation, and binary camera-ready fields. The five 2026-07-27 adjudication changes use the same rule applied to the earlier six terse Schema A responses. Their shared policy is documented in `PROVENANCE.md` and the adjudication evidence folder.

The separate reader-comparison round is retained as rubric-harmonization evidence. Its design does not support an independent reliability estimate, so the manuscript does not use it for that purpose. Test 03 uses the corrected Lean target; older Test 03 figures based on the earlier target require an explicit scoring-generation label.

The scoring engine package remains in preparation. These CSVs are the author-approved output basis, while software-release and current-engine validation claims require their own release receipt.
