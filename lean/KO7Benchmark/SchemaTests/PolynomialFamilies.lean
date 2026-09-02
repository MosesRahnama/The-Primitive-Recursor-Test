/-
  Parametric non-collapsing polynomial families for Schema A.

  These families cover the common successful agent shapes. They are not merely
  root-rule checks: each theorem proves strict decrease for every context-closed
  `Step`, hence well-foundedness of the reverse step relation.

  Family P1:
    [G a b]   = [a] + [b]
    [F x y n] = k * ([x] + [y] + 1) * ([n] + 1), with k > 0

  Family P2:
    [G a b]   = [a] + [b]
    [F x y n] = [x] + k * ([y] + 1) * ([n] + 1), with k > 0
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.PolynomialFamilies

open KO7Benchmark.SchemaTests
open SKTerm

/-! ### Product family P1 -/

def pProd (k : Nat) : SKTerm -> Nat
  | var _ => 0
  | z => 0
  | s t => pProd k t + 1
  | g a b => pProd k a + pProd k b
  | f x y n => k * (pProd k x + pProd k y + 1) * (pProd k n + 1)

@[simp] theorem pProd_var (k n : Nat) : pProd k (var n) = 0 := rfl
@[simp] theorem pProd_z (k : Nat) : pProd k z = 0 := rfl
@[simp] theorem pProd_s (k : Nat) (t : SKTerm) : pProd k (s t) = pProd k t + 1 := rfl
@[simp] theorem pProd_g (k : Nat) (a b : SKTerm) :
    pProd k (g a b) = pProd k a + pProd k b := rfl
@[simp] theorem pProd_f (k : Nat) (x y n : SKTerm) :
    pProd k (f x y n) = k * (pProd k x + pProd k y + 1) * (pProd k n + 1) := rfl

theorem pProd_root_base (k : Nat) (hk : 0 < k) (x y : SKTerm) :
    pProd k x < pProd k (f x y z) := by
  simp [pProd]
  nlinarith [hk, Nat.zero_le (pProd k x), Nat.zero_le (pProd k y)]

theorem pProd_root_succ (k : Nat) (hk : 0 < k) (x y n : SKTerm) :
    pProd k (g y (f x y n)) < pProd k (f x y (s n)) := by
  simp [pProd]
  nlinarith [hk, Nat.zero_le (pProd k x), Nat.zero_le (pProd k y),
    Nat.zero_le (pProd k n)]

theorem pProd_step_decreases (k : Nat) (hk : 0 < k) :
    ∀ {t u : SKTerm}, Step t u -> pProd k u < pProd k t
  | _, _, Step.root (RootStep.base x y) => pProd_root_base k hk x y
  | _, _, Step.root (RootStep.succ x y n) => pProd_root_succ k hk x y n
  | _, _, Step.s_arg h => by
      have ih := pProd_step_decreases k hk h
      simp [pProd]
      omega
  | _, _, Step.g_left h => by
      have ih := pProd_step_decreases k hk h
      simp [pProd]
      omega
  | _, _, Step.g_right h => by
      have ih := pProd_step_decreases k hk h
      simp [pProd]
      omega
  | _, _, @Step.f_arg1 t u b c h => by
      have ih := pProd_step_decreases k hk h
      have hcoeff : 0 < pProd k c + 1 := by omega
      simp [pProd]
      nlinarith [ih, hk, hcoeff]
  | _, _, @Step.f_arg2 a t u c h => by
      have ih := pProd_step_decreases k hk h
      have hcoeff : 0 < pProd k c + 1 := by omega
      simp [pProd]
      nlinarith [ih, hk, hcoeff]
  | _, _, @Step.f_arg3 a b t u h => by
      have ih := pProd_step_decreases k hk h
      have hcoeff : 0 < pProd k a + pProd k b + 1 := by omega
      have hcoef : 0 < k * (pProd k a + pProd k b + 1) := Nat.mul_pos hk hcoeff
      have hsucc : pProd k u + 1 < pProd k t + 1 := Nat.succ_lt_succ ih
      simpa [pProd, Nat.mul_assoc] using Nat.mul_lt_mul_of_pos_left hsucc hcoef

theorem wf_StepRev_pProd (k : Nat) (hk : 0 < k) :
    WellFounded (fun a b => Step b a) := by
  have hsub : Subrelation (fun a b => Step b a) (InvImage (· < ·) (pProd k)) := by
    intro a b hab
    exact pProd_step_decreases k hk hab
  exact Subrelation.wf hsub (InvImage.wf (pProd k) Nat.lt_wfRel.wf)

