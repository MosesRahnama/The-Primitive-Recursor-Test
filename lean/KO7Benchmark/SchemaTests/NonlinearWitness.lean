/-
  A concrete nonlinear interpretation proving context-closed termination
  of the schema-kernel TRS.

  μ(Z)        = 0
  μ(S(t))     = μ(t) + 1
  μ(G(a,b))   = μ(a) + μ(b)
  μ(F(x,y,n)) = (μ(y) + 1) * (μ(n) + 1) + μ(x) + 1

  This witness is intentionally external and nonlinear. It is not an
  in-boundary direct measure in the benchmark sense; it is a global escape
  witness confirming termination of the full context-closed TRS.

  Source: adapted from the companion paper's nonlinear polynomial witness.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.NonlinearWitness

open KO7Benchmark.SchemaTests
open SKTerm

def muW : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => muW t + 1
  | g a b => muW a + muW b
  | f x y n => (muW y + 1) * (muW n + 1) + muW x + 1

@[simp] theorem muW_var (n : Nat) : muW (var n) = 0 := rfl
@[simp] theorem muW_z : muW z = 0 := rfl
@[simp] theorem muW_s (t : SKTerm) : muW (s t) = muW t + 1 := rfl
@[simp] theorem muW_g (a b : SKTerm) : muW (g a b) = muW a + muW b := rfl
@[simp] theorem muW_f (x y n : SKTerm) :
    muW (f x y n) = (muW y + 1) * (muW n + 1) + muW x + 1 := rfl

theorem muW_root_base (x y : SKTerm) :
    muW x < muW (f x y z) := by
  simp [muW]
  omega

theorem muW_root_succ (x y n : SKTerm) :
    muW (g y (f x y n)) < muW (f x y (s n)) := by
  have hEq :
      muW (f x y (s n)) = muW (g y (f x y n)) + 1 := by
    simp [muW]
    ring
  rw [hEq]
  omega

theorem muW_step_decreases : ∀ {t u : SKTerm}, Step t u → muW u < muW t
  | _, _, Step.root (RootStep.base x y) => muW_root_base x y
  | _, _, Step.root (RootStep.succ x y n) => muW_root_succ x y n
  | _, _, Step.s_arg h => by
      simpa [muW] using Nat.succ_lt_succ (muW_step_decreases h)
  | _, _, Step.g_left h => by
      have hlt := muW_step_decreases h
      simp [muW]
      omega
  | _, _, Step.g_right h => by
      have hlt := muW_step_decreases h
      simp [muW]
      omega
  | _, _, Step.f_arg1 h => by
      have hlt := muW_step_decreases h
      simp [muW]
      omega
  | _, _, Step.f_arg2 h => by
      have hlt := muW_step_decreases h
      simp [muW]
      omega
  | _, _, Step.f_arg3 h => by
      have hlt := muW_step_decreases h
      simp [muW]
      omega

def StepRev : SKTerm → SKTerm → Prop := fun a b => Step b a

/-- The schema-kernel TRS is strongly normalizing. -/
theorem wf_StepRev : WellFounded StepRev := by
  let R : SKTerm → SKTerm → Prop := InvImage (· < ·) muW
  have hsub : Subrelation StepRev R := by
    intro a b hab
    exact muW_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf (fun t : SKTerm => muW t) Nat.lt_wfRel.wf)

end KO7Benchmark.SchemaTests.NonlinearWitness

