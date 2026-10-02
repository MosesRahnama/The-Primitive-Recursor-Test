/-
Relation: KO7Kernel.Step, KO7ContextClosure.StepCtx, the exact Schema A recursive-rule pattern, and the SANS control pattern.
Closure: root-only for the positive ranking and named-method barriers; full contextual closure only for the root-rank non-transport control.
Property: exact eight-rule Nat-ranking contract with a concrete witness; a load-bearing rec-succ control; KBO variable-condition obstruction; path-order precedence-route iff F > G; SANS controls.
Trust: kernel-checked with mathlib and existing benchmark modules; no additional trust declarations.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.SchemaTests.CandidateC_KBOFailure
import KO7Benchmark.SchemaTests.PathOrderFailurePatterns
import KO7Benchmark.SANSTests.KBOStyleSupport
import KO7Benchmark.SANSTests.PathOrderSupport

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.Test01MethodBoundaries

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

/-! ## Exact root-only natural-number ranking family -/

def StrictlyOrientsRoot (mu : Trace → Nat) : Prop :=
  ∀ {a b : Trace}, Step a b → mu b < mu a

structure RootNatObligations (mu : Trace → Nat) : Prop where
  intDelta : ∀ t : Trace, mu void < mu (integrate (delta t))
  mergeVoidLeft : ∀ t : Trace, mu t < mu (merge void t)
  mergeVoidRight : ∀ t : Trace, mu t < mu (merge t void)
  mergeCancel : ∀ t : Trace, mu t < mu (merge t t)
  recZero : ∀ b s : Trace, mu b < mu (recDelta b s void)
  recSucc : ∀ b s n : Trace,
    mu (app s (recDelta b s n)) < mu (recDelta b s (delta n))
  eqRefl : ∀ a : Trace, mu void < mu (eqW a a)
  eqDiff : ∀ a b : Trace,
    mu (integrate (merge a b)) < mu (eqW a b)

/--
Exact family theorem for the natural-number ranking method on Test 01.
Every field is one displayed KO7 root rule, and conversely every root step is
one of those eight fields.

Relation: KO7Kernel.Step.
Closure: root-only.
Property: strict orientation by a Nat ranking.
Trust: kernel-checked from KO7Kernel.Step and Nat arithmetic.
-/
theorem rootNatObligations_iff_orients (mu : Trace → Nat) :
    RootNatObligations mu ↔ StrictlyOrientsRoot mu := by
  constructor
  · intro h a b hs
    cases hs with
    | R_int_delta t => exact h.intDelta t
    | R_merge_void_left => exact h.mergeVoidLeft b
    | R_merge_void_right => exact h.mergeVoidRight b
    | R_merge_cancel => exact h.mergeCancel b
    | R_rec_zero b s => exact h.recZero b s
    | R_rec_succ b s n => exact h.recSucc b s n
    | R_eq_refl a => exact h.eqRefl a
    | R_eq_diff a b => exact h.eqDiff a b
  · intro h
    refine {
      intDelta := ?_
      mergeVoidLeft := ?_
      mergeVoidRight := ?_
      mergeCancel := ?_
      recZero := ?_
      recSucc := ?_
      eqRefl := ?_
      eqDiff := ?_ }
    · intro t
      exact h (Step.R_int_delta t)
    · intro t
      exact h (Step.R_merge_void_left t)
    · intro t
      exact h (Step.R_merge_void_right t)
    · intro t
      exact h (Step.R_merge_cancel t)
    · intro b s
      exact h (Step.R_rec_zero b s)
    · intro b s n
      exact h (Step.R_rec_succ b s n)
    · intro a
      exact h (Step.R_eq_refl a)
    · intro a b
      exact h (Step.R_eq_diff a b)

def RootStepRev : Trace → Trace → Prop := fun a b => Step b a

