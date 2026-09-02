# TTT2 Artifacts (Schema New-System Variant)

This folder stores external TTT2 evidence for the Schema A new-system variant.

## Input

- `Schema-Test-A-New-System.trs`: canonical TRS used for the new-system control

Contents:

```text
(VAR x y n)
(RULES
  F(x, y, Z) -> x
  F(x, y, S(n)) -> G(F(x, y, n))
)
```

## TTT2 Proof Outputs

This folder contains a live hosted replay from the integrated TTT2/CeTA host at
`http://138.232.18.220/tool/ttt2` on 2026-04-10.

### Certified (YES -> CeTA CERTIFIED)

- `Schema_New_System_FAST.cpf`: FAST strategy
- `Schema_New_System_HYDRA.cpf`: HYDRA strategy
- `Schema_New_System_LPO.cpf`: LPO strategy
- `Schema_New_System_COMP.cpf`: COMP strategy
- `Schema_New_System_KBO.cpf`: KBO strategy
- `Schema_New_System_POLY.cpf`: POLY strategy, `-direct -ib 5 -ob 6`
- `Schema_New_System_MAT2.cpf`: MAT(2) strategy, `-direct -dim 2 -ib 3 -ob 4`
- `Schema_New_System_MAT3.cpf`: MAT(3) strategy, `-direct -dim 3 -ib 2 -ob 3`

### Text outputs

- `Schema_New_System_TTT2_results_FAST.txt`
- `Schema_New_System_TTT2_results_HYDRA.txt`
- `Schema_New_System_TTT2_results_LPO.txt`
- `Schema_New_System_TTT2_results_COMP.txt`
- `Schema_New_System_TTT2_results_KBO.txt`
- `Schema_New_System_TTT2_results_POLY.txt`
- `Schema_New_System_TTT2_results_MAT2.txt`
- `Schema_New_System_TTT2_results_MAT3.txt`

## Results Summary

| Strategy | TTT2 | Time | CeTA | Notes |
|----------|------|------|------|-------|
| FAST | YES | 0.025s | **CERTIFIED** | DP + subterm criterion |
| HYDRA | YES | 0.034s | **CERTIFIED** | termination proof found automatically |
| LPO | YES | 0.001s | **CERTIFIED** | direct path-order proof |
| COMP | YES | 0.205s | **CERTIFIED** | competition strategy |
| KBO | YES | 0.002s | **CERTIFIED** | direct KBO proof |
| POLY | YES | 0.026s | **CERTIFIED** | direct polynomial proof |
| MAT(2) | YES | 0.059s | **CERTIFIED** | direct matrix proof |
| MAT(3) | YES | 0.075s | **CERTIFIED** | direct matrix proof |

See `Schema_New_System_CeTA_certification.txt` for exact commands and file names.

## Comparison with the Original Schema Kernel

The original schema kernel in `Artifacts/ttt2/schema/` has the recursive step

```text
F(x, y, S(n)) -> G(y, F(x, y, n))
```

and exhibits the same external-tool split as KO7: FAST, HYDRA, LPO, and COMP
certify, while KBO, POLY, and matrix interpretations fail.

The new-system variant drops the extra `y` payload from the wrapper:

```text
F(x, y, S(n)) -> G(F(x, y, n))
```

That change removes the obstruction seen in the original schema artifact. The
hosted replay shows that all eight archived strategies now certify successfully,
including KBO, POLY, and both matrix interpretations.

Concretely:

- FAST still finds the expected dependency-pair proof, with the recursive-call
  pair `F#(x,y,S(n)) -> F#(x,y,n)` discharged by projection to the third
  argument.
- KBO succeeds directly. The archived text output records `w0 = 1`,
  `w(G) = w(S) = w(Z) = 1`, `w(F) = 0`, and precedence `F > G ~ S ~ Z`.
- The direct POLY and MAT(2)/MAT(3) strategies also certify, showing that this
  variant no longer sits on the same external-proof barrier as the original
  schema kernel.

## Why This Matters

This folder provides a clean external contrast case for the benchmark. The new
system preserves the same two-rule recursor shape but no longer exhibits the
original schema's resistance to direct whole-term methods. In external tool
terms, the orientation boundary visible in `Artifacts/ttt2/schema/` is absent
here.

## File Inventory

### Input
- `Schema-Test-A-New-System.trs`

### Raw text outputs
- `Schema_New_System_TTT2_results_FAST.txt`
- `Schema_New_System_TTT2_results_HYDRA.txt`
- `Schema_New_System_TTT2_results_LPO.txt`
- `Schema_New_System_TTT2_results_COMP.txt`
- `Schema_New_System_TTT2_results_KBO.txt`
- `Schema_New_System_TTT2_results_POLY.txt`
- `Schema_New_System_TTT2_results_MAT2.txt`
- `Schema_New_System_TTT2_results_MAT3.txt`

### CPF certificates
- `Schema_New_System_FAST.cpf`
- `Schema_New_System_HYDRA.cpf`
- `Schema_New_System_LPO.cpf`
- `Schema_New_System_COMP.cpf`
- `Schema_New_System_KBO.cpf`
- `Schema_New_System_POLY.cpf`
- `Schema_New_System_MAT2.cpf`
- `Schema_New_System_MAT3.cpf`

### Certification log
- `Schema_New_System_CeTA_certification.txt`

### Summary
- `schema_new_system_certification_summary.json`