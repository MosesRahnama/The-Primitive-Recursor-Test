/-
  SANS path-order support with precedence F > G > S > Z.

  This mirrors the existing Schema-A candidate-A file: we do not build a
  generic LPO library here. We record the concrete local obligations behind
  the SANS path-order witness and close the success status with the existing
  benchmark-local strong-normalization proof from `LinearWitness.lean`.
-/
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.SANSTests.LinearWitness

namespace KO7Benchmark.SANSTests.PathOrderSupport

open KO7Benchmark.SANSTests
open SANSTerm

inductive PrecSym where
  | var | z | s | g | f
deriving DecidableEq, Repr

def rootSym : SANSTerm → PrecSym
  | var _ => PrecSym.var
  | z => PrecSym.z
  | s _ => PrecSym.s
  | g _ => PrecSym.g
  | f _ _ _ => PrecSym.f

def precRank : PrecSym → Nat
  | PrecSym.var => 0
  | PrecSym.z => 1
  | PrecSym.s => 2
  | PrecSym.g => 3
  | PrecSym.f => 4

@[simp] theorem rootSym_var (n : Nat) : rootSym (var n) = PrecSym.var := rfl
@[simp] theorem rootSym_z : rootSym z = PrecSym.z := rfl
@[simp] theorem rootSym_s (t : SANSTerm) : rootSym (s t) = PrecSym.s := rfl
@[simp] theorem rootSym_g (t : SANSTerm) : rootSym (g t) = PrecSym.g := rfl
@[simp] theorem rootSym_f (x y n : SANSTerm) : rootSym (f x y n) = PrecSym.f := rfl

@[simp] theorem prec_F_gt_G : precRank PrecSym.g < precRank PrecSym.f := by decide
@[simp] theorem prec_G_gt_S : precRank PrecSym.s < precRank PrecSym.g := by decide
@[simp] theorem prec_S_gt_Z : precRank PrecSym.z < precRank PrecSym.s := by decide
@[simp] theorem prec_Z_gt_var : precRank PrecSym.var < precRank PrecSym.z := by decide

abbrev stepWitness : SANSTerm → Nat := LinearWitness.mu

theorem root_base_supported (x y : SANSTerm) :
    stepWitness x < stepWitness (f x y z) := by
  simpa [stepWitness] using LinearWitness.mu_root_base x y

theorem recursive_call_smaller (x y n : SANSTerm) :
    stepWitness (f x y n) < stepWitness (f x y (s n)) := by
  simp [stepWitness, LinearWitness.mu]

theorem declares_F_over_G (x y n : SANSTerm) :
    precRank (rootSym (g (f x y n))) < precRank (rootSym (f x y (s n))) := by
  simp [precRank, rootSym]

theorem root_succ_supported (x y n : SANSTerm) :
    stepWitness (g (f x y n)) < stepWitness (f x y (s n)) := by
  change LinearWitness.mu (g (f x y n)) < LinearWitness.mu (f x y (s n))
  exact LinearWitness.mu_root_succ x y n

abbrev StepRev : SANSTerm → SANSTerm → Prop := LinearWitness.StepRev

theorem pathOrder_success_status : WellFounded StepRev := by
  exact LinearWitness.wf_StepRev

end KO7Benchmark.SANSTests.PathOrderSupport
