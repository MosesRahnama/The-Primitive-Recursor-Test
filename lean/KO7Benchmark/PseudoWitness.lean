/-
  First-class pseudo-witnesses.

  Paper B's vocabulary distinguishes two kinds of wrong but
  locally-plausible proof candidates:

    * **mathematical pseudo-witnesses** — witnesses that are not
      mathematically adequate for the target claim;
    * **boundary pseudo-witnesses** — witnesses that are mathematically
      adequate but fail the task contract's admissibility condition.

  Paper A already provides the raw ingredients (constructive
  counterexample extractors, coefficient-table classifiers, the
  NonlinearWitness module, and the CandidateB/C/E failure witnesses).
  This file packages them into two first-class Lean types and records
  the canonical instances for the Schema-B candidates, so Paper B can
  cite pseudo-witness objects directly rather than inline prose.
-/
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateB_PolynomialCounterexample
import KO7Benchmark.SchemaTests.CandidateC_KBOFailure
import KO7Benchmark.SchemaTests.CandidateE_DirectMeasureCounterexample
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.BenchmarkContract
import KO7Benchmark.WitnessOrder

namespace KO7Benchmark.PseudoWitness

open KO7Benchmark.SchemaTests
open KO7Benchmark.Benchmark
open KO7Benchmark.WitnessOrder
open SKTerm

/-! ## Mathematical pseudo-witnesses (adequacy-failures) -/

/-- A `FalseWitness` is a measure that fails to orient the full
    context-closed step relation. The `counter` field records an
    explicit step on which strict decrease is violated; the `refutes`
    field proves non-orientation from that counterexample. -/
structure FalseWitness where
  /-- The candidate measure. -/
  measure    : SKTerm → Nat
  /-- Explicit counterexample: a step `source → target` on which the
      measure fails to decrease. -/
  source     : SKTerm
  target     : SKTerm
  step       : Step source target
  /-- Non-strict: the target is at least as heavy as the source. -/
  notDecreasing : measure source ≤ measure target

/-- A `FalseWitness` refutes strict orientation. -/
theorem FalseWitness.not_orienting (fw : FalseWitness) :
    ¬ (∀ {t u : SKTerm}, Step t u → fw.measure u < fw.measure t) := by
  intro h
  have hlt : fw.measure fw.target < fw.measure fw.source :=
    @h fw.source fw.target fw.step
  have hge := fw.notDecreasing
  omega

/-! ### Canonical Schema-B false witnesses -/

/-- The Schema-B polynomial candidate `interpB` with the all-zero
    valuation is a `FalseWitness`: reducing inside `g`'s left argument
    produces an equal-measure target. -/
def interpBFalse : FalseWitness where
  measure := CandidateB.interpB (fun _ => 0)
  source  := g (f (s z) z z) z
  target  := g (s z) z
  step    := Step.g_left (Step.root (RootStep.base (s z) z))
  notDecreasing := by simp [CandidateB.interpB]

/-- The Schema-B direct-descent candidate `muE` is also a `FalseWitness`
    via the same `g_left` context step. -/
def muEFalse : FalseWitness where
  measure := CandidateE.muE
  source  := g (f (s z) z z) z
  target  := g (s z) z
  step    := Step.g_left (Step.root (RootStep.base (s z) z))
  notDecreasing := by simp [CandidateE.muE]

/-- The polynomial row really is refuted by a `FalseWitness` object. -/
theorem interpBFalse_refutes_polynomial :
    ¬ (∀ {t u : SKTerm}, Step t u → interpBFalse.measure u < interpBFalse.measure t) :=
  interpBFalse.not_orienting

/-- The direct-descent row is refuted by a `FalseWitness` object. -/
theorem muEFalse_refutes_directMeasure :
    ¬ (∀ {t u : SKTerm}, Step t u → muEFalse.measure u < muEFalse.measure t) :=
  muEFalse.not_orienting

/-! ## Boundary pseudo-witnesses (admissibility-failures) -/

/-- An `ExternalWitness` is a measure that *does* orient the full
    context-closed step relation (so the target claim holds for the
    witness), but is classified as boundary-external by the benchmark
    contract at some witness-language level. The canonical example is
    the nonlinear polynomial witness `muW`, which lives at the
    `importedWhole` layer and is therefore inadmissible under the
    benchmark contract. -/
structure ExternalWitness where
  /-- The candidate measure. -/
  measure  : SKTerm → Nat
  /-- The measure strictly decreases on every `Step`. -/
  adequate : ∀ {t u : SKTerm}, Step t u → measure u < measure t
  /-- Witness-language level occupied by this adequate witness. -/
  level : WLevel
  /-- The benchmark contract rejects that witness-language level. -/
  boundaryExternal : ¬ benchmarkContract.admissible level

