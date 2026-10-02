/-
  Candidate (E) for Schema Test B New System: a concrete exponential
  (elementary) interpretation over N that orients the full context-closed
  duplicating schema-kernel TRS.

    [var]       = 0
    [Z]         = 0
    [S(t)]      = [t] + 1
    [G(a,b)]    = [a] + [b]
    [F(x,y,n)]  = ([x] + [y] + 2) ^ ([n] + 1)

  Root rule checks:

  * base  F(x,y,Z) -> x:
      ([x]+[y]+2)^1 = [x]+[y]+2 > [x].

  * succ  F(x,y,S(n)) -> G(y, F(x,y,n)):
      with B = [x]+[y]+2 and k = [n]+1,
      LHS = B^(k+1) = B^k * B >= 2 * B^k = B^k + B^k >= B^k + B
          = B^k + [x] + [y] + 2  >  [y] + B^k = RHS.

  The interpretation is strictly monotone in every argument position:
  the base strictly grows in [x] and [y] with a positive exponent, and
  the exponent strictly grows in [n] with base >= 2. So the strict
  decrease lifts through every context. The duplication of `y` in the
  recursive rule is absorbed because the base is raised to a strictly
  smaller exponent on the right: exponential growth in the counter
  dominates one extra additive copy of the payload.

  Relation: Step (full contextual closure of both root rules).
  Property: SN, by strict measure decrease into Nat.
  Trust: kernel-only; no axioms beyond the mathlib baseline.
  Boundary status: mathematically adequate but boundary-EXTERNAL (the
  interpretation is imported, exactly like a path order or the
  nonlinear polynomial). This is the E-row positive witness for the
  Schema-B-New-System all-orienting menu.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.ExponentialInterp

open KO7Benchmark.SchemaTests
open SKTerm

def eInterp : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => eInterp t + 1
  | g a b => eInterp a + eInterp b
  | f x y n => (eInterp x + eInterp y + 2) ^ (eInterp n + 1)

@[simp] theorem eInterp_var (n : Nat) : eInterp (var n) = 0 := rfl
@[simp] theorem eInterp_z : eInterp z = 0 := rfl
@[simp] theorem eInterp_s (t : SKTerm) : eInterp (s t) = eInterp t + 1 := rfl
@[simp] theorem eInterp_g (a b : SKTerm) :
    eInterp (g a b) = eInterp a + eInterp b := rfl
@[simp] theorem eInterp_f (x y n : SKTerm) :
    eInterp (f x y n) = (eInterp x + eInterp y + 2) ^ (eInterp n + 1) := rfl

theorem eInterp_root_base (x y : SKTerm) : eInterp x < eInterp (f x y z) := by
  have h : eInterp (f x y z) = eInterp x + eInterp y + 2 := by
    simp [eInterp]
  omega

theorem eInterp_root_succ (x y n : SKTerm) :
    eInterp (g y (f x y n)) < eInterp (f x y (s n)) := by
  have hLHS : eInterp (f x y (s n)) =
      (eInterp x + eInterp y + 2) ^ (eInterp n + 1) * (eInterp x + eInterp y + 2) := by
    simp [eInterp, pow_succ]
  have hRHS : eInterp (g y (f x y n)) =
      eInterp y + (eInterp x + eInterp y + 2) ^ (eInterp n + 1) := by
    simp [eInterp]
  have hself : (eInterp x + eInterp y + 2) ≤
      (eInterp x + eInterp y + 2) ^ (eInterp n + 1) :=
    Nat.le_self_pow (by omega) _
  rw [hRHS, hLHS]
  calc eInterp y + (eInterp x + eInterp y + 2) ^ (eInterp n + 1)
      < (eInterp x + eInterp y + 2) + (eInterp x + eInterp y + 2) ^ (eInterp n + 1) := by
        omega
    _ ≤ (eInterp x + eInterp y + 2) ^ (eInterp n + 1) +
          (eInterp x + eInterp y + 2) ^ (eInterp n + 1) := by
        omega
    _ = (eInterp x + eInterp y + 2) ^ (eInterp n + 1) * 2 := by
        ring
    _ ≤ (eInterp x + eInterp y + 2) ^ (eInterp n + 1) * (eInterp x + eInterp y + 2) :=
        Nat.mul_le_mul (Nat.le_refl _) (by omega)

theorem eInterp_step_decreases : ∀ {t u : SKTerm}, Step t u → eInterp u < eInterp t
  | _, _, Step.root (RootStep.base x y) => eInterp_root_base x y
  | _, _, Step.root (RootStep.succ x y n) => eInterp_root_succ x y n
  | _, _, Step.s_arg h => by
      have := eInterp_step_decreases h
      simp only [eInterp_s]
      omega
  | _, _, Step.g_left h => by
      have := eInterp_step_decreases h
      simp only [eInterp_g]
      omega
  | _, _, Step.g_right h => by
      have := eInterp_step_decreases h
      simp only [eInterp_g]
      omega
  | _, _, Step.f_arg1 h => by
      have hlt := eInterp_step_decreases h
      simp only [eInterp_f]
      exact Nat.pow_lt_pow_left (by omega) (Nat.succ_ne_zero _)
  | _, _, Step.f_arg2 h => by
      have hlt := eInterp_step_decreases h
      simp only [eInterp_f]
      exact Nat.pow_lt_pow_left (by omega) (Nat.succ_ne_zero _)
  | _, _, Step.f_arg3 h => by
      have hlt := eInterp_step_decreases h
      simp only [eInterp_f]
      exact Nat.pow_lt_pow_right (by omega) (by omega)

def StepRev : SKTerm → SKTerm → Prop := fun a b => Step b a

/-- Strong normalization of the duplicating schema-kernel TRS, witnessed
independently by the exponential interpretation `eInterp`.

Relation: `Step` (full contextual closure). Property: SN.
Proves: well-foundedness of the reversed context-closed step relation.
Does not prove: anything about boundary admissibility; the interpretation
is imported, so the E row stays adequate-not-admissible. -/
theorem wf_StepRev_expInterp : WellFounded StepRev := by
  have hsub : Subrelation StepRev (InvImage (· < ·) eInterp) := by
    intro a b hab
    exact eInterp_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf eInterp Nat.lt_wfRel.wf)

end KO7Benchmark.SchemaTests.ExponentialInterp
