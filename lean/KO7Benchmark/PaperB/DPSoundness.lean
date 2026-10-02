/-
  Dependency-pair soundness for the schema, rule-derived (upgrade U1 of the
  2026-09-17 Lean audit).

  Relation: the two-rule schema of `SchemaKernel`.
  Closure: full contextual closure `Step`.
  Property: `Step` is strongly normalizing, proved without any interpretation,
    weight, or ordering parameter. The proof is the subterm-criterion argument
    specialised to the schema:
      * strong normalization is closed under the constructors `S` and `G`;
      * below a strongly normalizing term, the relation "reduct or immediate
        subterm" is well founded (`acc_descent_of_sn`);
      * `F x y n` is strongly normalizing when `x`, `y`, `n` are, by induction
        along that relation on `n` inside inductions on the reductions of `x`
        and `y` (`sn_f`). At the recursive rule the only comparison used is the
        one the dependency pair fixes: `n` against `S n`.
    The earlier bridge `CandidateD_SoundnessBridge` obtained the same
    conclusion through the polynomial `NonlinearWitness.muW`; this module
    removes that detour, so the rule-derived route's full-system claim rests
    on the rule-derived comparison alone.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.PaperB.BoundaryWitness

set_option autoImplicit false

namespace KO7Benchmark.PaperB.DPSoundness

open KO7Benchmark.SchemaTests
open SKTerm

/-- Reverse step relation: `StepRev a t` when `t` steps to `a`. -/
def StepRev : SKTerm → SKTerm → Prop := fun a t => Step t a

/-- Strong normalization of a term: every reduction sequence from it is finite. -/
def SN (t : SKTerm) : Prop := Acc StepRev t

/-- Immediate subterm: `ImmSub a t` when `a` is an argument of `t`. -/
inductive ImmSub : SKTerm → SKTerm → Prop
  | s_arg (t : SKTerm) : ImmSub t (s t)
  | g_left (a b : SKTerm) : ImmSub a (g a b)
  | g_right (a b : SKTerm) : ImmSub b (g a b)
  | f_arg1 (x y n : SKTerm) : ImmSub x (f x y n)
  | f_arg2 (x y n : SKTerm) : ImmSub y (f x y n)
  | f_arg3 (x y n : SKTerm) : ImmSub n (f x y n)

/-- Descent relation of the subterm criterion: `Descent a t` when `a` is a
    reduct of `t` or an immediate subterm of `t`. -/
def Descent : SKTerm → SKTerm → Prop := fun a t => Step t a ∨ ImmSub a t

/-! ## Strong normalization passes down through contexts -/

/-- If `C u` is strongly normalizing and `C` transports steps, `u` is
    strongly normalizing. -/
