/-
  Structural measure families for the schema scorer.

  Relation: the duplicating SchemaKernel rules, the extracted CandidateD
    dependency pair, and the copy-removed SANS control.
  Closure: root rules where a root counterexample suffices; full contextual
    Step for the max-depth and ordinal statements; the multiset success
    theorem is only for the transformed dependency-pair relation.
  Property: constructor-offset maximum-depth measures fail on both systems;
    a standard Dershowitz-Manna immediate-subterm size multiset fails the
    schema recursive rule; the transformed counter singleton succeeds under
    a well-founded singleton multiset order that is a restriction of that
    standard multiset extension; ordinal-valued whole-term measures are
    inhabited on both systems by lifts of exact contextual witnesses.
  Trust: mathlib and existing benchmark modules only. The generic Mathlib
    Dershowitz-Manna module is not imported because its olean is absent in
    this package cache; the standard defining relation needed for the
    counterexample is restated locally, and only the singleton restriction
    needed for the positive transformed problem is proved well founded here.
-/
import Mathlib.Tactic
import Mathlib.SetTheory.Ordinal.Arithmetic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.SANSTests.LinearWitness
import KO7Benchmark.ScoringAnchors.MeasureFailures

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.StructuralMeasures

open KO7Benchmark.SchemaTests
open SKTerm
open KO7Benchmark.SchemaTests.CandidateD

/-! ## Maximum-depth constructor-offset measures on the duplicating schema -/

structure MaxWeights where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace MaxWeights

def eval (M : MaxWeights) : SKTerm → Nat
  | .var _ => M.wVar
  | .z => M.wZ
  | .s t => M.wS + M.eval t
  | .g a b => M.wG + max (M.eval a) (M.eval b)
  | .f x y n => M.wF + max (M.eval x) (max (M.eval y) (M.eval n))

@[simp] theorem eval_var (M : MaxWeights) (v : Nat) :
    M.eval (.var v) = M.wVar := rfl

@[simp] theorem eval_z (M : MaxWeights) : M.eval .z = M.wZ := rfl

@[simp] theorem eval_s (M : MaxWeights) (t : SKTerm) :
    M.eval (.s t) = M.wS + M.eval t := rfl

@[simp] theorem eval_g (M : MaxWeights) (a b : SKTerm) :
    M.eval (.g a b) = M.wG + max (M.eval a) (M.eval b) := rfl

@[simp] theorem eval_f (M : MaxWeights) (x y n : SKTerm) :
    M.eval (.f x y n) =
      M.wF + max (M.eval x) (max (M.eval y) (M.eval n)) := rfl

theorem recursive_call_ties_source (M : MaxWeights) :
    M.eval (f z (s z) z) = M.eval (f z (s z) (s z)) := by
  simp [eval]

theorem recursive_counterexample_le (M : MaxWeights) :
    M.eval (f z (s z) (s z)) ≤ M.eval (g (s z) (f z (s z) z)) := by
  rw [← recursive_call_ties_source M]
  have hmax :
      M.eval (f z (s z) z) ≤
        max (M.eval (s z)) (M.eval (f z (s z) z)) :=
    le_max_right _ _
  simp only [eval_g]
  omega

theorem no_max_weights_orient_recursive_root (M : MaxWeights) :
    ¬ (∀ x y n : SKTerm,
        M.eval (g y (f x y n)) < M.eval (f x y (s n))) := by
  intro h
  have hlt := h z (s z) z
  have hle := recursive_counterexample_le M
  omega

theorem no_max_weights_orient_step (M : MaxWeights) :
    ¬ (∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a) := by
  intro h
  apply no_max_weights_orient_recursive_root M
  intro x y n
  exact h (Step.root (RootStep.succ x y n))

def standard : MaxWeights := ⟨1, 1, 1, 1, 1⟩

end MaxWeights

def depth : SKTerm → Nat
  | .var _ => 1
  | .z => 1
  | .s t => depth t + 1
  | .g a b => max (depth a) (depth b) + 1
  | .f x y n => max (depth x) (max (depth y) (depth n)) + 1

theorem max_standard_eq_depth (t : SKTerm) :
    MaxWeights.standard.eval t = depth t := by
  induction t with
  | var v => rfl
  | z => rfl
  | s t ih =>
      change 1 + MaxWeights.standard.eval t = depth t + 1
      rw [ih]
      omega
  | g a b iha ihb =>
      change 1 + max (MaxWeights.standard.eval a) (MaxWeights.standard.eval b) =
        max (depth a) (depth b) + 1
      rw [iha, ihb]
      omega
  | f x y n ihx ihy ihn =>
      change 1 + max (MaxWeights.standard.eval x)
          (max (MaxWeights.standard.eval y) (MaxWeights.standard.eval n)) =
        max (depth x) (max (depth y) (depth n)) + 1
      rw [ihx, ihy, ihn]
      omega

