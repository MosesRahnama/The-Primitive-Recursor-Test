/-
  The polynomial interpretation stated in the paper (ICLR Appendix C,
  Proposition 3).

  Relation: the two-rule schema of `SchemaKernel`.
  Closure: full contextual closure `Step`.
  Property: with [Z] = 0, [S](n) = n + 1, [G](y, v) = y + v + 1 and
    [F](x, y, n) = x + (n + 1)(y + 2), every valuation of the variables gives a
    strict decrease on both rules, the interpretation is strictly monotone in
    every argument, and the reverse step relation is well founded. The
    valuation is a parameter of every statement, so the decrease is checked for
    every natural-number valuation, as the paper says.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

set_option autoImplicit false

namespace KO7Benchmark.PaperB.PaperPolynomial

open KO7Benchmark.SchemaTests
open SKTerm

/-- The paper's interpretation under a valuation `σ` of the variables. -/
def evalP (σ : Nat → Nat) : SKTerm → Nat
  | var v => σ v
  | z => 0
  | s t => evalP σ t + 1
  | g a b => evalP σ a + evalP σ b + 1
  | f x y n => evalP σ x + (evalP σ n + 1) * (evalP σ y + 2)

@[simp] theorem evalP_var (σ : Nat → Nat) (v : Nat) : evalP σ (var v) = σ v := rfl
@[simp] theorem evalP_z (σ : Nat → Nat) : evalP σ z = 0 := rfl
@[simp] theorem evalP_s (σ : Nat → Nat) (t : SKTerm) : evalP σ (s t) = evalP σ t + 1 := rfl
@[simp] theorem evalP_g (σ : Nat → Nat) (a b : SKTerm) :
    evalP σ (g a b) = evalP σ a + evalP σ b + 1 := rfl
@[simp] theorem evalP_f (σ : Nat → Nat) (x y n : SKTerm) :
    evalP σ (f x y n) = evalP σ x + (evalP σ n + 1) * (evalP σ y + 2) := rfl

/-! ## Monotonicity in every argument -/

/-- `S` is monotone in its argument. -/
theorem mono_s (σ : Nat → Nat) {t u : SKTerm} (h : evalP σ u < evalP σ t) :
    evalP σ (s u) < evalP σ (s t) := by
  simp only [evalP_s]; omega

/-- `G` is monotone in both arguments. -/
theorem mono_g_left (σ : Nat → Nat) {a a' b : SKTerm} (h : evalP σ a' < evalP σ a) :
    evalP σ (g a' b) < evalP σ (g a b) := by
  simp only [evalP_g]; omega

theorem mono_g_right (σ : Nat → Nat) {a b b' : SKTerm} (h : evalP σ b' < evalP σ b) :
    evalP σ (g a b') < evalP σ (g a b) := by
  simp only [evalP_g]; omega

/-- `F` is monotone in all three arguments. The coefficients are `1` on the
    first, `n + 1` on the second, and `y + 2` on the third, matching the
    proposition's proof. -/
theorem mono_f_arg1 (σ : Nat → Nat) {x x' y n : SKTerm} (h : evalP σ x' < evalP σ x) :
    evalP σ (f x' y n) < evalP σ (f x y n) := by
  simp only [evalP_f]; omega

theorem mono_f_arg2 (σ : Nat → Nat) {x y y' n : SKTerm} (h : evalP σ y' < evalP σ y) :
    evalP σ (f x y' n) < evalP σ (f x y n) := by
  simp only [evalP_f]
  have hm : (evalP σ n + 1) * (evalP σ y' + 2) < (evalP σ n + 1) * (evalP σ y + 2) :=
    Nat.mul_lt_mul_of_pos_left (by omega) (Nat.succ_pos _)
  omega

theorem mono_f_arg3 (σ : Nat → Nat) {x y n n' : SKTerm} (h : evalP σ n' < evalP σ n) :
    evalP σ (f x y n') < evalP σ (f x y n) := by
  simp only [evalP_f]
  have hm : (evalP σ n' + 1) * (evalP σ y + 2) < (evalP σ n + 1) * (evalP σ y + 2) :=
    Nat.mul_lt_mul_of_pos_right (by omega) (Nat.succ_pos _)
  omega

/-- Both root rules decrease under every valuation. The recursive rule
    decreases by one. -/
theorem root_decreases (σ : Nat → Nat) {t u : SKTerm} (h : RootStep t u) :
    evalP σ u < evalP σ t := by
  cases h with
  | base x y =>
      simp only [evalP_f, evalP_z, Nat.zero_add, Nat.one_mul]
      omega
  | succ x y n =>
      simp only [evalP_f, evalP_g, evalP_s]
      have hexp : (evalP σ n + 1 + 1) * (evalP σ y + 2)
          = (evalP σ n + 1) * (evalP σ y + 2) + (evalP σ y + 2) := by ring
      omega

/-- The recursive rule decreases by exactly one unit. -/
theorem succ_rule_drop_one (σ : Nat → Nat) (x y n : SKTerm) :
    evalP σ (g y (f x y n)) + 1 = evalP σ (f x y (s n)) := by
  simp only [evalP_f, evalP_g, evalP_s]
  have hexp : (evalP σ n + 1 + 1) * (evalP σ y + 2)
      = (evalP σ n + 1) * (evalP σ y + 2) + (evalP σ y + 2) := by ring
  omega

/-- Strict monotonicity in every argument position, hence decrease under
    every context. -/
theorem step_decreases (σ : Nat → Nat) {t u : SKTerm} (h : Step t u) :
    evalP σ u < evalP σ t := by
  induction h with
  | root hr => exact root_decreases σ hr
  | s_arg _ ih => simp only [evalP_s]; omega
  | g_left _ ih => simp only [evalP_g]; omega
  | g_right _ ih => simp only [evalP_g]; omega
  | f_arg1 _ ih => simp only [evalP_f]; omega
  | @f_arg2 a t u c _ ih =>
      simp only [evalP_f]
      have hm : (evalP σ c + 1) * (evalP σ u + 2) < (evalP σ c + 1) * (evalP σ t + 2) :=
        Nat.mul_lt_mul_of_pos_left (by omega) (Nat.succ_pos _)
      omega
  | @f_arg3 a b t u _ ih =>
      simp only [evalP_f]
      have hm : (evalP σ u + 1) * (evalP σ b + 2) < (evalP σ t + 1) * (evalP σ b + 2) :=
        Nat.mul_lt_mul_of_pos_right (by omega) (Nat.succ_pos _)
      omega

/-- Reverse step relation on the schema. -/
def StepRev : SKTerm → SKTerm → Prop := fun a b => Step b a

/-- Proposition 3: the schema terminates under the paper's interpretation,
    for every valuation. -/
theorem wf_StepRev (σ : Nat → Nat) : WellFounded StepRev :=
  Subrelation.wf (fun {_ _} h => step_decreases σ h)
    (InvImage.wf (evalP σ) Nat.lt_wfRel.wf)

/-- The interpretation of `F` has degree two: the coefficient of `y` is
    `n + 1`, which the counter controls. This is the coupling that no additive
    measure has. -/
theorem coefficient_of_payload (σ : Nat → Nat) (x y n : SKTerm) :
    evalP σ (f x y n) = evalP σ x + (evalP σ n + 1) * evalP σ y + 2 * (evalP σ n + 1) := by
  simp only [evalP_f]
  ring

end KO7Benchmark.PaperB.PaperPolynomial