theorem rootNatObligations_wf (mu : Trace → Nat) (h : RootNatObligations mu) :
    WellFounded RootStepRev := by
  have horient : StrictlyOrientsRoot mu :=
    (rootNatObligations_iff_orients mu).1 h
  have hsub : Subrelation RootStepRev (InvImage (fun a b : Nat => a < b) mu) := by
    intro a b hab
    exact horient hab
  exact Subrelation.wf hsub (InvImage.wf mu Nat.lt_wfRel.wf)

/--
A concrete remaining-root-reduction-height ranking. It assigns zero to roots
that cannot step, while merge and recDelta retain enough height to expose an
arbitrary reduct that may itself step at the root.
-/
def rootFuel : Trace → Nat
  | .void => 0
  | .delta _ => 0
  | .integrate (.delta _) => 1
  | .integrate _ => 0
  | .merge a b => Nat.max (rootFuel a) (rootFuel b) + 1
  | .app _ _ => 0
  | .recDelta b _ _ => rootFuel b + 1
  | .eqW a b => Nat.max (rootFuel a) (rootFuel b) + 1

theorem rootFuel_obligations : RootNatObligations rootFuel := by
  refine {
    intDelta := ?_
    mergeVoidLeft := ?_
    mergeVoidRight := ?_
    mergeCancel := ?_
    recZero := ?_
    recSucc := ?_
    eqRefl := ?_
    eqDiff := ?_ }
  · intro t
    exact Nat.zero_lt_one
  · intro t
    change rootFuel t < Nat.max 0 (rootFuel t) + 1
    exact Nat.lt_succ_of_le (Nat.le_max_right 0 (rootFuel t))
  · intro t
    change rootFuel t < Nat.max (rootFuel t) 0 + 1
    exact Nat.lt_succ_of_le (Nat.le_max_left (rootFuel t) 0)
  · intro t
    change rootFuel t < Nat.max (rootFuel t) (rootFuel t) + 1
    exact Nat.lt_succ_of_le (Nat.le_max_left (rootFuel t) (rootFuel t))
  · intro b s
    change rootFuel b < rootFuel b + 1
    exact Nat.lt_succ_self (rootFuel b)
  · intro b s n
    change 0 < rootFuel b + 1
    exact Nat.zero_lt_succ (rootFuel b)
  · intro a
    change 0 < Nat.max (rootFuel a) (rootFuel a) + 1
    exact Nat.zero_lt_succ _
  · intro a b
    change 0 < Nat.max (rootFuel a) (rootFuel b) + 1
    exact Nat.zero_lt_succ _

theorem rootFuel_orients_root : StrictlyOrientsRoot rootFuel :=
  (rootNatObligations_iff_orients rootFuel).1 rootFuel_obligations

theorem rootFuel_root_wf : WellFounded RootStepRev :=
  rootNatObligations_wf rootFuel rootFuel_obligations

/-! ### The recursive-rule obligation is load-bearing -/

structure RootNatObligationsExceptRecSucc (mu : Trace → Nat) : Prop where
  intDelta : ∀ t : Trace, mu void < mu (integrate (delta t))
  mergeVoidLeft : ∀ t : Trace, mu t < mu (merge void t)
  mergeVoidRight : ∀ t : Trace, mu t < mu (merge t void)
  mergeCancel : ∀ t : Trace, mu t < mu (merge t t)
  recZero : ∀ b s : Trace, mu b < mu (recDelta b s void)
  eqRefl : ∀ a : Trace, mu void < mu (eqW a a)
  eqDiff : ∀ a b : Trace,
    mu (integrate (merge a b)) < mu (eqW a b)

def rootFuelWithoutRecSucc : Trace → Nat
  | .void => 0
  | .delta _ => 0
  | .integrate (.delta _) => 1
  | .integrate _ => 0
  | .merge a b => Nat.max (rootFuelWithoutRecSucc a) (rootFuelWithoutRecSucc b) + 1
  | .app _ _ => 0
  | .recDelta b _ .void => rootFuelWithoutRecSucc b + 1
  | .recDelta _ _ (.delta _) => 0
  | .recDelta b _ _ => rootFuelWithoutRecSucc b + 1
  | .eqW a b => Nat.max (rootFuelWithoutRecSucc a) (rootFuelWithoutRecSucc b) + 1

