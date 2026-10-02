/-
  Self-contained benchmarked primitive-recursion family classification.

  This module formalizes the family-relative global theorem that anchors
  Paper B's "Schema A New System is the negative control" claim: among
  the structurally complete primitive-recursion configurations, the
  duplicating member is the unique blocked one for direct whole-term
  witnesses, while the linear member admits a simple direct witness.

  Family scope:

  ```
                base   step
                ----   ----
   absent       any    any   ->  not structurally complete
   present      absent any   ->  not structurally complete
   present      linear       ->  full linear      (direct witness exists)
   present      duplicating  ->  full duplicating (direct witness blocked)
  ```

  This is a benchmark-local family theorem, not a claim about all term
  rewriting. The full twelve-class direct-measure barrier theorem in
  the companion theorem stack is strictly stronger; here we mechanize
  the additive case so the cross-task negative-control story closes
  inside the benchmark Lean.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.BenchmarkedPRCFamily

open KO7Benchmark.SchemaTests
open SKTerm

/-! ## Family configuration -/

inductive BaseRuleFlag
  | absent
  | present
  deriving DecidableEq, Repr

inductive StepRuleFlag
  | absent
  | linear
  | duplicating
  deriving DecidableEq, Repr

structure PRCConfig where
  baseRule : BaseRuleFlag
  stepRule : StepRuleFlag
  deriving DecidableEq, Repr

def fullLinear : PRCConfig :=
  ⟨BaseRuleFlag.present, StepRuleFlag.linear⟩

def fullDuplicating : PRCConfig :=
  ⟨BaseRuleFlag.present, StepRuleFlag.duplicating⟩

def StructurallyComplete (cfg : PRCConfig) : Prop :=
  cfg.baseRule = BaseRuleFlag.present ∧ cfg.stepRule ≠ StepRuleFlag.absent

/-! ## Family root-step relation on `SKTerm` -/

/-- Root-step relation parameterized by a configuration. The `linear`
    constructor has no wrapper; the `dup` constructor wraps the recursive
    call under `g y (·)`. -/
inductive FamilyStep : PRCConfig → SKTerm → SKTerm → Prop
  | base {cfg : PRCConfig} (h : cfg.baseRule = BaseRuleFlag.present)
      (x y : SKTerm) : FamilyStep cfg (f x y z) x
  | linear {cfg : PRCConfig} (h : cfg.stepRule = StepRuleFlag.linear)
      (x y n : SKTerm) : FamilyStep cfg (f x y (s n)) (f x y n)
  | dup {cfg : PRCConfig} (h : cfg.stepRule = StepRuleFlag.duplicating)
      (x y n : SKTerm) : FamilyStep cfg (f x y (s n)) (g y (f x y n))

/-- Recursive-call relation extracted from the step rule. -/
inductive FamilyCallStep : PRCConfig → SKTerm → SKTerm → Prop
  | linear {cfg : PRCConfig} (h : cfg.stepRule = StepRuleFlag.linear)
      (x y n : SKTerm) : FamilyCallStep cfg (f x y (s n)) (f x y n)
  | dup {cfg : PRCConfig} (h : cfg.stepRule = StepRuleFlag.duplicating)
      (x y n : SKTerm) : FamilyCallStep cfg (f x y (s n)) (f x y n)

/-! ## Witness predicates -/

/-- Constructor-weight assignments for the schema-kernel constructors,
    parameterizing additive direct witnesses. The `g`-weight must be
    positive so that wrapper structure cannot be discarded; the `s`-weight
    must be positive so that the counter is reflected in the measure. -/
structure AdditiveSchemaMeasure where
  wVar  : Nat
  wZ    : Nat
  wS    : Nat
  wG    : Nat
  wF    : Nat
  wG_pos : 0 < wG
  wS_pos : 0 < wS

namespace AdditiveSchemaMeasure

def eval (M : AdditiveSchemaMeasure) : SKTerm → Nat
  | var _ => M.wVar
  | z => M.wZ
  | s t => M.wS + M.eval t
  | g a b => M.wG + M.eval a + M.eval b
  | f x y n => M.wF + M.eval x + M.eval y + M.eval n

@[simp] theorem eval_var (M : AdditiveSchemaMeasure) (n : Nat) :
    M.eval (var n) = M.wVar := rfl
@[simp] theorem eval_z (M : AdditiveSchemaMeasure) :
    M.eval z = M.wZ := rfl
