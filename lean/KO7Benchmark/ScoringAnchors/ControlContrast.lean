/-
  The copy-removal control, as a two-sided statement.

  Relation: the two-rule schema of `SchemaKernel` against the copy-removed
    variant of `SANSKernel`, whose step rule is `F(x, y, S(n)) -> G(F(x, y, n))`
    with a unary `G`.
  Closure: full contextual closure on both systems.
  Property: one and the same family of additive constructor-weight measures is
    empty on the schema and inhabited on the control. The weights
    `(var 0, Z 0, S 1, G 0, F 1)` orient every step of the control; no weights
    at all orient the schema. The structural difference is the occurrence count
    of the second argument on the right side of the step rule: two on the
    schema, one on the control.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.SANSTests.LinearWitness
import KO7Benchmark.ScoringAnchors.MeasureFailures

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.ControlContrast

open KO7Benchmark.SANSTests
open KO7Benchmark.ScoringAnchors.MeasureFailures

/-! ## The additive family on the control system -/

/-- Constructor weights on the control signature; `G` is unary there. -/
structure SANSAdditive where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace SANSAdditive

def eval (M : SANSAdditive) : SANSTerm → Nat
  | .var _ => M.wVar
  | .z => M.wZ
  | .s t => M.wS + M.eval t
  | .g t => M.wG + M.eval t
  | .f x y n => M.wF + M.eval x + M.eval y + M.eval n

/-- The weights that realise the control measure `LinearWitness.mu`. -/
def control : SANSAdditive := ⟨0, 0, 1, 0, 1⟩

@[simp] theorem control_wS : control.wS = 1 := rfl
@[simp] theorem control_wG : control.wG = 0 := rfl
@[simp] theorem control_wF : control.wF = 1 := rfl

theorem eval_control (t : SANSTerm) : control.eval t = LinearWitness.mu t := by
  induction t with
  | var v => rfl
  | z => rfl
  | s t ih =>
      show control.wS + control.eval t = LinearWitness.mu t + 1
      rw [ih, control_wS]
      omega
  | g t ih =>
      show control.wG + control.eval t = LinearWitness.mu t
      rw [ih, control_wG]
      omega
  | f x y n ihx ihy ihn =>
      show control.wF + control.eval x + control.eval y + control.eval n
        = LinearWitness.mu x + LinearWitness.mu y + LinearWitness.mu n + 1
      rw [ihx, ihy, ihn, control_wF]
      omega

/-- The additive family is inhabited on the control system. -/
theorem control_orients_step :
    ∀ {a b : SANSTerm}, Step a b → control.eval b < control.eval a := by
  intro a b h
  rw [eval_control, eval_control]
  exact LinearWitness.mu_step_decreases h

theorem additive_family_inhabited_on_control :
    ∃ M : SANSAdditive, ∀ {a b : SANSTerm}, Step a b → M.eval b < M.eval a :=
  ⟨control, control_orients_step⟩

end SANSAdditive

/-! ## The same family on the schema -/

/-- The additive family is empty on the schema. -/
theorem additive_family_empty_on_schema :
    ¬ ∃ M : GenAdditive,
        ∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
          KO7Benchmark.SchemaTests.Step a b → M.eval b < M.eval a := by
  rintro ⟨M, h⟩
  exact GenAdditive.no_gen_additive_orients_step M h

/-- The control weights read on the schema signature. -/
def controlOnSchema : GenAdditive := ⟨0, 0, 1, 0, 1⟩

/-- Transporting the control measure to the schema fails, on the ground
    instance in which the copied argument carries two `S` symbols. -/
theorem controlOnSchema_fails :
    ¬ (∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
        KO7Benchmark.SchemaTests.Step a b →
          controlOnSchema.eval b < controlOnSchema.eval a) :=
  GenAdditive.no_gen_additive_orients_step controlOnSchema

/-- The two-sided contrast in one statement: inhabited on the control, empty
    on the schema. -/
theorem control_contrast :
    (∃ M : SANSAdditive, ∀ {a b : SANSTerm}, Step a b → M.eval b < M.eval a) ∧
    ¬ (∃ M : GenAdditive,
        ∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
          KO7Benchmark.SchemaTests.Step a b → M.eval b < M.eval a) :=
  ⟨SANSAdditive.additive_family_inhabited_on_control, additive_family_empty_on_schema⟩

/-! ## The structural difference -/

/-- Occurrences of one variable in a control term. -/
def occS (v : Nat) : SANSTerm → Nat
  | .var w => if v = w then 1 else 0
  | .z => 0
  | .s t => occS v t
  | .g t => occS v t
  | .f x y n => occS v x + occS v y + occS v n

/-- The second argument occurs twice on the right side of the schema step rule
    and once on the right side of the control step rule. Every other symbol
    count agrees. -/
theorem copy_count_difference :
    occS 1 (.g (.f (.var 0) (.var 1) (.var 2))) = 1 ∧
      MeasureFailures.occ 1
        (.g (.var 1) (.f (.var 0) (.var 1) (.var 2))) = 2 := by
  constructor <;> rfl

end KO7Benchmark.ScoringAnchors.ControlContrast
