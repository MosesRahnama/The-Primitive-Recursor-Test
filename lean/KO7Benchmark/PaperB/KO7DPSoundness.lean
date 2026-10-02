/-
  Rule-derived strong normalization of the full KO7 contextual system
  (upgrades U1 and U4 of the 2026-09-17 Lean audit, KO7 side).

  Relation: the eight root rules of `KO7Kernel.Step` on `Trace`.
  Closure: full one-hole context closure `KO7ContextClosure.StepCtx`.
  Property: `StepCtx` is strongly normalizing, proved without any
    interpretation, weight, or ordering parameter, by the subterm-criterion
    argument: strong normalization is closed under every constructor, the
    relation "reduct or immediate subterm" is well founded below every
    strongly normalizing term, and `recDelta b s n` is strongly normalizing
    by induction along that relation on the counter `n`. At `R_rec_succ` the
    only comparison used is the dependency-pair comparison `n` against
    `delta n`. The rules `R_eq_diff` and `R_merge_*` are handled by the
    closure lemmas for `integrate` and `merge`.
    The earlier contextual certificate `wf_StepCtxRev_expInterp` used an
    exponential interpretation; this module gives the same conclusion on the
    rule-derived route, so the KO7 tower at the contextual relation carries a
    transformed-call certificate for the full system.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.KO7DependencyPairs

set_option autoImplicit false

namespace KO7Benchmark.PaperB.KO7DPSoundness

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

/-- Strong normalization for the contextual relation. -/
def SN (t : Trace) : Prop := Acc StepCtxRev t

/-- Immediate subterm relation on `Trace`. -/
inductive ImmSub : Trace → Trace → Prop
  | delta (t : Trace) : ImmSub t (delta t)
  | integrate (t : Trace) : ImmSub t (integrate t)
  | mergeLeft (a b : Trace) : ImmSub a (merge a b)
  | mergeRight (a b : Trace) : ImmSub b (merge a b)
  | appLeft (a b : Trace) : ImmSub a (app a b)
  | appRight (a b : Trace) : ImmSub b (app a b)
  | recBase (b s n : Trace) : ImmSub b (recDelta b s n)
  | recStep (b s n : Trace) : ImmSub s (recDelta b s n)
  | recCounter (b s n : Trace) : ImmSub n (recDelta b s n)
  | eqLeft (a b : Trace) : ImmSub a (eqW a b)
  | eqRight (a b : Trace) : ImmSub b (eqW a b)

/-- Descent: reduct or immediate subterm. -/
def Descent : Trace → Trace → Prop := fun a t => StepCtx t a ∨ ImmSub a t

/-! ## Strong normalization passes down through contexts -/

