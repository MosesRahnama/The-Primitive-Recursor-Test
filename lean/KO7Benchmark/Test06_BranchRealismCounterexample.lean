/-
  Test 06: the proposed helper theorem is false on the nested-delta branch.
-/
import KO7Benchmark.KO7Kernel

namespace KO7Benchmark.Test06

open KO7Benchmark.KO7Kernel
open Trace

def kappa : Trace → Nat
  | .void => 0
  | .delta t => kappa t
  | .integrate t => kappa t
  | .merge a b => Nat.max (kappa a) (kappa b)
  | .app a b => Nat.max (kappa a) (kappa b)
  | .recDelta b s (.delta n) => Nat.max (Nat.max (kappa b) (kappa s)) (kappa n) + 1
  | .recDelta b s n => Nat.max (Nat.max (kappa b) (kappa s)) (kappa n)
  | .eqW a b => Nat.max (kappa a) (kappa b)

def lhs : Trace := recDelta void void (delta (delta void))
def mid : Trace := recDelta void void (delta void)
def rhs : Trace := app void mid

theorem nested_delta_values :
    kappa lhs = 1 ∧ kappa mid = 1 ∧ kappa rhs = 1 := by
  constructor
  · simp [lhs, kappa]
  constructor
  · simp [mid, kappa]
  · simp [rhs, mid, kappa]

theorem rec_succ_nested_delta_step : Step lhs rhs := by
  exact Step.R_rec_succ void void (delta void)

theorem kappa_rec_delta_step_is_false :
    ¬ ∀ (b s n : Trace), kappa (recDelta b s (delta n)) = kappa (recDelta b s n) + 1 := by
  intro h
  have hbad := h void void (delta void)
  simp [kappa] at hbad

theorem kappa_rec_succ_drop_is_false :
    ¬ ∀ (b s n : Trace), kappa (app s (recDelta b s n)) < kappa (recDelta b s (delta n)) := by
  intro h
  have hbad := h void void (delta void)
  simp [kappa] at hbad

theorem rec_succ_ground_counterexample :
    Step lhs rhs ∧ kappa rhs = kappa lhs := by
  constructor
  · exact rec_succ_nested_delta_step
  · simp [lhs, rhs, mid, kappa]

end KO7Benchmark.Test06
