# Test 08 surface-transport certification report

Date: 2026-07-27

State: `bundle 22/22 hashes verified -> 8 new TTT2 runs -> 8 YES -> 8 CPFs CeTA CERTIFIED -> LPO-only YES on all 4 -> Lean v4.30.0 lake build exit 0, zero axioms`

All stated expectations were met. Nothing was reinterpreted, and no expectation had to be relaxed.

## Result table

| System | Costume | Auto | LPO only | CeTA (auto / lpo) |
|---|---|---|---|---|
| BMSSP `exec_walk_weight` | unblinded | YES, 0.036 s | YES, 0.006 s | CERTIFIED / CERTIFIED |
| BMSSP `exec_walk_weight` | blinded | YES, 0.032 s | YES, 0.005 s | CERTIFIED / CERTIFIED |
| Equality `extract_prefix` (let-lifted) | unblinded | YES, 0.047 s | YES, 0.006 s | CERTIFIED / CERTIFIED |
| Equality `extract_prefix` (let-lifted) | blinded | YES, 0.030 s | YES, 0.006 s | CERTIFIED / CERTIFIED |

| Lean check | Outcome |
|---|---|
| `lake build`, toolchain `leanprover/lean4:v4.30.0` | exit 0, 3 jobs, no warnings |
| `#print axioms` on all 7 declarations | every one reports `does not depend on any axioms` |
| `sorry` / `admit` / `partial` / `unsafe` / `axiom` / `native_decide` tokens | none in source |

Times are TTT2's own reported seconds. Wall times, per-run transport exit status (0 for all 8), input hashes, remote commands, decoded output, raw HTML, and CPF are in `verification/ttt2/` and `TEST08_CERT_RESULTS.csv`.

## Inputs

Byte-verified against the bundle's `MANIFEST.sha256`: 22 of 22 files match. The bundle's own static scripts (`validate_transport.py`, `reproduce_blinding.py`, `check_lpo_witness.py`) all exit 0.

| System | File | SHA-256 | Rules |
|---|---|---|---:|
| B unblinded | `bmssp_exec_walk_weight.trs` | `84963DCAF075AC74CA4D02673F8D25BC08A9537ACCB55CD910442C2B57BACF53` | 3 |
| B blinded | `bmssp_exec_walk_weight_blinded.trs` | `D870892C61D00CD9DA37BBB58546AE34A489B8D1B2035DC95ED3F4B9070646DF` | 3 |
| E unblinded | `equality_extract_prefix_letlift.trs` | `9A4DBE35E173D4CE750F0A1C293571D77F44A394FE894A631636CEACF8097840` | 3 |
| E blinded | `equality_extract_prefix_letlift_blinded.trs` | `E5B8B9B028335F9F48CB8F46E47F468D798E7B4FB31493259F02C1138B49BA81` | 3 |

Bundle root: `<manuscript repository, not distributed>`.

## Tool and execution provenance

- Prover: TTT2 1.19 `[hg: unknown]`
- Integrated host: `http://138.232.18.220/tool/ttt2`, same endpoint and same form protocol as the Test 07 workflow
- Reproducible runner: `TTT2-Artifacts/test-08-surface-transport/run_ttt2_matrix.ps1`, a direct adaptation of `TTT2-Artifacts/test-07-propagation-fac/run_ttt2_matrix.ps1` with the same strategy blobs, same `cetaEnabled=1` form field, and the same provenance-header record format. Only the input set, the run roots, and the strategy menu differ.
- New runs: 8 (4 systems x {auto, LPO only}). Per-run transport exit status: 0 for all 8.
- Timeout: the PowerShell HTTP wrapper enforced a 60-second wall-clock limit. The host's returned TTT2 command exposes no numeric timeout argument. This is recorded in every run file, and is a provenance limitation rather than a tool-side timeout.
- Certifier: the host's CeTA executable replayed every CPF and returned `CERTIFIED` on all 8. The host response block does not print a CeTA version string, so no version is asserted from these runs. The archived Test 07 record for the same endpoint reads CeTA 2.36.
- Strategy cores, exactly as returned by the host:
  - Automatic: `./ttt2 -C "" -cpf -t input.trs`
  - LPO only: `./ttt2 -C "" -cpf -t -s 'lpo' input.trs`

## What the automatic proofs actually do

Both systems are closed by the dependency-pair transformation followed by the subterm criterion with a collapsing argument filter, that is, an argument projection. The equality system additionally passes through a dependency-graph decomposition first.

| System | Route in the certified CPF | Projection |
|---|---|---|
| B (both costumes) | `dpTrans` then `subtermProc` | marked binary symbol to argument 2 |
| E (both costumes) | `dpTrans` then `depGraphProc` then `subtermProc` | marked ternary symbol to argument 3 |

