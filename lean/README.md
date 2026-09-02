# Lean Answer-Evidence Project

This folder is the public Lean 4 project for the benchmark's mechanized
evidence.
It is generated mechanically from the source `lean/` tree by
`3.public-repo/build_3_lean.py`.

## Scope

The export contains two lanes:

- `KO7Benchmark` — the locked answer-key lane used by the scoring pipeline;
- `KO7BenchmarkTheory` — the separate theory lane used for theorem-level
  manuscript claims, when that root exists in the source tree.

The answer-key lane is gated by a frozen file inventory, so future theory-side
additions cannot silently change the scoring provenance surface. If a Lean
theorem appears in `../scoring/answer-key/answer_key.json`, it should
resolve inside the locked `KO7Benchmark` lane.

## Build

Requires Lean 4 v4.22.0-rc4. The public export pins dependencies in
`lakefile.lean` and `lake-manifest.json`.

From this folder:

```powershell
lake update
lake build KO7Benchmark
lake build KO7BenchmarkTheory
```

## How To Audit The Answer Chain

1. Read `../scoring/answer-key/answer_key.json`.
2. For each `lean_theorems` entry, search this folder for the theorem or
   definition name.
3. Open the matching Lean file and inspect whether it proves a positive
   answer, records an answer-key row, or gives a counterexample.
4. Compare the same surface to the TTT2 artifacts in
   `../TTT2-Artifacts/` when a termination-prover certificate is part
   of the evidence.

The scoring scripts do not run Lean. Lean is the mechanized provenance
layer behind the answer key and the theorem appendix; `../scoring/` is the
deterministic CSV verdict layer.

## Theory Lane Inventory (updated 2026-07-02)

`KO7BenchmarkTheory` collects the witness-order, operational-incompleteness,
rename-invariance, boundary-factorization, certificate-bridge,
pseudo-witness, META-HALT, and `PaperB/` theory-mirror modules. The
2026-07-02 expansion added six `PaperB/` modules mechanizing the previously
manuscript-level theory of `Rahnama_PRT_Benchmark.tex` section 3:

| Module | Content | Headline anchors |
|---|---|---|
| `PaperB/SemanticTransport` | Semantic layers, verifiers, Galois interfaces, witness/property transport, composition, cross-layer transfer, interface bottleneck; schema instance fully populated | `transport_delivers_property`, `schema_interface_bottleneck` |
| `PaperB/PseudoWitnessMass` | Verifier/pseudo masses, free energies, bottleneck signature, signature-domination equivalence + satisfiability witness | `bottleneckSignature_iff_pseudoDomination` |
| `PaperB/ExhaustionGap` | Supervisory catalogs, exhaustion gap, typed-abstention counting bound, 12-class direct-measure catalog enum, recursor certificate bound | `typedAbstention_length_ge_exhaustionGap`, `ko7_typedAbstention_certificate_bound` |
| `PaperB/SearchBudgetInvariance` | Budgeted searches, confinement, representation-lift requirement, budget-uniform non-admissibility with truth-side contrast | `confined_search_never_admissible`, `confined_truth_without_admissibility` |
| `PaperB/EntropyMonotone` | Finite Shannon entropy, pushforward monotonicity, verdict-first signature bound over `MethodFamily` | `shannonEntropy_pushforward_le`, `verdict_entropy_le_method_entropy` |
| `PaperB/ContractCoherence` | Answer-key coherence audit (admissible implies adequate; adequate implies truth; no incoherent row) + Schema B control row invariance | `answerKey_never_incoherent`, `schemaB_control_row_invariance` |

Audit status: every headline declaration above passes `#print axioms` inside
the baseline `{propext, Classical.choice, Quot.sound}` or is axiom-free
(audit driver kept outside this release, not in any build
target). No `sorry`, `admit`, `axiom`, or `native_decide` anywhere in the
six modules. Scope notes live in each module header; in particular the
`SemanticTransport` transport realization supplies the full-TRS fact
through the local nonlinear witness and does not mechanize the Arts-Giesl
soundness metatheorem, and the `ExhaustionGap` 12-class enum is catalog
bookkeeping (the additive member is refuted locally; the remaining classes
are cited from the orientation-boundary artifact).
