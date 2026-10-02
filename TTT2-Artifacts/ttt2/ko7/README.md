# TTT2 Artifacts (KO7 Full Step)

This folder stores reproducibility artifacts for the KO7 full-step TRS,
copied from the companion `OperatorKO7` repository for self-contained reference.

## Input
- `KO7_full_step.trs`: input TRS (8 rules, 7 constructors)

## TTT2 Proof Outputs

### Certified (YES → CeTA CERTIFIED)
- `KO7_FAST.cpf`: FAST strategy (DP + SCC + subterm criterion)
- `KO7_LPO.cpf`: LPO strategy (lexicographic path order, rule removal)
- `KO7_COMP.cpf`: COMP strategy (DP + TDG + SCC + subterm + matrix + LPO)

### Search-inconclusive outputs (MAYBE; not negative evidence)
- `KO7_KBO.cpf`: KBO strategy (Knuth-Bendix order)
- `KO7_POLY.cpf`: POLY strategy (polynomial interpretation, `-ib 5 -ob 6`)
- `KO7_MAT2.cpf`: MAT(2) strategy (matrix interpretation, dim 2)
- `KO7_MAT3.cpf`: MAT(3) strategy (matrix interpretation, dim 3)

### No certificate produced in this run
- FBI strategy: returned MAYBE (0.17s) but produced no CPF certificate. No `.cpf` file is included for this strategy.

## Prior Text Outputs
- `KO7_full_step_TTT2_results_FAST.txt`: FAST strategy human-readable output
- `KO7_full_step_TTT2_results_POLY.txt`: POLY strategy human-readable output

Note: Human-readable text outputs are preserved only for FAST and POLY. Timings for other strategies are from TTT2 runs and can be reproduced using the generation commands below. CPF files (which encode the complete proof certificates) are included for all strategies that produced them (FBI returned MAYBE with no CPF output).

## Certification Log
- `KO7_CeTA_certification.txt`: full CeTA 2.36 verification results for all strategies

## Generation

TTT2 1.20 [hg: 1ffa9886eb7f]:
```bash
# Requires local TTT2 1.20 binary (originally built in OperatorKO7/Comments/ttt2-1.20/)
./ttt2 -cpf <TRS>                              # FAST (default)
./ttt2 -cpf -s lpo <TRS>                       # LPO
./ttt2 -cpf -s 'dp;...' <TRS>                  # COMP (full strategy string in certification log)
./ttt2 -cpf -s kbo <TRS>                       # KBO
./ttt2 -cpf -s 'poly -direct -ib 5 -ob 6' <TRS>   # POLY
./ttt2 -cpf -s 'matrix -dim 2 -ib 2 -ob 2' <TRS>  # MAT(2)
./ttt2 -cpf -s 'matrix -dim 3 -ib 2 -ob 2' <TRS>  # MAT(3)
```

Post-processing: raw TTT2 output has a `YES`/`MAYBE` line before XML; CPF files here have that line stripped.

## CeTA Certification (2026-03-04)

CeTA 2.36 via web interface at http://138.232.18.220/tool/ceta.

| Strategy | TTT2 | CeTA |
|----------|------|------|
| FAST | YES | **CERTIFIED** |
| LPO | YES | **CERTIFIED** |
| COMP | YES | **CERTIFIED** |
| KBO | MAYBE | REJECTED termination-assumption CPF; no proof or refutation |
| POLY | MAYBE | REJECTED termination-assumption CPF; no proof or refutation |
| MAT(2) | MAYBE | REJECTED termination-assumption CPF; no proof or refutation |
| MAT(3) | MAYBE | REJECTED termination-assumption CPF; no proof or refutation |
| FBI | MAYBE | N/A |

FAST, LPO, and COMP certify under the recorded strategies. The remaining bounded
searches produced no termination certificate. MAYBE and CeTA rejection of a
termination-assumption CPF are never used to infer that a method family fails.
