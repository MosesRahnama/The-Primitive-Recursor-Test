/-
  The equality rules of the benchmark system, guarded.

  Relation: the eight root rules of `KO7Kernel.Step` on `Trace`, with the
    difference rule `eqW a b -> integrate (merge a b)` carrying the side
    condition `a ≠ b`.
  Closure: the root relation; the generic lemma covers any subrelation of the
    contextual closure.
  Property: responses objected that the two equality rules overlap, because
    the unguarded difference rule also applies when the two arguments agree,
    and that the guard needs decidable equality on terms. Both points resolve
    inside the system: equality on `Trace` is decidable, the guarded system
    has one applicable equality rule per term, and the guarded relation is a
    subrelation of the unguarded one, so it inherits strong normalization.
    Guarding removes the overlap and changes no termination verdict.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.PaperB.KO7DPSoundness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.GuardedEquality

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

/-! ## The overlap in the published rules -/

/-- On a term whose two arguments agree, both published equality rules apply,
    so the published system has two reducts there. -/
theorem equality_rules_overlap (a : Trace) :
    Step (eqW a a) void ∧ Step (eqW a a) (integrate (merge a a)) :=
  ⟨Step.R_eq_refl a, Step.R_eq_diff a a⟩

/-- Equality on terms is decidable, so the guard is computable. -/
instance : DecidableEq Trace := inferInstance

/-! ## The guarded root relation -/

/-- The published root rules with the difference rule guarded. -/
inductive StepGuarded : Trace → Trace → Prop
  | R_int_delta (t : Trace) : StepGuarded (integrate (delta t)) void
  | R_merge_void_left (t : Trace) : StepGuarded (merge void t) t
  | R_merge_void_right (t : Trace) : StepGuarded (merge t void) t
  | R_merge_cancel (t : Trace) : StepGuarded (merge t t) t
  | R_rec_zero (b s : Trace) : StepGuarded (recDelta b s void) b
  | R_rec_succ (b s n : Trace) :
      StepGuarded (recDelta b s (delta n)) (app s (recDelta b s n))
  | R_eq_refl (a : Trace) : StepGuarded (eqW a a) void
  | R_eq_diff (a b : Trace) : a ≠ b → StepGuarded (eqW a b) (integrate (merge a b))

/-- The guarded relation is a subrelation of the published one. -/
theorem stepGuarded_imp_step {t u : Trace} (h : StepGuarded t u) : Step t u :=
  match h with
  | .R_int_delta t => Step.R_int_delta t
  | .R_merge_void_left t => Step.R_merge_void_left t
  | .R_merge_void_right t => Step.R_merge_void_right t
  | .R_merge_cancel t => Step.R_merge_cancel t
  | .R_rec_zero b s => Step.R_rec_zero b s
  | .R_rec_succ b s n => Step.R_rec_succ b s n
  | .R_eq_refl a => Step.R_eq_refl a
  | .R_eq_diff a b _ => Step.R_eq_diff a b

/-- Exactly one equality rule applies to any term headed by `eqW`. -/
theorem equality_rules_exclusive (a b : Trace) :
    (a = b ∧ StepGuarded (eqW a b) void) ∨
    (a ≠ b ∧ StepGuarded (eqW a b) (integrate (merge a b))) := by
  by_cases h : a = b
  · subst h
    exact Or.inl ⟨rfl, StepGuarded.R_eq_refl a⟩
  · exact Or.inr ⟨h, StepGuarded.R_eq_diff a b h⟩

/-- On agreeing arguments the guarded system has one reduct. -/
theorem guard_removes_overlap (a : Trace) :
    ¬ StepGuarded (eqW a a) (integrate (merge a a)) := by
  intro h
  cases h with
  | R_eq_diff _ _ hne => exact hne rfl

/-! ## Termination is unchanged -/

/-- Any subrelation of the contextual closure inherits strong normalization
    from `KO7DPSoundness`. -/
theorem wf_of_subrelation_ctx {R : Trace → Trace → Prop}
    (h : ∀ {a b : Trace}, R a b → StepCtx a b) :
    WellFounded (fun a b : Trace => R b a) :=
  Subrelation.wf (fun {_ _} hr => h hr)
    KO7Benchmark.PaperB.KO7DPSoundness.wf_StepCtxRev_rule_derived

/-- The guarded system terminates. -/
theorem wf_StepGuardedRev : WellFounded (fun a b : Trace => StepGuarded b a) :=
  wf_of_subrelation_ctx (fun h => StepCtx.root (stepGuarded_imp_step h))

/-- Guarding changes no termination verdict: the published system and the
    guarded system are both strongly normalizing. -/
theorem guard_preserves_termination :
    WellFounded (fun a b : Trace => StepCtx b a) ∧
      WellFounded (fun a b : Trace => StepGuarded b a) :=
  ⟨KO7Benchmark.PaperB.KO7DPSoundness.wf_StepCtxRev_rule_derived, wf_StepGuardedRev⟩

end KO7Benchmark.ScoringAnchors.GuardedEquality
