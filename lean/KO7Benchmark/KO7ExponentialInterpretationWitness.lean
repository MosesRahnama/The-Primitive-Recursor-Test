/-
  Exact positive-integer exponential interpretation asserted in the Test 01
  fruit response `gemini-3.1-pro-preview-fruit__2026-06-28T17-31-03-00056`.

    void                    = 1
    delta(t), integrate(t) = E(t) + 1
    merge(t,u), app(t,u)   = E(t) + E(u) + 1
    recDelta(b,s,n)        = E(b) + (E(s) + 1) * 2 ^ E(n)
    eqW(a,b)               = E(a) + E(b) + 5

  The file checks all eight rules and strict monotonicity in every context.
  It establishes mathematical adequacy only; benchmark-boundary admissibility
  remains a separate policy question.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.KO7ContextClosure

namespace KO7Benchmark.KO7ExponentialInterpretationWitness

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

@[simp] def expInterp : Trace → Nat
  | void => 1
  | delta t => expInterp t + 1
  | integrate t => expInterp t + 1
  | merge t u => expInterp t + expInterp u + 1
  | app f t => expInterp f + expInterp t + 1
  | recDelta b s n => expInterp b + (expInterp s + 1) * 2 ^ expInterp n
  | eqW a b => expInterp a + expInterp b + 5

theorem expInterp_pos (t : Trace) : 1 ≤ expInterp t := by
  induction t <;> simp_all [expInterp]
  all_goals omega

theorem expInterp_root_decreases : ∀ {t u : Trace}, Step t u → expInterp u < expInterp t
  | _, _, Step.R_int_delta t => by
      have ht := expInterp_pos t
      simp [expInterp]
  | _, _, Step.R_merge_void_left t => by
      simp only [expInterp]
      omega
  | _, _, Step.R_merge_void_right t => by
      simp only [expInterp]
      omega
  | _, _, Step.R_merge_cancel t => by
      have ht := expInterp_pos t
      simp only [expInterp]
      omega
  | _, _, Step.R_rec_zero b s => by
      have hs : 0 < expInterp s + 1 := by omega
      simp only [expInterp]
      nlinarith
  | _, _, Step.R_rec_succ b s n => by
      have hn : 1 ≤ expInterp n := expInterp_pos n
      have hpow : 2 ≤ 2 ^ expInterp n := by
        have h := Nat.pow_le_pow_right (by decide : 0 < (2 : Nat)) hn
        simpa using h
      simp only [expInterp, pow_succ]
      nlinarith
  | _, _, Step.R_eq_refl a => by
      have ha := expInterp_pos a
      simp only [expInterp]
      omega
  | _, _, Step.R_eq_diff a b => by
      simp only [expInterp]
      omega

theorem expInterp_stepCtx_decreases :
    ∀ {t u : Trace}, StepCtx t u → expInterp u < expInterp t
  | _, _, StepCtx.root h => expInterp_root_decreases h
  | _, _, StepCtx.delta h => by
      simpa [expInterp] using Nat.succ_lt_succ (expInterp_stepCtx_decreases h)
  | _, _, StepCtx.integrate h => by
      simpa [expInterp] using Nat.succ_lt_succ (expInterp_stepCtx_decreases h)
  | _, _, StepCtx.mergeLeft h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.mergeRight h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.appLeft h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.appRight h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.recBase h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.recStep (b := b) (s := s) (s' := s') (n := n) h => by
      have hlt := expInterp_stepCtx_decreases h
      have hcoef : expInterp s' + 1 < expInterp s + 1 := Nat.succ_lt_succ hlt
      have hpow : 0 < 2 ^ expInterp n := Nat.pow_pos (by decide)
      have hmul := Nat.mul_lt_mul_of_pos_left hcoef hpow
      simpa only [expInterp, Nat.mul_comm] using Nat.add_lt_add_left hmul (expInterp b)
  | _, _, StepCtx.recCounter (b := b) (s := s) (n := n) (n' := n') h => by
      have hlt := expInterp_stepCtx_decreases h
      have hpow : 2 ^ expInterp n' < 2 ^ expInterp n :=
        Nat.pow_lt_pow_right (by decide : 1 < (2 : Nat)) hlt
      have hcoef : 0 < expInterp s + 1 := by omega
      have hmul := Nat.mul_lt_mul_of_pos_left hpow hcoef
      simpa only [expInterp] using Nat.add_lt_add_left hmul (expInterp b)
  | _, _, StepCtx.eqLeft h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega
  | _, _, StepCtx.eqRight h => by
      have hlt := expInterp_stepCtx_decreases h
      simp only [expInterp]
      omega

/-- Full context-closed strong normalization under the exact response map. -/
theorem wf_StepCtxRev_expInterp : WellFounded StepCtxRev := by
  have hsub : Subrelation StepCtxRev (InvImage (· < ·) expInterp) := by
    intro t u h
    exact expInterp_stepCtx_decreases h
  exact Subrelation.wf hsub (InvImage.wf expInterp Nat.lt_wfRel.wf)

end KO7Benchmark.KO7ExponentialInterpretationWitness