/-! ### Affine payload-clock family P2 -/

def pPayloadClock (k : Nat) : SKTerm -> Nat
  | var _ => 0
  | z => 0
  | s t => pPayloadClock k t + 1
  | g a b => pPayloadClock k a + pPayloadClock k b
  | f x y n => pPayloadClock k x + k * (pPayloadClock k y + 1) * (pPayloadClock k n + 1)

@[simp] theorem pPayloadClock_var (k n : Nat) : pPayloadClock k (var n) = 0 := rfl
@[simp] theorem pPayloadClock_z (k : Nat) : pPayloadClock k z = 0 := rfl
@[simp] theorem pPayloadClock_s (k : Nat) (t : SKTerm) :
    pPayloadClock k (s t) = pPayloadClock k t + 1 := rfl
@[simp] theorem pPayloadClock_g (k : Nat) (a b : SKTerm) :
    pPayloadClock k (g a b) = pPayloadClock k a + pPayloadClock k b := rfl
@[simp] theorem pPayloadClock_f (k : Nat) (x y n : SKTerm) :
    pPayloadClock k (f x y n) =
      pPayloadClock k x + k * (pPayloadClock k y + 1) * (pPayloadClock k n + 1) := rfl

theorem pPayloadClock_root_base (k : Nat) (hk : 0 < k) (x y : SKTerm) :
    pPayloadClock k x < pPayloadClock k (f x y z) := by
  simp [pPayloadClock]
  nlinarith [hk, Nat.zero_le (pPayloadClock k y)]

theorem pPayloadClock_root_succ (k : Nat) (hk : 0 < k) (x y n : SKTerm) :
    pPayloadClock k (g y (f x y n)) < pPayloadClock k (f x y (s n)) := by
  simp [pPayloadClock]
  nlinarith [hk, Nat.zero_le (pPayloadClock k y), Nat.zero_le (pPayloadClock k n)]

theorem pPayloadClock_step_decreases (k : Nat) (hk : 0 < k) :
    ∀ {t u : SKTerm}, Step t u -> pPayloadClock k u < pPayloadClock k t
  | _, _, Step.root (RootStep.base x y) => pPayloadClock_root_base k hk x y
  | _, _, Step.root (RootStep.succ x y n) => pPayloadClock_root_succ k hk x y n
  | _, _, Step.s_arg h => by
      have ih := pPayloadClock_step_decreases k hk h
      simp [pPayloadClock]
      omega
  | _, _, Step.g_left h => by
      have ih := pPayloadClock_step_decreases k hk h
      simp [pPayloadClock]
      omega
  | _, _, Step.g_right h => by
      have ih := pPayloadClock_step_decreases k hk h
      simp [pPayloadClock]
      omega
  | _, _, @Step.f_arg1 t u b c h => by
      have ih := pPayloadClock_step_decreases k hk h
      simp [pPayloadClock]
      omega
  | _, _, @Step.f_arg2 a t u c h => by
      have ih := pPayloadClock_step_decreases k hk h
      have hcoeff : 0 < pPayloadClock k c + 1 := by omega
      simp [pPayloadClock]
      nlinarith [ih, hk, hcoeff]
  | _, _, @Step.f_arg3 a b t u h => by
      have ih := pPayloadClock_step_decreases k hk h
      have hcoeff : 0 < pPayloadClock k b + 1 := by omega
      have hcoef : 0 < k * (pPayloadClock k b + 1) := Nat.mul_pos hk hcoeff
      have hsucc : pPayloadClock k u + 1 < pPayloadClock k t + 1 := Nat.succ_lt_succ ih
      simpa [pPayloadClock, Nat.mul_assoc] using Nat.mul_lt_mul_of_pos_left hsucc hcoef

theorem wf_StepRev_pPayloadClock (k : Nat) (hk : 0 < k) :
    WellFounded (fun a b => Step b a) := by
  have hsub : Subrelation (fun a b => Step b a) (InvImage (· < ·) (pPayloadClock k)) := by
    intro a b hab
    exact pPayloadClock_step_decreases k hk hab
  exact Subrelation.wf hsub (InvImage.wf (pPayloadClock k) Nat.lt_wfRel.wf)

end KO7Benchmark.SchemaTests.PolynomialFamilies
