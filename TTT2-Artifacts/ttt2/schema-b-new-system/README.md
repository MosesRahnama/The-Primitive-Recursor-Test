# TTT2 / CeTA Artifacts: Schema Test B New System

External termination evidence for the **Schema Test B New System** surface.

## The system (duplicating)

```text
(VAR x y n)
(RULES
  F(x, y, Z) -> x
  F(x, y, S(n)) -> G(y, F(x, y, n))
)
```

`Schema-Test-B-New-System.trs` in this folder. Its SHA-256 is
`65698e5ccec51ff49ca5b1763c3befafa71002725885c7790544e786ce828b9d`, which is
**byte-identical** to the duplicating schema kernel
`../schema/Test-07-Schema-Kernel.trs`. This is the SAME TRS used by Schema B;
Schema B New System keeps the system and changes only the five-slot method menu.

## Provenance (important, read this)

The `.cpf` certificates here are **copies of the schema-kernel certificates**
from `../schema/`, produced 2026-04-07 on the remote TTT2 host
`http://138.232.18.220/tool/ttt2` and certified by CeTA 2.36. They apply to
Schema B New System **because the TRS is the same file** (same SHA-256), not
because a fresh Schema-B-New-System run was performed. TTT2 is a remote
web-hosted tool; it cannot be invoked from the local environment, so these
artifacts were cited, not regenerated.

Do NOT confuse this folder with `../schema-new-system/`, which is the
NON-duplicating Schema **A** New System (`F(x,y,S(n)) -> G(F(x,y,n))`), a
different TRS on which all eight strategies certify.

## Per-method evidence (the five Schema B New System slots)

A CeTA certificate proves that one named method terminates the TRS. In the
recorded TTT2 runs, the path-order and dependency-pair strategies certify. The
bounded direct POLY/KBO/MAT searches return MAYBE, which is search-inconclusive
and not a refutation. The exact nonlinear-polynomial, MPO, and exponential
methods in this test are therefore supported by their named Lean developments,
not inferred from failed TTT2 searches.

| Slot | Method | TTT2 / CeTA | Definitive proof |
|---|---|---|---|
| A | LPO, F > G > S > Z | **YES / CERTIFIED** -> `Schema_B_New_System_LPO.cpf` | CeTA (Isabelle kernel) + Lean |
| B | nonlinear poly `x+(y+1)(n+1)` | MAYBE; termination-assumption CPF rejected, so no TTT2 proof or refutation | **Lean** (`NonCollapsingPoly.wf_StepRev_p2`) |
| C | MPO, F > G > S > Z | none (no MPO strategy in the tested set) | **Lean native MPO** (`SchemaMPO.wf_RootStepRev_mpo`, Veblen ordinal) |
| D | DP + subterm, pi(F)=3 | **YES / CERTIFIED** -> `Schema_B_New_System_FAST.cpf`, `Schema_B_New_System_HYDRA.cpf` | CeTA (Isabelle kernel) + Lean |
| E | exponential `(x+y+2)^(n+1)` | none (TTT2 has no exponential method) | **Lean** (`ExponentialInterp.wf_StepRev_expInterp`) |

Machine-readable form: `schema_b_new_system_certification_summary.json`.
Reviewer-facing matrix: `METHOD_EVIDENCE_MATRIX.md`.
CSV matrix: `method_evidence_matrix.csv`.

Also in this folder: the certified copies `Schema_B_New_System_LPO.cpf` /
`Schema_B_New_System_COMP.cpf`, the search-inconclusive MAYBE outputs
`Schema_B_New_System_KBO.cpf`, `Schema_B_New_System_MAT2.cpf`,
`Schema_B_New_System_MAT3.cpf`, `Schema_B_New_System_POLY.cpf`, and the CeTA
verification log `Schema_B_New_System_CeTA_certification.txt`.

Bottom line: every method has a complete kernel-checked formal proof of
mathematical adequacy, but not every method has a TTT2 certificate. A and D
come from the CeTA (Isabelle) kernel while B, C, E come from the Lean kernel.
C has native Lean MPO root evidence plus a Lean full-contextual certificate;
it is not recorded as a generic MPO library or as a successful TTT2 MPO
certificate. There is no method with only informal evidence.

## If you want fresh TTT2 runs for B, C, E

These must be run on the TTT2 host (the local environment has no TTT2 binary).
Submit `Schema-Test-B-New-System.trs` with:

```text
B (nonlinear poly):  './ttt2' '-C' "" '-cpf' '-t' '-s' 'poly -direct -ib 6 -ob 8' 'input.trs'
C (MPO):             './ttt2' '-C' "" '-cpf' '-t' '-s' 'rpo' 'input.trs'   (TTT2 has no bare 'mpo'; RPO with multiset status is the nearest preset)
E (exponential):     not expressible as a TTT2 strategy (no exponential interpretation method)
```

The tested POLY bound returned MAYBE; an RPO run may or may not match the
multiset-status shape, and E is outside TTT2's recorded strategy language. A
TTT2 YES for B or C would provide an additional external certificate, but a
MAYBE result would remain non-evidence. If any run returns YES plus CERTIFIED,
archive the `.cpf` here and update `schema_b_new_system_certification_summary.json`.