theorem rootFuelWithoutRecSucc_seven_rules :
    RootNatObligationsExceptRecSucc rootFuelWithoutRecSucc := by
  refine {
    intDelta := ?_
    mergeVoidLeft := ?_
    mergeVoidRight := ?_
    mergeCancel := ?_
    recZero := ?_
    eqRefl := ?_
    eqDiff := ?_ }
  · intro t
    exact Nat.zero_lt_one
  · intro t
    change rootFuelWithoutRecSucc t <
      Nat.max 0 (rootFuelWithoutRecSucc t) + 1
    exact Nat.lt_succ_of_le (Nat.le_max_right 0 (rootFuelWithoutRecSucc t))
  · intro t
    change rootFuelWithoutRecSucc t <
      Nat.max (rootFuelWithoutRecSucc t) 0 + 1
    exact Nat.lt_succ_of_le (Nat.le_max_left (rootFuelWithoutRecSucc t) 0)
  · intro t
    change rootFuelWithoutRecSucc t <
      Nat.max (rootFuelWithoutRecSucc t) (rootFuelWithoutRecSucc t) + 1
    exact Nat.lt_succ_of_le
      (Nat.le_max_left (rootFuelWithoutRecSucc t) (rootFuelWithoutRecSucc t))
  · intro b s
    change rootFuelWithoutRecSucc b < rootFuelWithoutRecSucc b + 1
    exact Nat.lt_succ_self (rootFuelWithoutRecSucc b)
  · intro a
    change 0 <
      Nat.max (rootFuelWithoutRecSucc a) (rootFuelWithoutRecSucc a) + 1
    exact Nat.zero_lt_succ _
  · intro a b
    change 0 <
      Nat.max (rootFuelWithoutRecSucc a) (rootFuelWithoutRecSucc b) + 1
    exact Nat.zero_lt_succ _

theorem rootFuelWithoutRecSucc_fails_recursive_rule :
    ¬ StrictlyOrientsRoot rootFuelWithoutRecSucc := by
  intro h
  have hbad := h (Step.R_rec_succ void void void)
  have hzero : (0 : Nat) < 0 := by
    simpa only [rootFuelWithoutRecSucc] using hbad
  exact (by decide : ¬ ((0 : Nat) < 0)) hzero

theorem recSucc_obligation_is_load_bearing :
    ∃ mu : Trace → Nat,
      RootNatObligationsExceptRecSucc mu ∧ ¬ StrictlyOrientsRoot mu :=
  ⟨rootFuelWithoutRecSucc, rootFuelWithoutRecSucc_seven_rules,
    rootFuelWithoutRecSucc_fails_recursive_rule⟩

/--
The root rank is not a contextual rank. This blocks using the root-only Test 01
certificate as evidence for KO7ContextClosure.StepCtx.
-/
theorem rootFuel_not_contextual :
    ¬ (∀ {a b : Trace}, StepCtx a b → rootFuel b < rootFuel a) := by
  intro h
  have hbad := h (StepCtx.delta (StepCtx.root (Step.R_int_delta void)))
  have hzero : (0 : Nat) < 0 := by
    simpa only [rootFuel] using hbad
  exact (by decide : ¬ ((0 : Nat) < 0)) hzero

/-! ## KBO variable-condition boundary -/

namespace KBOBoundary

/--
The strongest repository-native KBO statement available for the duplicated
recursive schema: any relation satisfying the standard KBO variable-count
condition is unable to orient the recursive rule.

Missing native semantics: this repository has no KO7 KBO datatype/relation and
no generic KBO well-foundedness theorem. This is a necessary-condition barrier,
not a KBO termination theorem.
-/
theorem duplicated_schema_blocks_kbo_variable_condition :
    ¬ (∃ gt : KO7Benchmark.SchemaTests.SKTerm → KO7Benchmark.SchemaTests.SKTerm → Prop,
      KO7Benchmark.SchemaTests.CandidateC.RespectsVariableCondition gt ∧
        gt KO7Benchmark.SchemaTests.CandidateC.succLhs
          KO7Benchmark.SchemaTests.CandidateC.succRhs) :=
  KO7Benchmark.SchemaTests.CandidateC.no_variable_condition_orientation