theorem sn_of_congr (C : Trace → Trace)
    (hC : ∀ {u u' : Trace}, StepCtx u u' → StepCtx (C u) (C u')) :
    ∀ {w : Trace}, SN w → ∀ u, w = C u → SN u := by
  intro w hw
  induction hw with
  | intro w _ ih =>
      intro u hu
      subst hu
      constructor
      intro u' hu'
      exact ih (C u') (hC hu') u' rfl

theorem sn_imm_sub {t a : Trace} (ht : SN t) (h : ImmSub a t) : SN a :=
  match h with
  | .delta t' => sn_of_congr (fun w => delta w) (fun hs => StepCtx.delta hs) ht t' rfl
  | .integrate t' =>
      sn_of_congr (fun w => integrate w) (fun hs => StepCtx.integrate hs) ht t' rfl
  | .mergeLeft a' b' =>
      sn_of_congr (fun w => merge w b') (fun hs => StepCtx.mergeLeft hs) ht a' rfl
  | .mergeRight a' b' =>
      sn_of_congr (fun w => merge a' w) (fun hs => StepCtx.mergeRight hs) ht b' rfl
  | .appLeft a' b' =>
      sn_of_congr (fun w => app w b') (fun hs => StepCtx.appLeft hs) ht a' rfl
  | .appRight a' b' =>
      sn_of_congr (fun w => app a' w) (fun hs => StepCtx.appRight hs) ht b' rfl
  | .recBase b' s' n' =>
      sn_of_congr (fun w => recDelta w s' n') (fun hs => StepCtx.recBase hs) ht b' rfl
  | .recStep b' s' n' =>
      sn_of_congr (fun w => recDelta b' w n') (fun hs => StepCtx.recStep hs) ht s' rfl
  | .recCounter b' s' n' =>
      sn_of_congr (fun w => recDelta b' s' w) (fun hs => StepCtx.recCounter hs) ht n' rfl
  | .eqLeft a' b' =>
      sn_of_congr (fun w => eqW w b') (fun hs => StepCtx.eqLeft hs) ht a' rfl
  | .eqRight a' b' =>
      sn_of_congr (fun w => eqW a' w) (fun hs => StepCtx.eqRight hs) ht b' rfl

/-! ## Strong normalization builds up through the constructors -/

theorem sn_void : SN void := by
  constructor
  intro u hu
  change StepCtx void u at hu
  cases hu with
  | root hr => cases hr

theorem sn_delta {t : Trace} (ht : SN t) : SN (delta t) := by
  induction ht with
  | intro t _ ih =>
      constructor
      intro u hu
      change StepCtx (delta t) u at hu
      cases hu with
      | root hr => cases hr
      | delta hs => exact ih _ hs

/-- Root reducts of `integrate t`: only `R_int_delta`, to `void`. -/
theorem sn_of_root_integrate {t u : Trace} (h : Step (integrate t) u) : SN u := by
  cases h with
  | R_int_delta => exact sn_void

theorem sn_integrate {t : Trace} (ht : SN t) : SN (integrate t) := by
  induction ht with
  | intro t _ ih =>
      constructor
      intro u hu
      change StepCtx (integrate t) u at hu
      cases hu with
      | root hr => exact sn_of_root_integrate hr
      | integrate hs => exact ih _ hs

/-- Root reducts of `merge a b` are `a`, `b`, or the shared term. -/
theorem sn_of_root_merge {a b u : Trace} (ha : SN a) (hb : SN b)
    (h : Step (merge a b) u) : SN u := by
  cases h with
  | R_merge_void_left => exact hb
  | R_merge_void_right => exact ha
  | R_merge_cancel => first | exact ha | exact hb

theorem sn_merge_aux {a : Trace} (ha : SN a) : ∀ b : Trace, SN b → SN (merge a b) := by
  induction ha with
  | intro a ha' iha =>
      intro b hb
      induction hb with
      | intro b hb' ihb =>
          constructor
          intro u hu
          change StepCtx (merge a b) u at hu
          cases hu with
          | root hr => exact sn_of_root_merge (Acc.intro a ha') (Acc.intro b hb') hr
          | mergeLeft hs => exact iha _ hs b (Acc.intro b hb')
          | mergeRight hs => exact ihb _ hs

theorem sn_merge {a b : Trace} (ha : SN a) (hb : SN b) : SN (merge a b) :=
  sn_merge_aux ha b hb

theorem sn_app_aux {a : Trace} (ha : SN a) : ∀ b : Trace, SN b → SN (app a b) := by
  induction ha with
  | intro a _ iha =>
      intro b hb
      induction hb with
      | intro b hb' ihb =>
          constructor
          intro u hu
          change StepCtx (app a b) u at hu
          cases hu with
          | root hr => cases hr
          | appLeft hs => exact iha _ hs b (Acc.intro b hb')
          | appRight hs => exact ihb _ hs

theorem sn_app {a b : Trace} (ha : SN a) (hb : SN b) : SN (app a b) :=
  sn_app_aux ha b hb

/-- Root reducts of `eqW a b`: `void` or `integrate (merge a b)`. -/
theorem sn_of_root_eqW {a b u : Trace} (ha : SN a) (hb : SN b)
    (h : Step (eqW a b) u) : SN u := by
  cases h with
  | R_eq_refl => exact sn_void
  | R_eq_diff => exact sn_integrate (sn_merge ha hb)

theorem sn_eqW_aux {a : Trace} (ha : SN a) : ∀ b : Trace, SN b → SN (eqW a b) := by
  induction ha with
  | intro a ha' iha =>
      intro b hb
      induction hb with
      | intro b hb' ihb =>
          constructor
          intro u hu
          change StepCtx (eqW a b) u at hu
          cases hu with
          | root hr => exact sn_of_root_eqW (Acc.intro a ha') (Acc.intro b hb') hr
          | eqLeft hs => exact iha _ hs b (Acc.intro b hb')
          | eqRight hs => exact ihb _ hs

theorem sn_eqW {a b : Trace} (ha : SN a) (hb : SN b) : SN (eqW a b) :=
  sn_eqW_aux ha b hb

/-! ## The descent relation is well founded below strongly normalizing terms -/

theorem acc_descent_aux :
    ∀ t : Trace, SN t → (∀ a, StepCtx t a → Acc Descent a) → Acc Descent t := by
  intro t
  induction t with
  | void =>
      intro _ H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub
  | delta t iht =>
      intro hsn H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub with
        | delta =>
            apply iht (sn_imm_sub hsn (ImmSub.delta t))
            intro a' ha'
            exact Acc.inv (H (delta a') (StepCtx.delta ha')) (Or.inr (ImmSub.delta a'))
  | integrate t iht =>
      intro hsn H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub with
        | integrate =>
            apply iht (sn_imm_sub hsn (ImmSub.integrate t))
            intro a' ha'
            exact Acc.inv (H (integrate a') (StepCtx.integrate ha'))
              (Or.inr (ImmSub.integrate a'))
  | merge a b iha ihb =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | mergeLeft =>
            apply iha (sn_imm_sub hsn (ImmSub.mergeLeft a b))
            intro a' ha'
            exact Acc.inv (H (merge a' b) (StepCtx.mergeLeft ha'))
              (Or.inr (ImmSub.mergeLeft a' b))
        | mergeRight =>
            apply ihb (sn_imm_sub hsn (ImmSub.mergeRight a b))
            intro b' hb'
            exact Acc.inv (H (merge a b') (StepCtx.mergeRight hb'))
              (Or.inr (ImmSub.mergeRight a b'))
  | app a b iha ihb =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | appLeft =>
            apply iha (sn_imm_sub hsn (ImmSub.appLeft a b))
            intro a' ha'
            exact Acc.inv (H (app a' b) (StepCtx.appLeft ha'))
              (Or.inr (ImmSub.appLeft a' b))
        | appRight =>
            apply ihb (sn_imm_sub hsn (ImmSub.appRight a b))
            intro b' hb'
            exact Acc.inv (H (app a b') (StepCtx.appRight hb'))
              (Or.inr (ImmSub.appRight a b'))
  | recDelta b s n ihb ihs ihn =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | recBase =>
            apply ihb (sn_imm_sub hsn (ImmSub.recBase b s n))
            intro b' hb'
            exact Acc.inv (H (recDelta b' s n) (StepCtx.recBase hb'))
              (Or.inr (ImmSub.recBase b' s n))
        | recStep =>
            apply ihs (sn_imm_sub hsn (ImmSub.recStep b s n))
            intro s' hs'
            exact Acc.inv (H (recDelta b s' n) (StepCtx.recStep hs'))
              (Or.inr (ImmSub.recStep b s' n))
        | recCounter =>
            apply ihn (sn_imm_sub hsn (ImmSub.recCounter b s n))
            intro n' hn'
            exact Acc.inv (H (recDelta b s n') (StepCtx.recCounter hn'))
              (Or.inr (ImmSub.recCounter b s n'))
  | eqW a b iha ihb =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | eqLeft =>
            apply iha (sn_imm_sub hsn (ImmSub.eqLeft a b))
            intro a' ha'
            exact Acc.inv (H (eqW a' b) (StepCtx.eqLeft ha'))
              (Or.inr (ImmSub.eqLeft a' b))
        | eqRight =>
            apply ihb (sn_imm_sub hsn (ImmSub.eqRight a b))
            intro b' hb'
            exact Acc.inv (H (eqW a b') (StepCtx.eqRight hb'))
              (Or.inr (ImmSub.eqRight a b'))

theorem acc_descent_of_sn {t : Trace} (ht : SN t) : Acc Descent t := by
  induction ht with
  | intro t h ih => exact acc_descent_aux t (Acc.intro t h) (fun a ha => ih a ha)

/-! ## The recursor -/

/-- `recDelta b s n` is strongly normalizing when `b`, `s` are and `n` is
    `Descent`-accessible. `R_rec_succ` uses the descent `n` against
    `delta n`, the dependency-pair comparison; `R_rec_zero` uses `SN b`. -/
theorem sn_recDelta {n : Trace} (hn : Acc Descent n) :
    ∀ b s : Trace, SN b → SN s → SN (recDelta b s n) := by
  induction hn with
  | intro n _ ihn =>
      intro b s hb
      revert s
      induction hb with
      | intro b hb' ihb =>
          intro s hs
          induction hs with
          | intro s hs' ihs =>
              constructor
              intro u hu
              change StepCtx (recDelta b s n) u at hu
              cases hu with
              | root hr =>
                  cases hr with
                  | R_rec_zero => exact Acc.intro b hb'
                  | R_rec_succ b s m =>
                      apply sn_app (Acc.intro s hs')
                      exact ihn m (Or.inr (ImmSub.delta m)) b s (Acc.intro b hb') (Acc.intro s hs')
              | recBase hs => exact ihb _ hs s (Acc.intro s hs')
              | recStep hs => exact ihs _ hs
              | recCounter hs =>
                  exact ihn _ (Or.inl hs) b s (Acc.intro b hb') (Acc.intro s hs')

/-- Every trace is strongly normalizing under the full contextual relation. -/
theorem sn_all : ∀ t : Trace, SN t
  | void => sn_void
  | delta t => sn_delta (sn_all t)
  | integrate t => sn_integrate (sn_all t)
  | merge a b => sn_merge (sn_all a) (sn_all b)
  | app a b => sn_app (sn_all a) (sn_all b)
  | recDelta b s n => sn_recDelta (acc_descent_of_sn (sn_all n)) b s (sn_all b) (sn_all s)
  | eqW a b => sn_eqW (sn_all a) (sn_all b)

/-- Strong normalization of the full KO7 contextual system on the
    rule-derived route: no interpretation, no ordering parameter. -/
theorem wf_StepCtxRev_rule_derived : WellFounded StepCtxRev := ⟨sn_all⟩

/-- The dependency-pair comparison is an instance of the descent relation. -/
theorem dp_pair_is_descent (b s n : Trace) :
    KO7Benchmark.KO7DependencyPairs.DPPair (recDelta b s (delta n)) (recDelta b s n) ∧
      Descent n (delta n) :=
  ⟨KO7Benchmark.KO7DependencyPairs.DPPair.succ b s n, Or.inr (ImmSub.delta n)⟩

end KO7Benchmark.PaperB.KO7DPSoundness