theorem depth_not_step_orienting :
    ¬ (∀ {a b : SKTerm}, Step a b → depth b < depth a) := by
  intro h
  apply MaxWeights.no_max_weights_orient_step MaxWeights.standard
  intro a b hs
  simpa only [max_standard_eq_depth] using h hs

/-! ## Maximum-depth control: copy removal does not rescue this family -/

namespace SANSControl

open KO7Benchmark.SANSTests
open SANSTerm

structure MaxWeights where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace MaxWeights

def eval (M : MaxWeights) : SANSTerm → Nat
  | .var _ => M.wVar
  | .z => M.wZ
  | .s t => M.wS + M.eval t
  | .g t => M.wG + M.eval t
  | .f x y n => M.wF + max (M.eval x) (max (M.eval y) (M.eval n))

@[simp] theorem eval_z (M : MaxWeights) : M.eval .z = M.wZ := rfl

@[simp] theorem eval_s (M : MaxWeights) (t : SANSTerm) :
    M.eval (.s t) = M.wS + M.eval t := rfl

@[simp] theorem eval_g (M : MaxWeights) (t : SANSTerm) :
    M.eval (.g t) = M.wG + M.eval t := rfl

@[simp] theorem eval_f (M : MaxWeights) (x y n : SANSTerm) :
    M.eval (.f x y n) =
      M.wF + max (M.eval x) (max (M.eval y) (M.eval n)) := rfl

theorem recursive_call_ties_source (M : MaxWeights) :
    M.eval (.f .z (.s .z) .z) = M.eval (.f .z (.s .z) (.s .z)) := by
  simp [eval]

theorem recursive_counterexample_le (M : MaxWeights) :
    M.eval (.f .z (.s .z) (.s .z)) ≤
      M.eval (.g (.f .z (.s .z) .z)) := by
  rw [← recursive_call_ties_source M]
  simp only [eval_g]
  omega

theorem no_max_weights_orient_step (M : MaxWeights) :
    ¬ (∀ {a b : SANSTerm}, KO7Benchmark.SANSTests.Step a b →
        M.eval b < M.eval a) := by
  intro h
  have hlt := h
    (KO7Benchmark.SANSTests.Step.root
      (KO7Benchmark.SANSTests.RootStep.succ .z (.s .z) .z))
  have hle := recursive_counterexample_le M
  omega

end MaxWeights
end SANSControl

/-! ## Direct immediate-subterm multiset and transformed-call multiset -/

/-- Standard Dershowitz-Manna multiset extension, restated locally because the
Mathlib module containing the same definition is not built in this package
cache. M is smaller than N when a nonempty part Z of N is replaced by a
multiset Y whose every element is strictly below some element of Z. -/
def DMLT (M N : Multiset Nat) : Prop :=
  ∃ X Y Z : Multiset Nat,
    Z ≠ 0 ∧
    M = X + Y ∧
    N = X + Z ∧
    ∀ y ∈ Y, ∃ z ∈ Z, y < z

def immediateSizeBag : SKTerm → Multiset Nat
  | .var _ => 0
  | .z => 0
  | .s t => {KO7Benchmark.ScoringAnchors.MeasureFailures.size t}
  | .g a b =>
      {KO7Benchmark.ScoringAnchors.MeasureFailures.size a,
       KO7Benchmark.ScoringAnchors.MeasureFailures.size b}
  | .f x y n =>
      {KO7Benchmark.ScoringAnchors.MeasureFailures.size x,
       KO7Benchmark.ScoringAnchors.MeasureFailures.size y,
       KO7Benchmark.ScoringAnchors.MeasureFailures.size n}

theorem dm_element_bounded {M N : Multiset Nat}
    (h : DMLT M N) {m : Nat} (hm : m ∈ M) :
    ∃ n ∈ N, m ≤ n := by
  rcases h with ⟨X, Y, Z, hZ, rfl, rfl, hYZ⟩
  simp only [Multiset.mem_add] at hm
  rcases hm with hm | hm
  · exact ⟨m, by simp [hm], Nat.le_refl m⟩
  · rcases hYZ m hm with ⟨n, hn, hmn⟩
    exact ⟨n, by simp [hn], Nat.le_of_lt hmn⟩

theorem immediate_size_multiset_fails_recursive_root :
    ¬ DMLT
      (immediateSizeBag (g z (f z z z)))
      (immediateSizeBag (f z z (s z))) := by
  intro h
  have hm : 4 ∈ immediateSizeBag (g z (f z z z)) := by
    decide
  rcases dm_element_bounded h hm with ⟨n, hn, hle⟩
  simp [immediateSizeBag, KO7Benchmark.ScoringAnchors.MeasureFailures.size] at hn
  omega