@[simp] theorem eval_s (M : AdditiveSchemaMeasure) (t : SKTerm) :
    M.eval (s t) = M.wS + M.eval t := rfl
@[simp] theorem eval_g (M : AdditiveSchemaMeasure) (a b : SKTerm) :
    M.eval (g a b) = M.wG + M.eval a + M.eval b := rfl
@[simp] theorem eval_f (M : AdditiveSchemaMeasure) (x y n : SKTerm) :
    M.eval (f x y n) = M.wF + M.eval x + M.eval y + M.eval n := rfl

end AdditiveSchemaMeasure

/-- An additive direct whole-term witness for `cfg`. -/
def HasDirectWitness (cfg : PRCConfig) : Prop :=
  ∃ M : AdditiveSchemaMeasure,
    ∀ {a b : SKTerm}, FamilyStep cfg a b → M.eval b < M.eval a

/-- A possibly-nonadditive imported-whole witness for `cfg`. -/
def HasImportedWholeWitness (cfg : PRCConfig) : Prop :=
  ∃ μ : SKTerm → Nat,
    ∀ {a b : SKTerm}, FamilyStep cfg a b → μ b < μ a

/-- A transformed-call witness on the recursive-call relation. -/
def HasTransformedCallWitness (cfg : PRCConfig) : Prop :=
  ∃ ρ : SKTerm → Nat,
    ∀ {a b : SKTerm}, FamilyCallStep cfg a b → ρ b < ρ a

/-! ## Direct witness for `fullLinear` -/

/-- Simple constructor-additive measure used as the direct witness on the
    linear member. -/
def linearMeasure : AdditiveSchemaMeasure where
  wVar := 0
  wZ := 0
  wS := 1
  wG := 1
  wF := 1
  wG_pos := by decide
  wS_pos := by decide

theorem fullLinear_has_direct_witness :
    HasDirectWitness fullLinear := by
  refine ⟨linearMeasure, ?_⟩
  intro a b h
  cases h with
  | base _ x y =>
      simp [linearMeasure, AdditiveSchemaMeasure.eval]
      omega
  | linear _ x y n =>
      simp [linearMeasure, AdditiveSchemaMeasure.eval]
  | dup hstep _ _ _ =>
      cases hstep

/-! ## Refutation for `fullDuplicating` -/

/-- The additive direct-witness no-go for the duplicating member. The
    witness substitution is `x = z`, `y = s z`, `n = z` and uses the
    fact that the right-hand side accumulates `2 * eval s` while the
    left-hand side has only one occurrence of `eval (s z)`. -/
theorem fullDuplicating_has_no_direct_witness :
    ¬ HasDirectWitness fullDuplicating := by
  rintro ⟨M, h⟩
  -- Apply the duplicating rule with `x = z`, `y = s z`, `n = z`.
  have hstep :
      FamilyStep fullDuplicating
        (f z (s z) (s z))
        (g (s z) (f z (s z) z)) :=
    FamilyStep.dup (cfg := fullDuplicating) rfl z (s z) z
  have hlt := h hstep
  simp only [AdditiveSchemaMeasure.eval] at hlt
  have hG := M.wG_pos
  have hS := M.wS_pos
  omega

/-- The duplicating member still admits a transformed-call witness via
    third-argument counter-depth descent, irrespective of the wrapper. -/
def callDepth : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => callDepth t + 1
  | g _ _ => 0
  | f _ _ n => callDepth n

theorem fullDuplicating_has_transformed_call_witness :
    HasTransformedCallWitness fullDuplicating := by
  refine ⟨callDepth, ?_⟩
  intro a b h
  cases h with
  | linear hstep _ _ _ => cases hstep
  | dup _ x y n =>
      simp [callDepth]

/-- Schema-A imported-whole witness on the duplicating member. The bridge
    measure `μ_imp` mirrors the nonlinear polynomial used in
    `SchemaTests.NonlinearWitness` for `Step`; here we transport that idea
    to the family-step relation. -/
def importedWholeMeasure : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => importedWholeMeasure t + 1
  | g a b => importedWholeMeasure a + importedWholeMeasure b
  | f x y n =>
      (importedWholeMeasure y + 1) * (importedWholeMeasure n + 1)
        + importedWholeMeasure x + 1

