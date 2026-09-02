/-
  Candidate (D): Dependency pairs with subterm criterion,
  projecting to the third argument of F.

  Status: SUCCEEDS (in the narrow DP-pair sense).

  The extracted dependency pair from the recursive rule is:
    F(x, y, S(n))  →  F(x, y, n)

  The projection sDepth on the third argument of F gives a strict
  decrease: sDepth(S(n)) = sDepth(n) + 1 > sDepth(n).

  This file formalizes that the extracted DP problem is well-founded.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.CandidateD

open KO7Benchmark.SchemaTests
open SKTerm

/-- The extracted dependency pair from the recursive rule. -/
inductive DPPair : SKTerm → SKTerm → Prop
  | succ (x y n : SKTerm) : DPPair (f x y (s n)) (f x y n)

/-- Projection to S-depth of the third argument. -/
def sDepth : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => sDepth t + 1
  | g _ _ => 0
  | f _ _ n => sDepth n

@[simp] theorem sDepth_var (n : Nat) : sDepth (var n) = 0 := rfl
@[simp] theorem sDepth_z : sDepth z = 0 := rfl
@[simp] theorem sDepth_s (t : SKTerm) : sDepth (s t) = sDepth t + 1 := rfl
@[simp] theorem sDepth_g (a b : SKTerm) : sDepth (g a b) = 0 := rfl
@[simp] theorem sDepth_f (x y n : SKTerm) : sDepth (f x y n) = sDepth n := rfl

/-- Every DP pair strictly decreases the projection. -/
theorem dp_pair_decreases : ∀ {a b : SKTerm}, DPPair a b → sDepth b < sDepth a
  | _, _, DPPair.succ x y n => by
      simp [sDepth]

def DPPairRev : SKTerm → SKTerm → Prop := fun a b => DPPair b a

/-- The extracted DP problem is well-founded. -/
theorem wf_DPPairRev : WellFounded DPPairRev := by
  let R : SKTerm → SKTerm → Prop := InvImage (· < ·) sDepth
  have hsub : Subrelation DPPairRev R := by
    intro a b hab
    exact dp_pair_decreases hab
  exact Subrelation.wf hsub (InvImage.wf (fun t : SKTerm => sDepth t) Nat.lt_wfRel.wf)

/-- The DP pair is mechanically extracted from the recursive root rule. -/
theorem rec_rule_extracts_pair (x y n : SKTerm) :
    RootStep (f x y (s n)) (g y (f x y n)) ∧ DPPair (f x y (s n)) (f x y n) := by
  exact ⟨RootStep.succ x y n, DPPair.succ x y n⟩

end KO7Benchmark.SchemaTests.CandidateD