/-- A well-founded multiset relation sufficient for this transformed problem:
both bags must be singleton and their elements decrease. -/
def SingletonBagLT (M N : Multiset Nat) : Prop :=
  ∃ a b : Nat, M = {a} ∧ N = {b} ∧ a < b

theorem singletonBagLT_sub_dm {M N : Multiset Nat}
    (h : SingletonBagLT M N) : DMLT M N := by
  rcases h with ⟨a, b, rfl, rfl, hab⟩
  refine ⟨0, {a}, {b}, by simp, by simp, by simp, ?_⟩
  intro y hy
  simp only [Multiset.mem_singleton] at hy
  subst y
  exact ⟨b, by simp, hab⟩

theorem wf_singletonBagLT : WellFounded SingletonBagLT := by
  have hsub :
      Subrelation SingletonBagLT
        (InvImage (fun a b : Nat => a < b) Multiset.sum) := by
    intro M N h
    rcases h with ⟨a, b, rfl, rfl, hab⟩
    simpa using hab
  exact Subrelation.wf hsub
    (InvImage.wf Multiset.sum Nat.lt_wfRel.wf)

def dpBag : SKTerm → Multiset Nat
  | .f _ _ n => {sDepth n}
  | _ => 0

theorem dpBag_pair_decreases :
    ∀ {a b : SKTerm}, DPPair a b →
      SingletonBagLT (dpBag b) (dpBag a)
  | _, _, DPPair.succ x y n => by
      refine ⟨sDepth n, sDepth (s n), by simp [dpBag], by simp [dpBag], ?_⟩
      simp [sDepth]

theorem dpBag_pair_decreases_dm {a b : SKTerm} (h : DPPair a b) :
    DMLT (dpBag b) (dpBag a) :=
  singletonBagLT_sub_dm (dpBag_pair_decreases h)

theorem wf_DPPairRev_singleton_multiset : WellFounded DPPairRev := by
  let R : SKTerm → SKTerm → Prop :=
    InvImage SingletonBagLT dpBag
  have hsub : Subrelation DPPairRev R := by
    intro a b hab
    exact dpBag_pair_decreases hab
  exact Subrelation.wf hsub
    (InvImage.wf dpBag wf_singletonBagLT)

/-! ## Ordinal-valued contextual measures are inhabited -/

noncomputable def ordinalMu (t : SKTerm) : Ordinal.{0} :=
  KO7Benchmark.SchemaTests.NonlinearWitness.muW t

theorem ordinalMu_step_decreases {t u : SKTerm} (h : Step t u) :
    ordinalMu u < ordinalMu t := by
  change
    ((KO7Benchmark.SchemaTests.NonlinearWitness.muW u : Nat) : Ordinal.{0}) <
      ((KO7Benchmark.SchemaTests.NonlinearWitness.muW t : Nat) : Ordinal.{0})
  exact_mod_cast
    KO7Benchmark.SchemaTests.NonlinearWitness.muW_step_decreases h

theorem wf_StepRev_ordinal :
    WellFounded (fun a b : SKTerm => Step b a) := by
  have hsub :
      Subrelation (fun a b : SKTerm => Step b a)
        (InvImage (fun a b : Ordinal.{0} => a < b) ordinalMu) := by
    intro a b hab
    exact ordinalMu_step_decreases hab
  exact Subrelation.wf hsub (InvImage.wf ordinalMu Ordinal.lt_wf)

noncomputable def sansOrdinalMu
    (t : KO7Benchmark.SANSTests.SANSTerm) : Ordinal.{0} :=
  KO7Benchmark.SANSTests.LinearWitness.mu t

theorem sansOrdinalMu_step_decreases
    {t u : KO7Benchmark.SANSTests.SANSTerm}
    (h : KO7Benchmark.SANSTests.Step t u) :
    sansOrdinalMu u < sansOrdinalMu t := by
  change
    ((KO7Benchmark.SANSTests.LinearWitness.mu u : Nat) : Ordinal.{0}) <
      ((KO7Benchmark.SANSTests.LinearWitness.mu t : Nat) : Ordinal.{0})
  exact_mod_cast
    KO7Benchmark.SANSTests.LinearWitness.mu_step_decreases h

theorem wf_SANS_StepRev_ordinal :
    WellFounded
      (fun a b : KO7Benchmark.SANSTests.SANSTerm =>
        KO7Benchmark.SANSTests.Step b a) := by
  have hsub :
      Subrelation
        (fun a b : KO7Benchmark.SANSTests.SANSTerm =>
          KO7Benchmark.SANSTests.Step b a)
        (InvImage (fun a b : Ordinal.{0} => a < b) sansOrdinalMu) := by
    intro a b hab
    exact sansOrdinalMu_step_decreases hab
  exact Subrelation.wf hsub
    (InvImage.wf sansOrdinalMu Ordinal.lt_wf)

end KO7Benchmark.ScoringAnchors.StructuralMeasures