namespace Control

structure SANSKBOStyleLocalContract : Prop where
  variableBase : ∀ v : Nat,
    KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.baseRhs ≤
      KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.baseLhs
  variableSucc : ∀ v : Nat,
    KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.succRhs ≤
      KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.succLhs
  baseWeightDrop : ∀ x y : KO7Benchmark.SANSTests.SANSTerm,
    KO7Benchmark.SANSTests.KBOStyleSupport.weight x <
      KO7Benchmark.SANSTests.KBOStyleSupport.weight
        (KO7Benchmark.SANSTests.SANSTerm.f x y KO7Benchmark.SANSTests.SANSTerm.z)
  succWeightTie : ∀ x y n : KO7Benchmark.SANSTests.SANSTerm,
    KO7Benchmark.SANSTests.KBOStyleSupport.weight
        (KO7Benchmark.SANSTests.SANSTerm.g
          (KO7Benchmark.SANSTests.SANSTerm.f x y n)) =
      KO7Benchmark.SANSTests.KBOStyleSupport.weight
        (KO7Benchmark.SANSTests.SANSTerm.f x y
          (KO7Benchmark.SANSTests.SANSTerm.s n))
  succPrecedenceTieBreak : ∀ x y n : KO7Benchmark.SANSTests.SANSTerm,
    KO7Benchmark.SANSTests.PathOrderSupport.precRank
        (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
          (KO7Benchmark.SANSTests.SANSTerm.g
            (KO7Benchmark.SANSTests.SANSTerm.f x y n))) <
      KO7Benchmark.SANSTests.PathOrderSupport.precRank
        (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
          (KO7Benchmark.SANSTests.SANSTerm.f x y
            (KO7Benchmark.SANSTests.SANSTerm.s n)))

/--
Nonduplicating control: all repository-local KBO-style obligations recorded for
SANS are jointly inhabited. This still does not claim a generic KBO theorem.
-/
theorem sans_kbo_style_local_contract : SANSKBOStyleLocalContract := by
  refine {
    variableBase := KO7Benchmark.SANSTests.KBOStyleSupport.variable_condition_base
    variableSucc := KO7Benchmark.SANSTests.KBOStyleSupport.variable_condition_succ
    baseWeightDrop := KO7Benchmark.SANSTests.KBOStyleSupport.root_base_weight_drop
    succWeightTie := KO7Benchmark.SANSTests.KBOStyleSupport.root_succ_weight_tie
    succPrecedenceTieBreak :=
      KO7Benchmark.SANSTests.KBOStyleSupport.root_succ_prec_breaks_tie }

end Control
end KBOBoundary

/-! ## Path-order precedence-route boundary -/

namespace PathOrderBoundary

def SchemaRecSuccPrecedenceRoute
    (rank : KO7Benchmark.SchemaTests.CandidateA.PrecSym → Nat) : Prop :=
  ∀ x y n : KO7Benchmark.SchemaTests.SKTerm,
    rank (KO7Benchmark.SchemaTests.CandidateA.rootSym
      (KO7Benchmark.SchemaTests.SKTerm.g y
        (KO7Benchmark.SchemaTests.SKTerm.f x y n))) <
      rank (KO7Benchmark.SchemaTests.CandidateA.rootSym
        (KO7Benchmark.SchemaTests.SKTerm.f x y
          (KO7Benchmark.SchemaTests.SKTerm.s n)))

/--
For the exact duplicated recursive rule, the precedence route is available
exactly when F ranks strictly above G.