theorem fullDuplicating_has_imported_whole_witness :
    HasImportedWholeWitness fullDuplicating := by
  refine ⟨importedWholeMeasure, ?_⟩
  intro a b h
  cases h with
  | base _ x y =>
      simp [importedWholeMeasure]
      omega
  | linear hstep _ _ _ => cases hstep
  | dup _ x y n =>
      have hEq :
          importedWholeMeasure (f x y (s n)) =
            importedWholeMeasure (g y (f x y n)) + 1 := by
        simp [importedWholeMeasure]; ring
      rw [hEq]; omega

/-! ## Family classification theorem -/

/-- Family classification: every configuration falls into exactly one of
    three buckets. The duplicating complete member fails direct witnesses
    but admits both imported-whole and transformed-call routes; the linear
    complete member admits a direct witness; structurally-incomplete
    members carry no positive obligation. -/
theorem global_family_classification (cfg : PRCConfig) :
    (cfg = fullDuplicating ∧ StructurallyComplete cfg
      ∧ ¬ HasDirectWitness cfg
      ∧ HasImportedWholeWitness cfg
      ∧ HasTransformedCallWitness cfg)
    ∨ (cfg = fullLinear ∧ StructurallyComplete cfg ∧ HasDirectWitness cfg)
    ∨ (¬ StructurallyComplete cfg) := by
  -- Six-config case split, fully resolved.
  rcases cfg with ⟨b, st⟩
  cases b with
  | absent =>
      cases st with
      | absent =>
          right; right
          intro h
          exact BaseRuleFlag.noConfusion h.1
      | linear =>
          right; right
          intro h
          exact BaseRuleFlag.noConfusion h.1
      | duplicating =>
          right; right
          intro h
          exact BaseRuleFlag.noConfusion h.1
  | present =>
      cases st with
      | absent =>
          right; right
          intro h
          exact h.2 rfl
      | linear =>
          right; left
          refine ⟨rfl, ⟨rfl, by decide⟩, ?_⟩
          exact fullLinear_has_direct_witness
      | duplicating =>
          left
          refine ⟨rfl, ⟨rfl, by decide⟩, ?_, ?_, ?_⟩
          · exact fullDuplicating_has_no_direct_witness
          · exact fullDuplicating_has_imported_whole_witness
          · exact fullDuplicating_has_transformed_call_witness

/-- Among structurally complete family members, the duplicating member is
    the unique one without a direct witness. -/
theorem fullDuplicating_unique_blocked_complete_member (cfg : PRCConfig)
    (hcomplete : StructurallyComplete cfg) :
    (¬ HasDirectWitness cfg) ↔ cfg = fullDuplicating := by
  constructor
  · intro hno
    rcases global_family_classification cfg with
      ⟨heq, _⟩ | ⟨_, _, hdir⟩ | hnc
    · exact heq
    · exact absurd hdir hno
    · exact absurd hcomplete hnc
  · intro heq
    rw [heq]
    exact fullDuplicating_has_no_direct_witness

theorem every_other_complete_member_has_direct_witness (cfg : PRCConfig)
    (hcomplete : StructurallyComplete cfg) (hneq : cfg ≠ fullDuplicating) :
    HasDirectWitness cfg := by
  rcases global_family_classification cfg with
    ⟨heq, _⟩ | ⟨_, _, hdir⟩ | hnc
  · exact absurd heq hneq
  · exact hdir
  · exact absurd hcomplete hnc

theorem fullDuplicating_is_global_minimum_in_bench_family :
    StructurallyComplete fullDuplicating
      ∧ ¬ HasDirectWitness fullDuplicating
      ∧ HasImportedWholeWitness fullDuplicating
      ∧ HasTransformedCallWitness fullDuplicating
      ∧ (∀ cfg : PRCConfig,
          StructurallyComplete cfg → cfg ≠ fullDuplicating → HasDirectWitness cfg) :=
  ⟨⟨rfl, by decide⟩,
   fullDuplicating_has_no_direct_witness,
   fullDuplicating_has_imported_whole_witness,
   fullDuplicating_has_transformed_call_witness,
   every_other_complete_member_has_direct_witness⟩

theorem fullDuplicating_is_unique_blocked_complete_family_member :
    StructurallyComplete fullDuplicating
      ∧ ¬ HasDirectWitness fullDuplicating
      ∧ (∀ cfg : PRCConfig,
          StructurallyComplete cfg → cfg ≠ fullDuplicating → HasDirectWitness cfg) := by
  rcases fullDuplicating_is_global_minimum_in_bench_family with ⟨h1, h2, _, _, h5⟩
  exact ⟨h1, h2, h5⟩

end KO7Benchmark.BenchmarkedPRCFamily
