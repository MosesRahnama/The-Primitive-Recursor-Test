/-
  A concrete linear polynomial interpretation proving context-closed
  termination of the SANS TRS.

  μ(var)      = 0
  μ(Z)        = 0
  μ(S(t))     = μ(t) + 1
  μ(G(t))     = μ(t)
  μ(F(x,y,n)) = μ(x) + μ(y) + μ(n) + 1

  Rule check:

  * Base rule `F(x, y, Z) -> x`:
      μ(F(x,y,Z)) = μ(x) + μ(y) + 0 + 1  >  μ(x).

  * Step rule `F(x, y, S(n)) -> G(F(x, y, n))`:
      μ(F(x,y,S(n))) = μ(x) + μ(y) + (μ(n)+1) + 1 = μ(x) + μ(y) + μ(n) + 2,
      μ(G(F(x,y,n))) = μ(F(x,y,n))             = μ(x) + μ(y) + μ(n) + 1.

  Every context-closure step is monotone and strictly decreasing under
  `μ` because `μ` is a linear combination with all coefficients equal
  to 1 (so every subterm reduction reduces the enclosing term by the
  same amount).

  The key observation: unlike the duplicating Schema A kernel — where
  `μ(F(x,y,S(n))) = μ(x) + μ(y) + μ(n) + 2` fails to dominate
  `μ(G(y, F(x,y,n))) = μ(y) + μ(x) + μ(y) + μ(n) + 1`, because `y`
  appears twice on the right — SANS's unary `G` means `y` appears at
  most once on either side of every rule, so a linear measure suffices.

  This witness is a boundary-admissible first-order measure argument
  (no external type-theoretic machinery), and it succeeds. This is the
  formal companion to the answer-key claim that the Schema A orientation
  obstruction is lifted in SANS.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel

namespace KO7Benchmark.SANSTests.LinearWitness

open KO7Benchmark.SANSTests
open SANSTerm

def mu : SANSTerm → Nat
  | var _ => 0
  | z => 0
  | s t => mu t + 1
  | g t => mu t
  | f x y n => mu x + mu y + mu n + 1

@[simp] theorem mu_var (n : Nat) : mu (var n) = 0 := rfl
@[simp] theorem mu_z : mu z = 0 := rfl
@[simp] theorem mu_s (t : SANSTerm) : mu (s t) = mu t + 1 := rfl
@[simp] theorem mu_g (t : SANSTerm) : mu (g t) = mu t := rfl
@[simp] theorem mu_f (x y n : SANSTerm) :
    mu (f x y n) = mu x + mu y + mu n + 1 := rfl

theorem mu_root_base (x y : SANSTerm) :
    mu x < mu (f x y z) := by
  simp [mu]; omega

theorem mu_root_succ (x y n : SANSTerm) :
    mu (g (f x y n)) < mu (f x y (s n)) := by
  simp [mu]

theorem mu_step_decreases : ∀ {t u : SANSTerm}, Step t u → mu u < mu t
  | _, _, Step.root (RootStep.base x y) => mu_root_base x y
  | _, _, Step.root (RootStep.succ x y n) => mu_root_succ x y n
  | _, _, Step.s_arg h => by
      simpa [mu] using Nat.succ_lt_succ (mu_step_decreases h)
  | _, _, Step.g_arg h => by
      simpa [mu] using mu_step_decreases h
  | _, _, Step.f_arg1 h => by
      have hlt := mu_step_decreases h
      simp [mu]; omega
  | _, _, Step.f_arg2 h => by
      have hlt := mu_step_decreases h
      simp [mu]; omega
  | _, _, Step.f_arg3 h => by
      have hlt := mu_step_decreases h
      simp [mu]; omega

def StepRev : SANSTerm → SANSTerm → Prop := fun a b => Step b a

/-- The SANS TRS is strongly normalizing under context closure. -/
theorem wf_StepRev : WellFounded StepRev := by
  let R : SANSTerm → SANSTerm → Prop := InvImage (· < ·) mu
  have hsub : Subrelation StepRev R := by
    intro a b hab
    exact mu_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf (fun t : SANSTerm => mu t) Nat.lt_wfRel.wf)

end KO7Benchmark.SANSTests.LinearWitness