theorem sn_of_congr (C : SKTerm → SKTerm)
    (hC : ∀ {u u' : SKTerm}, Step u u' → Step (C u) (C u')) :
    ∀ {w : SKTerm}, SN w → ∀ u, w = C u → SN u := by
  intro w hw
  induction hw with
  | intro w _ ih =>
      intro u hu
      subst hu
      constructor
      intro u' hu'
      exact ih (C u') (hC hu') u' rfl

/-- Immediate subterms of strongly normalizing terms are strongly normalizing. -/
theorem sn_imm_sub {t a : SKTerm} (ht : SN t) (h : ImmSub a t) : SN a :=
  match h with
  | .s_arg t' => sn_of_congr (fun w => s w) (fun hs => Step.s_arg hs) ht t' rfl
  | .g_left a' b' => sn_of_congr (fun w => g w b') (fun hs => Step.g_left hs) ht a' rfl
  | .g_right a' b' => sn_of_congr (fun w => g a' w) (fun hs => Step.g_right hs) ht b' rfl
  | .f_arg1 x' y' n' => sn_of_congr (fun w => f w y' n') (fun hs => Step.f_arg1 hs) ht x' rfl
  | .f_arg2 x' y' n' => sn_of_congr (fun w => f x' w n') (fun hs => Step.f_arg2 hs) ht y' rfl
  | .f_arg3 x' y' n' => sn_of_congr (fun w => f x' y' w) (fun hs => Step.f_arg3 hs) ht n' rfl

/-! ## Strong normalization builds up through `S` and `G` -/

theorem sn_var (v : Nat) : SN (var v) := by
  constructor
  intro u hu
  change Step (var v) u at hu
  cases hu with
  | root hr => cases hr

theorem sn_z : SN z := by
  constructor
  intro u hu
  change Step z u at hu
  cases hu with
  | root hr => cases hr

/-- No rule has `S` at the root, so `S t` inherits strong normalization. -/
theorem sn_s {t : SKTerm} (ht : SN t) : SN (s t) := by
  induction ht with
  | intro t _ ih =>
      constructor
      intro u hu
      change Step (s t) u at hu
      cases hu with
      | root hr => cases hr
      | s_arg hs => exact ih _ hs

/-- No rule has `G` at the root, so `G a b` inherits strong normalization. -/
theorem sn_g_aux {a : SKTerm} (ha : SN a) : ∀ b : SKTerm, SN b → SN (g a b) := by
  induction ha with
  | intro a _ iha =>
      intro b hb
      induction hb with
      | intro b hb' ihb =>
          constructor
          intro u hu
          change Step (g a b) u at hu
          cases hu with
          | root hr => cases hr
          | g_left hs => exact iha _ hs b (Acc.intro b hb')
          | g_right hs => exact ihb _ hs

theorem sn_g {a b : SKTerm} (ha : SN a) (hb : SN b) : SN (g a b) :=
  sn_g_aux ha b hb

/-! ## The descent relation is well founded below strongly normalizing terms -/

/-- Structural core: a strongly normalizing term whose reducts are all
    `Descent`-accessible is itself `Descent`-accessible. -/
theorem acc_descent_aux :
    ∀ t : SKTerm, SN t → (∀ a, Step t a → Acc Descent a) → Acc Descent t := by
  intro t
  induction t with
  | var v =>
      intro _ H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub
  | z =>
      intro _ H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub
  | s t iht =>
      intro hsn H
      constructor
      intro a ha
      rcases ha with hstep | hsub
      · exact H a hstep
      · cases hsub with
        | s_arg =>
            apply iht (sn_imm_sub hsn (ImmSub.s_arg t))
            intro a' ha'
            exact Acc.inv (H (s a') (Step.s_arg ha')) (Or.inr (ImmSub.s_arg a'))
  | g a b iha ihb =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | g_left =>
            apply iha (sn_imm_sub hsn (ImmSub.g_left a b))
            intro a' ha'
            exact Acc.inv (H (g a' b) (Step.g_left ha')) (Or.inr (ImmSub.g_left a' b))
        | g_right =>
            apply ihb (sn_imm_sub hsn (ImmSub.g_right a b))
            intro b' hb'
            exact Acc.inv (H (g a b') (Step.g_right hb')) (Or.inr (ImmSub.g_right a b'))
  | f x y n ihx ihy ihn =>
      intro hsn H
      constructor
      intro c hc
      rcases hc with hstep | hsub
      · exact H c hstep
      · cases hsub with
        | f_arg1 =>
            apply ihx (sn_imm_sub hsn (ImmSub.f_arg1 x y n))
            intro x' hx'
            exact Acc.inv (H (f x' y n) (Step.f_arg1 hx')) (Or.inr (ImmSub.f_arg1 x' y n))
        | f_arg2 =>
            apply ihy (sn_imm_sub hsn (ImmSub.f_arg2 x y n))
            intro y' hy'
            exact Acc.inv (H (f x y' n) (Step.f_arg2 hy')) (Or.inr (ImmSub.f_arg2 x y' n))
        | f_arg3 =>
            apply ihn (sn_imm_sub hsn (ImmSub.f_arg3 x y n))
            intro n' hn'
            exact Acc.inv (H (f x y n') (Step.f_arg3 hn')) (Or.inr (ImmSub.f_arg3 x y n'))

/-- Below a strongly normalizing term, "reduct or immediate subterm" is well
    founded. This is the well-foundedness the subterm criterion uses. -/
theorem acc_descent_of_sn {t : SKTerm} (ht : SN t) : Acc Descent t := by
  induction ht with
  | intro t h ih => exact acc_descent_aux t (Acc.intro t h) (fun a ha => ih a ha)

/-! ## The recursor -/

/-- `F x y n` is strongly normalizing when `x`, `y` are and `n` is
    `Descent`-accessible. The recursive rule is handled by the descent
    `n` against `S n`, the dependency-pair comparison; the base rule by `SN x`;
    the contexts by the inductions on `x`, `y`, and the reducts of `n`. -/
theorem sn_f {n : SKTerm} (hn : Acc Descent n) :
    ∀ x y : SKTerm, SN x → SN y → SN (f x y n) := by
  induction hn with
  | intro n _ ihn =>
      intro x y hx
      revert y
      induction hx with
      | intro x hx' ihx =>
          intro y hy
          induction hy with
          | intro y hy' ihy =>
              constructor
              intro u hu
              change Step (f x y n) u at hu
              cases hu with
              | root hr =>
                  cases hr with
                  | base => exact Acc.intro x hx'
                  | succ x y m =>
                      apply sn_g (Acc.intro y hy')
                      exact ihn m (Or.inr (ImmSub.s_arg m)) x y (Acc.intro x hx') (Acc.intro y hy')
              | f_arg1 hs => exact ihx _ hs y (Acc.intro y hy')
              | f_arg2 hs => exact ihy _ hs
              | f_arg3 hs => exact ihn _ (Or.inl hs) x y (Acc.intro x hx') (Acc.intro y hy')

/-- Every term is strongly normalizing. -/
theorem sn_all : ∀ t : SKTerm, SN t
  | var v => sn_var v
  | z => sn_z
  | s t => sn_s (sn_all t)
  | g a b => sn_g (sn_all a) (sn_all b)
  | f x y n => sn_f (acc_descent_of_sn (sn_all n)) x y (sn_all x) (sn_all y)

/-- Strong normalization of the schema by the subterm criterion, with no
    interpretation. -/
theorem wf_StepRev : WellFounded StepRev := ⟨sn_all⟩

/-- The same statement on the reverse relation used by the earlier witnesses,
    so the two proofs are interchangeable in every bridge. -/
theorem wf_NonlinearWitness_StepRev : WellFounded NonlinearWitness.StepRev := wf_StepRev

/-- The rule-extracted dependency-pair witness with its full-system field
    proved by the subterm criterion instead of the polynomial bridge. -/
theorem schema_dp_rule_extracted_witness_rule_derived :
    KO7Benchmark.PaperB.RuleExtractedDPWitness := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro x y n
    exact CandidateD.DPPair.succ x y n
  · intro x y n
    simp [CandidateD.sDepth]
  · exact CandidateD.wf_DPPairRev
  · exact wf_NonlinearWitness_StepRev

/-- The dependency-pair comparison is an instance of the descent relation:
    the counter of the recursive call is an immediate subterm of the counter
    of the call site. -/
theorem dp_pair_is_descent (x y n : SKTerm) :
    CandidateD.DPPair (f x y (s n)) (f x y n) ∧ Descent n (s n) :=
  ⟨CandidateD.DPPair.succ x y n, Or.inr (ImmSub.s_arg n)⟩

end KO7Benchmark.PaperB.DPSoundness