Missing native semantics: the repository has no generic LPO/RPO relation for
KO7 Test 01. This certifies only the load-bearing precedence route, not full
LPO/RPO orientation or well-foundedness.
-/
theorem schema_recSucc_precedenceRoute_iff_F_gt_G
    (rank : KO7Benchmark.SchemaTests.CandidateA.PrecSym → Nat) :
    SchemaRecSuccPrecedenceRoute rank ↔
      rank KO7Benchmark.SchemaTests.CandidateA.PrecSym.g <
        rank KO7Benchmark.SchemaTests.CandidateA.PrecSym.f := by
  constructor
  · intro h
    exact KO7Benchmark.SchemaTests.PathOrderFailurePatterns.precedence_route_requires_F_gt_G
      rank KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
        KO7Benchmark.SchemaTests.SKTerm.z
        (h KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
          KO7Benchmark.SchemaTests.SKTerm.z)
  · intro h x y n
    simpa only [KO7Benchmark.SchemaTests.CandidateA.rootSym] using h

theorem candidateA_precedence_route_nonvacuous :
    SchemaRecSuccPrecedenceRoute KO7Benchmark.SchemaTests.CandidateA.precRank := by
  intro x y n
  exact KO7Benchmark.SchemaTests.CandidateA.candidateA_declares_F_over_G x y n

theorem equal_F_G_precedence_route_rejected :
    ¬ SchemaRecSuccPrecedenceRoute
      KO7Benchmark.SchemaTests.PathOrderFailurePatterns.precFGEqual := by
  intro h
  exact KO7Benchmark.SchemaTests.PathOrderFailurePatterns.precFGEqual_route_fails
    KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
      KO7Benchmark.SchemaTests.SKTerm.z
      (h KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
        KO7Benchmark.SchemaTests.SKTerm.z)

theorem G_over_F_precedence_route_rejected :
    ¬ SchemaRecSuccPrecedenceRoute
      KO7Benchmark.SchemaTests.PathOrderInadequate.precBad := by
  intro h
  exact KO7Benchmark.SchemaTests.PathOrderInadequate.precBad_route_fails
    KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
      KO7Benchmark.SchemaTests.SKTerm.z
      (h KO7Benchmark.SchemaTests.SKTerm.z KO7Benchmark.SchemaTests.SKTerm.z
        KO7Benchmark.SchemaTests.SKTerm.z)

namespace Control

def SANSRecSuccPrecedenceRoute
    (rank : KO7Benchmark.SANSTests.PathOrderSupport.PrecSym → Nat) : Prop :=
  ∀ x y n : KO7Benchmark.SANSTests.SANSTerm,
    rank (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
      (KO7Benchmark.SANSTests.SANSTerm.g
        (KO7Benchmark.SANSTests.SANSTerm.f x y n))) <
      rank (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
        (KO7Benchmark.SANSTests.SANSTerm.f x y
          (KO7Benchmark.SANSTests.SANSTerm.s n)))

theorem sans_recSucc_precedenceRoute_iff_F_gt_G
    (rank : KO7Benchmark.SANSTests.PathOrderSupport.PrecSym → Nat) :
    SANSRecSuccPrecedenceRoute rank ↔
      rank KO7Benchmark.SANSTests.PathOrderSupport.PrecSym.g <
        rank KO7Benchmark.SANSTests.PathOrderSupport.PrecSym.f := by
  constructor
  · intro h
    simpa only [KO7Benchmark.SANSTests.PathOrderSupport.rootSym] using
      h KO7Benchmark.SANSTests.SANSTerm.z KO7Benchmark.SANSTests.SANSTerm.z
        KO7Benchmark.SANSTests.SANSTerm.z
  · intro h x y n
    simpa only [KO7Benchmark.SANSTests.PathOrderSupport.rootSym] using h

theorem sans_default_precedence_route_nonvacuous :
    SANSRecSuccPrecedenceRoute KO7Benchmark.SANSTests.PathOrderSupport.precRank := by
  intro x y n
  exact KO7Benchmark.SANSTests.PathOrderSupport.declares_F_over_G x y n

end Control
end PathOrderBoundary

end KO7Benchmark.ScoringAnchors.Test01MethodBoundaries
