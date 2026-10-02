# Schema Test B New System: Method Evidence Matrix

System:

```text
(VAR x y n)
(RULES
  F(x, y, Z) -> x
  F(x, y, S(n)) -> G(y, F(x, y, n))
)
```

This file records the definitive artifact status for the five prompt methods.
It deliberately separates **TTT2 / CeTA certificates** from **Lean-kernel
certificates**. The local machine has no `ttt2` or `ceta` binary, so no fresh
CeTA certificates were generated locally.

| Slot | Prompt method | Mathematical adequacy | Boundary status | TTT2 / CeTA artifact | Lean artifact |
|---|---|---:|---:|---|---|
| A | LPO with precedence `F > G > S > Z` | yes | external | `Schema_B_New_System_LPO.cpf`, CeTA `CERTIFIED` | `SchemaBNewSystemFullProofs.slotA_LPO_full_certificate`; `BenchmarkContract.schemaBNewSystem_A_LPO_full_method_backed` |
| B | nonlinear polynomial `[F]=x+(y+1)(n+1)` | yes | external | `Schema_B_New_System_POLY.cpf` is a `MAYBE`/rejection artifact, not a certificate | `NonCollapsingPoly.p2_step_decreases`; `NonCollapsingPoly.wf_StepRev_p2`; `SchemaBNewSystemFullProofs.slotB_nonlinearPoly_full_certificate`; `BenchmarkContract.schemaBNewSystem_B_nonlinearPoly_full_method_backed` |
| C | MPO with precedence `F > G > S > Z`, multiset status | yes | external | none | Native root MPO: `SchemaMPO.mpo_orients_rootStep`, `SchemaMPO.wf_MPORev`, `SchemaMPO.wf_RootStepRev_mpo`; full contextual certificate: `SchemaBNewSystemFullProofs.slotC_MPO_full_certificate`; contract theorem: `BenchmarkContract.schemaBNewSystem_C_MPO_full_method_backed` |
| D | dependency pairs with subterm criterion, projection to the third `F` argument | yes | in-boundary | `Schema_B_New_System_FAST.cpf` and `Schema_B_New_System_HYDRA.cpf`, CeTA `CERTIFIED` | `CandidateD.DPPair.succ`; `CandidateD.dp_pair_decreases`; `CandidateDBridge.candidateD_full_trs_wf`; `SchemaBNewSystemFullProofs.slotD_DP_full_certificate`; `BenchmarkContract.schemaBNewSystem_D_DP_full_method_backed` |
| E | exponential interpretation `[F]=(x+y+2)^(n+1)` | yes | external | none, TTT2 has no exponential-interpretation strategy | `ExponentialInterp.eInterp_step_decreases`; `ExponentialInterp.wf_StepRev_expInterp`; `SchemaBNewSystemFullProofs.slotE_exponential_full_certificate`; `BenchmarkContract.schemaBNewSystem_E_exponential_full_method_backed` |

Combined Lean closeout theorem:

```lean
KO7Benchmark.BenchmarkContract.schemaBNewSystem_all_five_full_method_backed
KO7Benchmark.SchemaTests.SchemaBNewSystemFullProofs.schemaBNewSystem_all_slots_have_full_certificates
```

Interpretation:

- A and D have genuine TTT2 / CeTA certificates for this exact TRS, by reuse
  of byte-identical schema-kernel CPF artifacts.
- B, C, and E do not have successful TTT2 / CeTA certificates in this folder.
  Their definitive adequacy evidence is Lean-kernel evidence.
- C is intentionally recorded with two layers: a native specialized MPO
  root-orientation / root-termination proof, and a benchmark-local full
  contextual certificate. It is not recorded as a generic MPO library or as a
  successful TTT2 MPO certificate.
