# Test 07 TTT2/CeTA verification report

Date: 2026-07-26

State: `exact TRSs frozen -> 19 new TTT2 runs -> 10 new YES CPFs CeTA CERTIFIED -> 9 restricted MAYBE outputs retained as non-proofs -> S4 historical FAST certificate reused`

## Tool and execution provenance

- Prover: TTT2 1.19 `[hg: unknown]`
- Certifier: CeTA 2.36
- Integrated host: `http://138.232.18.220/tool/ttt2`
- Reproducible runner: `TTT2-Artifacts/test-07-propagation-fac/run_ttt2_matrix.ps1`
- New runs: 19
- Per-run transport exit status: 0 for all 19 runs
- Timeout: the PowerShell HTTP wrapper enforced a 60-second wall-clock timeout. The integrated host's returned TTT2 command does not expose a numeric timeout argument. This is recorded in every run file and is a provenance limitation, not silently rewritten as a tool-side timeout.
- Every run has decoded full output, original TTT2 output, raw HTML, CPF, command, input hash, exit status, tool time, and wall time under `verification/ttt2/`.
- Every new `YES` CPF was replayed by the host's independent CeTA executable and returned `CERTIFIED`.
- Every `MAYBE` CPF contains an unresolved termination assumption; CeTA returned `REJECTED`. These rows are search-inconclusive, never negative mathematical evidence.

## Exact inputs

| System | File | SHA-256 | Rules |
|---|---|---|---:|
| S1 | `S1_fac.trs` | `949744A7555405F5A29B71E9BB45F99A1EB9A4EB5D05340882F64DB2807475CA` | 8 |
| S2 | `S2_nofac.trs` | `B6A485921A04EF5AD02CBD3C7408AD5524799BE7F2B940814905D7EBCCF43875` | 7 |
| S3 | `S3_ag316.trs` | `A92569B976D46854E99810399D604C6D5DF7236B453E399D7D9BC57D729C2E8A` | 6 |
| S4 | `S4_schema.trs` | `65698E5CCEC51FF49CA5B1763C3BEFAFA71002725885C7790544E786CE828B9D` | 2 |

The files were transcribed from the four prompt files named in the verification plan. The S4 rule file also matches the TRS embedded in the pre-existing schema CPF.

The plan's nonce system is S1 under a symbol-only renaming. Termination and method-class evidence transport across that bijective renaming, so the S1 artifacts are the canonical evidence and no duplicate nonce run was manufactured.

## Strategy commands

The exact returned command is retained in each source file. Strategy cores were:

- Automatic: `./ttt2 -C "" -cpf -t input.trs`
- LPO only: `./ttt2 -C "" -cpf -t -s 'lpo' input.trs`
- KBO only: `./ttt2 -C "" -cpf -t -s 'kbo' input.trs`
- Direct linear polynomial only: `./ttt2 -C "" -cpf -t -s 'poly -direct -ib 5 -ob 6' input.trs`
- Dependency-pair branch: `dp;(tdg | sccs | sc)*;(edg -gtcap -nl[2] | sccs | sc | sc -rec -defs[1] | sc -mulex -defs[1] | sct | {ur?;lpo -dp -af[2]}restore | {ur?;matrix -dp -dim 2 -ib 2 -ob 2 -ur[2]}restore | uncurryx?;uncurryx -top )[10]*`

The DP strategy forces the DP transformation, then permits graph, subterm, and reduction-pair processors. It is not a claim that the subterm criterion alone solves every SCC.

## Results

Tool time is TTT2's reported time in seconds. Full wall times are in `TTT2_RESULTS.csv`.

| System | Auto | LPO only | KBO only | Linear poly only | DP based |
|---|---|---|---|---|---|
| S1 fac | YES, 0.272, CERTIFIED | MAYBE, 0.005 | MAYBE, 0.005 | MAYBE, 0.090 | YES, 0.118, CERTIFIED |
| S2 no fac | YES, 0.028, CERTIFIED | YES, 0.005, CERTIFIED | MAYBE, 0.006 | MAYBE, 0.066 | YES, 0.006, CERTIFIED |
| S3 AG01/#3.16 | YES, 0.048, CERTIFIED | YES, 0.006, CERTIFIED | MAYBE, 0.001 | MAYBE, 0.045 | YES, 0.005, CERTIFIED |
| S4 schema | reused YES, 0.025, CERTIFIED | YES, 0.001, CERTIFIED | MAYBE, 0.001 | MAYBE, 0.026 | YES, 0.001, CERTIFIED |

S4 automatic termination reuses `TTT2-Artifacts/ttt2/schema/Schema_FAST.cpf` and `Schema_CeTA_certification.txt` as directed. S4 was newly run only under restricted strategies.

## Claim-matrix disposition

| Claim | Machine disposition | Evidence |
|---|---|---|
| M1: S1 terminates | PROVED and certified | `S1_fac_auto.cpf`, CeTA `CERTIFIED`, 0.272 s |
| M2: S2/S3/S4 terminate | PROVED and certified | S2/S3 auto CPFs; reused S4 FAST CPF |
| M3: no direct simplification order for S1 | TTT2 restricted runs are `MAYBE`; class impossibility is PROVEN-IN-LEAN | LPO/KBO/poly run files plus `no_simplification_order_orients_fac_rule` and `no_strictly_monotone_nat_interpretation_orients_fac_rule` |
| M4: S2/S3 admit LPO | PROVED and certified | `S2_nofac_lpo.cpf`, `S3_ag316_lpo.cpf` |
| M5: additive whole-term measures fail on duplication | PROVEN-IN-LEAN | `every_additive_weight_has_nondecreasing_ag316_instance`; reused S4 Lean anchors listed in `LEAN_REPORT.md` |
| M6: a DP route discharges all systems | PROVED and certified | Four DP CPFs, all CeTA `CERTIFIED` |
| M7: false armC method claims | Mapped to exact Lean theorems, with one scope exception flagged | `verification/lean/SESSION_CLAIM_MAP.csv` |

RPO was not separately searched by TTT2 because the requested restricted menu exposes LPO, KBO, and polynomial processors. RPO is covered by the abstract Lean theorem whenever it satisfies the stated simplification-order laws.

## Discrepancies and non-overclaims

1. The narrow expert strategy `dp;sc` solves S4 but returns `MAYBE` on S1-S3. Those exploratory outputs are retained in `verification/ttt2/exploratory_dp_sc/`. M6 therefore uses the exact DP branch needed by the certified automatic proof, including a matrix reduction pair for the factorial SCC.
2. Restricted `MAYBE` is not a proof of method-class impossibility. M3's impossibility component comes from Lean, not from TTT2 failure.
3. S2 and S3 return `MAYBE` under the bounded direct polynomial search even though they are certified terminating and LPO-orientable. No negative conclusion is drawn from those rows.
4. The integrated host does not expose a numeric timeout in its printed TTT2 command. The archived wrapper enforced 60 seconds externally; this differs from a local `ttt2 ... file 60` invocation and is stated in every artifact.

## Artifact locations

- Detailed results: `verification/TTT2_RESULTS.csv`
- New run outputs: `verification/ttt2/`
- Canonical mirror: `TTT2-Artifacts/test-07-propagation-fac/`
- Reused S4 evidence: `TTT2-Artifacts/ttt2/schema/`
