/-
  SANS KBO-style local support.

  We record the concrete ingredients behind the archived TTT2 KBO success:

    * the variable condition holds on both rules;
    * the base rule strictly drops the chosen weight;
    * the recursive rule is weight-tied and broken by precedence F > G.

  As elsewhere in this benchmark package, we close the full success status by
  citing the local strong-normalization witness already proved in
  `LinearWitness.lean`.
-/
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.SANSTests.LinearWitness
import KO7Benchmark.SANSTests.PathOrderSupport

namespace KO7Benchmark.SANSTests.KBOStyleSupport

open KO7Benchmark.SANSTests
open SANSTerm

def countVar (v : Nat) : SANSTerm → Nat
  | var w => if v = w then 1 else 0
  | z => 0
  | s t => countVar v t
  | g t => countVar v t
  | f x y n => countVar v x + countVar v y + countVar v n

def baseLhs : SANSTerm := f (var 0) (var 1) z
def baseRhs : SANSTerm := var 0
def succLhs : SANSTerm := f (var 0) (var 1) (s (var 2))
def succRhs : SANSTerm := g (f (var 0) (var 1) (var 2))

theorem variable_condition_base (v : Nat) :
    countVar v baseRhs ≤ countVar v baseLhs := by
  cases v with
  | zero => simp [baseLhs, baseRhs, countVar]
  | succ v =>
      cases v with
      | zero => simp [baseLhs, baseRhs, countVar]
      | succ v => simp [baseLhs, baseRhs, countVar]

theorem variable_condition_succ (v : Nat) :
    countVar v succRhs ≤ countVar v succLhs := by
  cases v with
  | zero => simp [succLhs, succRhs, countVar]
  | succ v =>
      cases v with
      | zero => simp [succLhs, succRhs, countVar]
      | succ v =>
          cases v with
          | zero => simp [succLhs, succRhs, countVar]
          | succ v => simp [succLhs, succRhs, countVar]

def weight : SANSTerm → Nat
  | var _ => 1
  | z => 1
  | s t => weight t + 1
  | g t => weight t + 1
  | f x y n => weight x + weight y + weight n

theorem weight_pos : ∀ t : SANSTerm, 0 < weight t
  | var _ => by simp [weight]
  | z => by simp [weight]
  | s t => by
      have ht := weight_pos t
      simp [weight, ht]
  | g t => by
      have ht := weight_pos t
      simp [weight, ht]
  | f x y n => by
      have hx := weight_pos x
      have hy := weight_pos y
      have hn := weight_pos n
      simp [weight]
      omega

theorem root_base_weight_drop (x y : SANSTerm) :
    weight x < weight (f x y z) := by
  have hy := weight_pos y
  simp [weight]
  omega

theorem root_succ_weight_tie (x y n : SANSTerm) :
    weight (g (f x y n)) = weight (f x y (s n)) := by
  simp [weight]
  omega

theorem root_succ_prec_breaks_tie (x y n : SANSTerm) :
    PathOrderSupport.precRank (PathOrderSupport.rootSym (g (f x y n))) <
      PathOrderSupport.precRank (PathOrderSupport.rootSym (f x y (s n))) := by
  simp [PathOrderSupport.precRank, PathOrderSupport.rootSym]

abbrev StepRev : SANSTerm → SANSTerm → Prop := LinearWitness.StepRev

theorem kbo_style_success_status : WellFounded StepRev := by
  exact LinearWitness.wf_StepRev

end KO7Benchmark.SANSTests.KBOStyleSupport