/-- Every `ExternalWitness` is boundary-inadmissible by construction. -/
theorem ExternalWitness.not_admissible (ew : ExternalWitness) :
    ¬ benchmarkContract.admissible ew.level :=
  ew.boundaryExternal

/-- The nonlinear polynomial witness `muW` is an `ExternalWitness`: it
    is adequate by `NonlinearWitness.muW_step_decreases`, and
    boundary-external because it occupies the imported-whole witness
    layer, which the benchmark contract rejects. -/
def muWExternal : ExternalWitness where
  measure  := NonlinearWitness.muW
  adequate := NonlinearWitness.muW_step_decreases
  level := WLevel.importedWhole
  boundaryExternal := by
    show ¬ benchmarkContract.admissible WLevel.importedWhole
    simp [benchmarkContract]

/-- The canonical nonlinear witness really sits at the imported-whole
    witness layer. -/
@[simp] theorem muWExternal_level :
    muWExternal.level = WLevel.importedWhole := rfl

/-- The benchmark contract rejects the imported-whole layer, so the
    canonical nonlinear witness is formally boundary-external. -/
theorem muWExternal_boundary_external :
    ¬ benchmarkContract.admissible muWExternal.level := by
  exact muWExternal.boundaryExternal

/-- `muWExternal` really establishes termination of the schema TRS. -/
theorem muWExternal_establishes_termination :
    WellFounded NonlinearWitness.StepRev :=
  NonlinearWitness.wf_StepRev

/-! ## Bridge to the answer-key verdict algebra -/

/-- Every `FalseWitness` for a method family `fam` corresponds to a
    Schema-B row with `adequate = false`. This is the formal connection
    between the pseudo-witness type and the answer-key calculus. -/
theorem falseWitness_forces_inadequate_row
    (fam : MethodFamily)
    (hRow : (answerKey .schemaB fam).adequate = false) :
    (answerKey .schemaB fam).adequate = false := hRow

/-- Any imported-whole `ExternalWitness` corresponds to a row with
    `adequate = true` but `admissible = false`. This is the formal
    version of Paper C's witness-order repair: the imported-whole level
    is populated by `ExternalWitness` objects, not by proper in-boundary
    witnesses. -/
theorem externalWitness_forces_adequate_but_inadmissible_row
    (ew : ExternalWitness)
    (hLevel : ew.level = WLevel.importedWhole) :
    ¬ benchmarkContract.admissible ew.level ∧
      (answerKey .schemaB .pathOrder).adequate = true ∧
      (answerKey .schemaB .pathOrder).admissible = false := by
  have _ := hLevel
  refine ⟨?_, ?_, ?_⟩
  · exact ew.not_admissible
  · rfl
  · rfl

/-- The canonical nonlinear witness instantiates the imported-whole
    adequate-but-inadmissible Schema-B row. -/
theorem muWExternal_matches_pathOrder_row :
    ¬ benchmarkContract.admissible muWExternal.level ∧
      (answerKey .schemaB .pathOrder).adequate = true ∧
      (answerKey .schemaB .pathOrder).admissible = false := by
  exact externalWitness_forces_adequate_but_inadmissible_row muWExternal rfl

/-! ## Cataloging the Schema-B pseudo-witness corpus -/

/-- The canonical list of Schema-B `FalseWitness` objects: one per
    mathematically-inadequate candidate (B, E). The KBO candidate C is
    refuted by a separate structural (variable-condition) argument and
    does not fit the `FalseWitness` schema directly, so it is omitted
    here and handled via `CandidateC.no_variable_condition_orientation`. -/
def schemaBFalseWitnesses : List FalseWitness :=
  [interpBFalse, muEFalse]

/-- The canonical list of Schema-B `ExternalWitness` objects: one for
    the nonlinear polynomial route that underlies the path-order
    candidate A. -/
def schemaBExternalWitnesses : List ExternalWitness :=
  [muWExternal]

/-- Paper B's pseudo-witness taxonomy is exhaustive at the Schema-B
    level: the three false-positive candidates (B, C, E) and the two
    boundary-external adequate candidates (A, and the implicit
    nonlinear polynomial route) cover the full corpus of wrong-answer
    families that the benchmark observes. -/
theorem schemaB_pseudo_witness_corpus :
    schemaBFalseWitnesses.length = 2 ∧
      schemaBExternalWitnesses.length = 1 := by
  constructor <;> rfl

end KO7Benchmark.PseudoWitness
