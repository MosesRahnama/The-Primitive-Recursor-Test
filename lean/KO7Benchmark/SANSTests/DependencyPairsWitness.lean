/-
  SANS dependency pairs with projection to the third argument of F.

  The recursive rule extracts the pair

    F(x, y, S(n)) -> F(x, y, n)

  and the usual S-depth projection strictly decreases on that pair.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel

namespace KO7Benchmark.SANSTests.DependencyPairsWitness

open KO7Benchmark.SANSTests
open SANSTerm

inductive DPPair : SANSTerm → SANSTerm → Prop
  | succ (x y n : SANSTerm) : DPPair (f x y (s n)) (f x y n)

def sDepth : SANSTerm → Nat
  | var _ => 0
  | z => 0
  | s t => sDepth t + 1
  | g _ => 0
  | f _ _ n => sDepth n

@[simp] theorem sDepth_var (n : Nat) : sDepth (var n) = 0 := rfl
@[simp] theorem sDepth_z : sDepth z = 0 := rfl
@[simp] theorem sDepth_s (t : SANSTerm) : sDepth (s t) = sDepth t + 1 := rfl
@[simp] theorem sDepth_g (t : SANSTerm) : sDepth (g t) = 0 := rfl
@[simp] theorem sDepth_f (x y n : SANSTerm) : sDepth (f x y n) = sDepth n := rfl

theorem dp_pair_decreases : ∀ {a b : SANSTerm}, DPPair a b → sDepth b < sDepth a
  | _, _, DPPair.succ x y n => by
      simp [sDepth]

def DPPairRev : SANSTerm → SANSTerm → Prop := fun a b => DPPair b a

theorem wf_DPPairRev : WellFounded DPPairRev := by
  let R : SANSTerm → SANSTerm → Prop := InvImage (· < ·) sDepth
  have hsub : Subrelation DPPairRev R := by
    intro a b hab
    exact dp_pair_decreases hab
  exact Subrelation.wf hsub (InvImage.wf (fun t : SANSTerm => sDepth t) Nat.lt_wfRel.wf)

theorem rec_rule_extracts_pair (x y n : SANSTerm) :
    RootStep (f x y (s n)) (g (f x y n)) ∧ DPPair (f x y (s n)) (f x y n) := by
  exact ⟨RootStep.succ x y n, DPPair.succ x y n⟩

end KO7Benchmark.SANSTests.DependencyPairsWitness
