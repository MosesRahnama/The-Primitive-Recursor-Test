/-
  Self-contained KO7 dependency-pair extraction.

  The duplicating recursive rule
    `recDelta b s (delta n) -> app s (recDelta b s n)`
  extracts the single dependency pair
    `recDelta# b s (delta n) -> recDelta# b s n`
  whose third-argument delta-depth strictly decreases. This module proves
  that the extracted DP problem is well-founded, parallel to the Schema-A
  CandidateD construction in `SchemaTests.CandidateD_DependencyPairsWitness`
  but operating on the full 7-constructor KO7 `Trace`.

  The well-foundedness theorem here is the local benchmark-Lean equivalent
  of the authoritative KO7 DP-pair theorem; together with the root-step
  strong-normalization proof in `Test03_Ordinal_AnswerKey`, it closes the
  Test 1 truth-and-method row of the benchmark contract without depending
  on any external Lean artifact.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel

namespace KO7Benchmark.KO7DependencyPairs

open KO7Benchmark.KO7Kernel
open Trace

/-- Extracted recursive-call dependency pair from `R_rec_succ`. -/
inductive DPPair : Trace → Trace → Prop
  | succ (b s n : Trace) : DPPair (recDelta b s (delta n)) (recDelta b s n)

/-- Delta-nesting depth at the third-argument position of the active
    `recDelta` site. Constants outside that position contribute zero. -/
def deltaDepth : Trace → Nat
  | void => 0
  | delta t => deltaDepth t + 1
  | integrate _ => 0
  | merge _ _ => 0
  | app _ _ => 0
  | recDelta _ _ n => deltaDepth n
  | eqW _ _ => 0

@[simp] theorem deltaDepth_void : deltaDepth void = 0 := rfl
@[simp] theorem deltaDepth_delta (t : Trace) : deltaDepth (delta t) = deltaDepth t + 1 := rfl
@[simp] theorem deltaDepth_recDelta (b s n : Trace) :
    deltaDepth (recDelta b s n) = deltaDepth n := rfl

/-- Every DP pair strictly decreases the projection. -/
theorem dp_pair_decreases : ∀ {a b : Trace}, DPPair a b → deltaDepth b < deltaDepth a
  | _, _, DPPair.succ b s n => by
      simp [deltaDepth]

/-- Reverse relation used for the `WellFounded` statement. -/
def DPPairRev : Trace → Trace → Prop := fun a b => DPPair b a

/-- The extracted KO7 DP problem is well-founded under projection on the
    third-argument delta-depth. -/
theorem wf_DPPairRev : WellFounded DPPairRev := by
  let R : Trace → Trace → Prop := InvImage (· < ·) deltaDepth
  have hsub : Subrelation DPPairRev R := by
    intro a b hab
    exact dp_pair_decreases hab
  exact Subrelation.wf hsub (InvImage.wf (fun t : Trace => deltaDepth t) Nat.lt_wfRel.wf)

/-- The extracted DP pair already admits a simple linear base order on the
    counter coordinate. The function-form witness is recorded here so the
    benchmark answer-key bookkeeping can cite it without a `∃` introduction. -/
theorem extracted_dp_problem_has_linear_base_order :
    ∃ μ : Trace → Nat, ∀ {a b : Trace}, DPPair a b → μ b < μ a :=
  ⟨deltaDepth, dp_pair_decreases⟩

/-- The duplicating root step really does extract the canonical DP pair. -/
theorem rec_succ_extracts_pair (b s n : Trace) :
    Step (recDelta b s (delta n)) (app s (recDelta b s n)) ∧
      DPPair (recDelta b s (delta n)) (recDelta b s n) :=
  ⟨Step.R_rec_succ b s n, DPPair.succ b s n⟩

end KO7Benchmark.KO7DependencyPairs