This matches the route the bundle README predicted for each system (projection to argument 2 for BMSSP, argument 3 for `extract_prefix`). The blinded and unblinded proofs have the same shape.

## LPO witnesses

LPO-only returns YES and CeTA `CERTIFIED` on all four inputs, so the bundle's class-level claim that these transports are directly simplification-order orientable is confirmed by an independent search plus an independent certifier.

One precise distinction, stated rather than collapsed: the precedence TTT2 searched is **not** the precedence the bundle records. Both orient; they are different witnesses.

| System | Bundle's claimed precedence | TTT2's searched precedence |
|---|---|---|
| B | `exec_walk_weight > add > app > cons > zero > nil` (total) | `exec_walk_weight`=3 > `nil`=1 > `add`=`app`=`cons`=`zero`=0 (quasi, with ties) |
| E | `extract_prefix > extract_prefix_k > append > cons > best_eclass_term > nth > succ > nil > zero` (total) | `extract_prefix`=3 > `extract_prefix_k`=2 > `zero`=1 > all others =0 (quasi, with ties) |

Two further checks were run because the bundle's own witness script covers only the unblinded `.ari` files:

1. `verification/check_lpo_witness_all.py` reuses the bundle's parser and `lpo_gt` unchanged, and confirms the bundle's claimed precedence orients **all three rules of the blinded systems too**, after pushing the precedence through `BLINDING_MAP.json`. Exit 0.
2. TTT2's own searched precedence is **invariant under the blinding map**. `exec_walk_weight`/`f3` both rank 3, `nil`/`c0` both rank 1, and the remaining symbols tie at 0; likewise `extract_prefix`/`f5` at 3, `extract_prefix_k`/`f6` at 2, `zero`/`c0` at 1. The renaming is bijective on the signature, so this is the expected outcome, and it is now observed rather than assumed.

## Lean transport

Standalone Lake project at `verification/lean/`, built from the bundle's `SurfaceTransport.lean`, `lakefile.toml`, and `lean-toolchain` copied byte-identically (hashes re-verified after copy). No dependencies, so no Mathlib and no `lake exe cache get` step.

```
toolchain: leanprover/lean4:v4.30.0
lake build -> Build completed successfully (3 jobs).
LAKE_BUILD_EXIT=0
```

Lean reports version 4.30.0, `x86_64-w64-windows-gnu`, commit `d024af099ca4bf2c86f649261ebf59565dc8c622`. The pinned toolchain was not previously installed on this host and was fetched by `elan` for this run.

Axiom audit, via `lake env lean axiom_audit.lean` (a separate file, not part of the library target, so it does not alter the certified build):

```
'SurfaceTransport.execWalkWeight'            does not depend on any axioms
'SurfaceTransport.extractPrefix'             does not depend on any axioms
'SurfaceTransport.execWalkWeight_nil'        does not depend on any axioms
'SurfaceTransport.execWalkWeight_singleton'  does not depend on any axioms
'SurfaceTransport.execWalkWeight_cons_cons'  does not depend on any axioms
'SurfaceTransport.extractPrefix_zero'        does not depend on any axioms
'SurfaceTransport.extractPrefix_succ'        does not depend on any axioms
```

Both definitions use `termination_by structural`, so neither goes through well-founded recursion, and the five equation lemmas close by `rfl`. That is why the audit reports an empty axiom set rather than the usual `propext, Quot.sound, Classical.choice` baseline. A token scan of the source finds no `sorry`, `admit`, `partial`, `unsafe`, `axiom`, `native_decide`, `opaque`, or `implemented_by`; the only occurrence of those words is the docstring line asserting their absence. The build log has no warning, error, or `sorry` line.

## Non-overclaims

1. `YES` plus CeTA `CERTIFIED` certifies termination of the transported TRSs. It says nothing about whether the transports faithfully model the original AFP developments; the bundle itself declines that claim, and this pass did not test it.
2. The LPO-only `YES` results confirm direct simplification-order orientability. They are not evidence about the boundary rubric. As the run guide records, an LPO answer on these systems is mathematically correct and boundary-external.
3. The bundle's claimed precedences and TTT2's searched precedences are different objects, both valid. Neither is presented as confirming the other's exact form.
4. No CeTA version is asserted from these runs, because the host response does not carry one.

## Artifact locations

- Report: `results/test-08-surface-transport/verification/TEST08_CERT_REPORT.md`
- Results CSV: `results/test-08-surface-transport/verification/TEST08_CERT_RESULTS.csv`
- Run outputs (txt, html, cpf): `results/test-08-surface-transport/verification/ttt2/`
- Lean project, build log, axiom audit log: `results/test-08-surface-transport/verification/lean/`
- Extended witness checker: `results/test-08-surface-transport/verification/check_lpo_witness_all.py`
- Canonical mirror and runner: `TTT2-Artifacts/test-08-surface-transport/`
