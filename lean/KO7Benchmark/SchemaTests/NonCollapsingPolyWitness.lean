/-
  Non-collapsing polynomial interpretations that do orient the Schema A kernel.

  Several Schema A model responses proposed a polynomial interpretation that,
  unlike the collapsing shapes ruled out in `GCollapseBarrier`, depends on every
  load-bearing argument and orients the context-closed TRS. This file
  certifies two such agent-proposed forms as verified termination witnesses.

  Status: mathematically adequate (each orients every `Step`, hence the TRS is
  strongly normalizing) but boundary-EXTERNAL: the interpretation imports the
  well-order on `Nat`, so this is adequate-not-admissible, exactly like a path
  order. It is the positive counterpart to `CandidateB`/`GCollapseBarrier`.

  Form 1 (`p1`):  [Z]=[var]=0, [S t]=[t]+1, [G a b]=[a]+[b], [F x y n]=([x]+[y]+1)*([n]+1)
  Form 2 (`p2`):  [Z]=[var]=0, [S t]=[t]+1, [G a b]=[a]+[b], [F x y n]=[x]+([y]+1)*([n]+1)
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.NonCollapsingPoly

open KO7Benchmark.SchemaTests
open SKTerm

/-! ### Form 1: `[F x y n] = ([x]+[y]+1) * ([n]+1)` -/

def p1 : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => p1 t + 1
  | g a b => p1 a + p1 b
  | f x y n => (p1 x + p1 y + 1) * (p1 n + 1)

@[simp] theorem p1_var (n : Nat) : p1 (var n) = 0 := rfl
@[simp] theorem p1_z : p1 z = 0 := rfl
@[simp] theorem p1_s (t : SKTerm) : p1 (s t) = p1 t + 1 := rfl
@[simp] theorem p1_g (a b : SKTerm) : p1 (g a b) = p1 a + p1 b := rfl
@[simp] theorem p1_f (x y n : SKTerm) :
    p1 (f x y n) = (p1 x + p1 y + 1) * (p1 n + 1) := rfl

theorem p1_root_base (x y : SKTerm) : p1 x < p1 (f x y z) := by
  simp [p1]; nlinarith [p1 x, p1 y]

theorem p1_root_succ (x y n : SKTerm) :
    p1 (g y (f x y n)) < p1 (f x y (s n)) := by
  have hEq : p1 (f x y (s n)) = p1 (g y (f x y n)) + (p1 x + 1) := by
    simp [p1]; ring
  rw [hEq]; omega

theorem p1_step_decreases : ∀ {t u : SKTerm}, Step t u → p1 u < p1 t
  | _, _, Step.root (RootStep.base x y) => p1_root_base x y
  | _, _, Step.root (RootStep.succ x y n) => p1_root_succ x y n
  | _, _, Step.s_arg h => by have := p1_step_decreases h; simp [p1]; omega
  | _, _, Step.g_left h => by have := p1_step_decreases h; simp [p1]; omega
  | _, _, Step.g_right h => by have := p1_step_decreases h; simp [p1]; omega
  | _, _, Step.f_arg1 h => by have := p1_step_decreases h; simp [p1]; nlinarith [this]
  | _, _, Step.f_arg2 h => by have := p1_step_decreases h; simp [p1]; nlinarith [this]
  | _, _, Step.f_arg3 h => by have := p1_step_decreases h; simp [p1]; nlinarith [this]

/-- Strong normalization of the Schema A TRS, witnessed by the non-collapsing
polynomial `p1`. -/
theorem wf_StepRev_p1 : WellFounded (fun a b => Step b a) := by
  have hsub : Subrelation (fun a b => Step b a) (InvImage (· < ·) p1) := by
    intro a b hab
    exact p1_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf p1 Nat.lt_wfRel.wf)

/-! ### Form 2: `[F x y n] = [x] + ([y]+1) * ([n]+1)` -/

def p2 : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => p2 t + 1
  | g a b => p2 a + p2 b
  | f x y n => p2 x + (p2 y + 1) * (p2 n + 1)

@[simp] theorem p2_var (n : Nat) : p2 (var n) = 0 := rfl
@[simp] theorem p2_z : p2 z = 0 := rfl
@[simp] theorem p2_s (t : SKTerm) : p2 (s t) = p2 t + 1 := rfl
@[simp] theorem p2_g (a b : SKTerm) : p2 (g a b) = p2 a + p2 b := rfl
@[simp] theorem p2_f (x y n : SKTerm) :
    p2 (f x y n) = p2 x + (p2 y + 1) * (p2 n + 1) := rfl

theorem p2_root_base (x y : SKTerm) : p2 x < p2 (f x y z) := by
  simp [p2]

theorem p2_root_succ (x y n : SKTerm) :
    p2 (g y (f x y n)) < p2 (f x y (s n)) := by
  have hEq : p2 (f x y (s n)) = p2 (g y (f x y n)) + 1 := by
    simp [p2]; ring
  rw [hEq]; omega

theorem p2_step_decreases : ∀ {t u : SKTerm}, Step t u → p2 u < p2 t
  | _, _, Step.root (RootStep.base x y) => p2_root_base x y
  | _, _, Step.root (RootStep.succ x y n) => p2_root_succ x y n
  | _, _, Step.s_arg h => by have := p2_step_decreases h; simp [p2]; omega
  | _, _, Step.g_left h => by have := p2_step_decreases h; simp [p2]; omega
  | _, _, Step.g_right h => by have := p2_step_decreases h; simp [p2]; omega
  | _, _, Step.f_arg1 h => by have := p2_step_decreases h; simp [p2]; omega
  | _, _, Step.f_arg2 h => by have := p2_step_decreases h; simp [p2]; nlinarith [this]
  | _, _, Step.f_arg3 h => by have := p2_step_decreases h; simp [p2]; nlinarith [this]

/-- Strong normalization of the Schema A TRS, witnessed by the non-collapsing
polynomial `p2`. -/
theorem wf_StepRev_p2 : WellFounded (fun a b => Step b a) := by
  have hsub : Subrelation (fun a b => Step b a) (InvImage (· < ·) p2) := by
    intro a b hab
    exact p2_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf p2 Nat.lt_wfRel.wf)

end KO7Benchmark.SchemaTests.NonCollapsingPoly
