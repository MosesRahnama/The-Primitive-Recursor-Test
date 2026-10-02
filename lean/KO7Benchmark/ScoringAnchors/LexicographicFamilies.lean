/-
Relation: KO7Kernel.Step and KO7ContextClosure.StepCtx on the Test01 Trace system.
Closure: root-only for exact root failures and successes; full contextual closure only where StepCtx is named.
Property: exact observed lexicographic tuples are split into family failures, root-only working members, and a contextual non-vacuity control.
Trust: Mathlib and existing KO7Benchmark modules only; no sorry, admit, new axiom, native_decide, unsafe, partial, or opaque.
-/
import Mathlib.Data.Prod.Lex
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.KO7ExponentialInterpretationWitness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.LexicographicFamilies

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

abbrev Lex2Order : (Nat × Nat) → (Nat × Nat) → Prop :=
  Prod.Lex (· < ·) (· < ·)

abbrev Lex3Order :
    (Nat × (Nat × Nat)) → (Nat × (Nat × Nat)) → Prop :=
  Prod.Lex (· < ·) Lex2Order

abbrev Lex4Order :
    (Nat × (Nat × (Nat × Nat))) →
      (Nat × (Nat × (Nat × Nat))) → Prop :=
  Prod.Lex (· < ·) Lex3Order

abbrev Lex5Order :
    (Nat × (Nat × (Nat × (Nat × Nat)))) →
      (Nat × (Nat × (Nat × (Nat × Nat)))) → Prop :=
  Prod.Lex (· < ·) Lex4Order

theorem wf_Lex2Order : WellFounded Lex2Order :=
  WellFounded.prod_lex Nat.lt_wfRel.wf Nat.lt_wfRel.wf

theorem wf_Lex3Order : WellFounded Lex3Order :=
  WellFounded.prod_lex Nat.lt_wfRel.wf wf_Lex2Order

theorem wf_Lex4Order : WellFounded Lex4Order :=
  WellFounded.prod_lex Nat.lt_wfRel.wf wf_Lex3Order

theorem wf_Lex5Order : WellFounded Lex5Order :=
  WellFounded.prod_lex Nat.lt_wfRel.wf wf_Lex4Order

/-- A root orientation by a lexicographic pair whose first coordinate is Nat
and whose remaining coordinates are represented by an arbitrary tail type. -/
def StrictRootLex {β : Type} (tailRel : β → β → Prop)
    (head : Trace → Nat) (tail : Trace → β) : Prop :=
  ∀ {a b : Trace}, Step a b →
    Prod.Lex (· < ·) tailRel (head b, tail b) (head a, tail a)

/-- The corresponding full-context orientation. -/
def StrictContextLex {β : Type} (tailRel : β → β → Prop)
    (head : Trace → Nat) (tail : Trace → β) : Prop :=
  ∀ {a b : Trace}, StepCtx a b →
    Prod.Lex (· < ·) tailRel (head b, tail b) (head a, tail a)

def StrictRootLex2 (m₁ m₂ : Trace → Nat) : Prop :=
  StrictRootLex (· < ·) m₁ m₂

def StrictContextLex2 (m₁ m₂ : Trace → Nat) : Prop :=
  StrictContextLex (· < ·) m₁ m₂

def StrictRootLex3 (m₁ m₂ m₃ : Trace → Nat) : Prop :=
  StrictRootLex Lex2Order m₁ (fun t => (m₂ t, m₃ t))

def StrictContextLex3 (m₁ m₂ m₃ : Trace → Nat) : Prop :=
  StrictContextLex Lex2Order m₁ (fun t => (m₂ t, m₃ t))

def StrictRootLex4 (m₁ m₂ m₃ m₄ : Trace → Nat) : Prop :=
  StrictRootLex Lex3Order m₁ (fun t => (m₂ t, (m₃ t, m₄ t)))

def StrictContextLex4 (m₁ m₂ m₃ m₄ : Trace → Nat) : Prop :=
  StrictContextLex Lex3Order m₁ (fun t => (m₂ t, (m₃ t, m₄ t)))

def StrictRootLex5 (m₁ m₂ m₃ m₄ m₅ : Trace → Nat) : Prop :=
  StrictRootLex Lex4Order m₁
    (fun t => (m₂ t, (m₃ t, (m₄ t, m₅ t))))

def StrictContextLex5 (m₁ m₂ m₃ m₄ m₅ : Trace → Nat) : Prop :=
  StrictContextLex Lex4Order m₁
    (fun t => (m₂ t, (m₃ t, (m₄ t, m₅ t))))

/-- A failure already witnessed by a root rule also blocks the contextual
closure, independently of the tail relation and tail coordinates. -/
theorem root_failure_blocks_context {β : Type}
    (tailRel : β → β → Prop) (head : Trace → Nat) (tail : Trace → β)
    (h : ¬ StrictRootLex tailRel head tail) :
    ¬ StrictContextLex tailRel head tail := by
  intro hc
  apply h
  intro a b hs
  exact hc (StepCtx.root hs)

/-- If an exact root step increases the first coordinate, no later
lexicographic coordinate can repair that step. -/
theorem first_coordinate_increase_blocks_root {β : Type}
    (tailRel : β → β → Prop) (head : Trace → Nat) (tail : Trace → β)
    {a b : Trace} (hs : Step a b) (hinc : head a < head b) :
    ¬ StrictRootLex tailRel head tail := by
  intro h
  have hlex := h hs
  rcases Prod.lex_def.mp hlex with hlt | ⟨heq, _⟩
  · omega
  · omega

/-! ## Observed whole-term coordinates -/

@[simp] def nodeSize : Trace → Nat
  | .void => 1
  | .delta t => nodeSize t + 1
  | .integrate t => nodeSize t + 1
  | .merge a b => nodeSize a + nodeSize b + 1
  | .app a b => nodeSize a + nodeSize b + 1
  | .recDelta b s n => nodeSize b + nodeSize s + nodeSize n + 1
  | .eqW a b => nodeSize a + nodeSize b + 1

/-- The explicit "number of non-void constructors" version used in one
observed triple. -/
@[simp] def nonVoidSize : Trace → Nat
  | .void => 0
  | .delta t => nonVoidSize t + 1
  | .integrate t => nonVoidSize t + 1
  | .merge a b => nonVoidSize a + nonVoidSize b + 1
  | .app a b => nonVoidSize a + nonVoidSize b + 1
  | .recDelta b s n => nonVoidSize b + nonVoidSize s + nonVoidSize n + 1
  | .eqW a b => nonVoidSize a + nonVoidSize b + 1

@[simp] def eqWCount : Trace → Nat
  | .void => 0
  | .delta t => eqWCount t
  | .integrate t => eqWCount t
  | .merge a b => eqWCount a + eqWCount b
  | .app a b => eqWCount a + eqWCount b
  | .recDelta b s n => eqWCount b + eqWCount s + eqWCount n
  | .eqW a b => eqWCount a + eqWCount b + 1

@[simp] def deltaCount : Trace → Nat
  | .void => 0
  | .delta t => deltaCount t + 1
  | .integrate t => deltaCount t
  | .merge a b => deltaCount a + deltaCount b
  | .app a b => deltaCount a + deltaCount b
  | .recDelta b s n => deltaCount b + deltaCount s + deltaCount n
  | .eqW a b => deltaCount a + deltaCount b

@[simp] def mergeCount : Trace → Nat
  | .void => 0
  | .delta t => mergeCount t
  | .integrate t => mergeCount t
  | .merge a b => mergeCount a + mergeCount b + 1
  | .app a b => mergeCount a + mergeCount b
  | .recDelta b s n => mergeCount b + mergeCount s + mergeCount n
  | .eqW a b => mergeCount a + mergeCount b

@[simp] def integrateCount : Trace → Nat
  | .void => 0
  | .delta t => integrateCount t
  | .integrate t => integrateCount t + 1
  | .merge a b => integrateCount a + integrateCount b
  | .app a b => integrateCount a + integrateCount b
  | .recDelta b s n => integrateCount b + integrateCount s + integrateCount n
  | .eqW a b => integrateCount a + integrateCount b

@[simp] def recDeltaCount : Trace → Nat
  | .void => 0
  | .delta t => recDeltaCount t
  | .integrate t => recDeltaCount t
  | .merge a b => recDeltaCount a + recDeltaCount b
  | .app a b => recDeltaCount a + recDeltaCount b
  | .recDelta b s n => recDeltaCount b + recDeltaCount s + recDeltaCount n + 1
  | .eqW a b => recDeltaCount a + recDeltaCount b

/-- Leading delta depth of one counter term. -/
@[simp] def leadingDeltaDepth : Trace → Nat
  | .delta t => leadingDeltaDepth t + 1
  | _ => 0

/-- Sum of the leading delta depths of every recDelta counter occurring in a
whole term. This is the concrete coordinate proposed in a repeated Test01
lexicographic triple. -/
@[simp] def recCounterDepthSum : Trace → Nat
  | .void => 0
  | .delta t => recCounterDepthSum t
  | .integrate t => recCounterDepthSum t
  | .merge a b => recCounterDepthSum a + recCounterDepthSum b
  | .app a b => recCounterDepthSum a + recCounterDepthSum b
  | .recDelta b s n =>
      recCounterDepthSum b + recCounterDepthSum s +
        recCounterDepthSum n + leadingDeltaDepth n
  | .eqW a b => recCounterDepthSum a + recCounterDepthSum b

/-- Maximum leading delta depth among all recDelta counters in a whole term. -/
@[simp] def recCounterDepthMax : Trace → Nat
  | .void => 0
  | .delta t => recCounterDepthMax t
  | .integrate t => recCounterDepthMax t
  | .merge a b => max (recCounterDepthMax a) (recCounterDepthMax b)
  | .app a b => max (recCounterDepthMax a) (recCounterDepthMax b)
  | .recDelta b s n =>
      max (leadingDeltaDepth n)
        (max (recCounterDepthMax b)
          (max (recCounterDepthMax s) (recCounterDepthMax n)))
  | .eqW a b => max (recCounterDepthMax a) (recCounterDepthMax b)

theorem observed_coordinates_nonconstant :
    eqWCount void = 0 ∧ eqWCount (eqW void void) = 1 ∧
    deltaCount void = 0 ∧ deltaCount (delta void) = 1 ∧
    recCounterDepthSum void = 0 ∧
      recCounterDepthSum (recDelta void void (delta void)) = 1 ∧
    recCounterDepthMax void = 0 ∧
      recCounterDepthMax (recDelta void void (delta void)) = 1 := by
  decide

/-! ## First-coordinate duplication barriers -/

/-- The copied payload makes total eqW count grow on an exact recursive root
step. The result is independent of every later lexicographic coordinate. -/
theorem eqWCount_first_blocks_any_tail {β : Type}
    (tailRel : β → β → Prop) (tail : Trace → β) :
    ¬ StrictRootLex tailRel eqWCount tail := by
  apply first_coordinate_increase_blocks_root tailRel eqWCount tail
    (Step.R_rec_succ void (eqW void void) void)
  decide

/-- With an eqW-free payload the same first coordinate ties rather than grows.
This isolates payload duplication as the blocker used above. -/
theorem eqWCount_payload_control :
    eqWCount (recDelta void void (delta void)) =
      eqWCount (app void (recDelta void void void)) := by
  rfl

theorem eqW_size_not_root_orienting :
    ¬ StrictRootLex2 eqWCount nodeSize :=
  eqWCount_first_blocks_any_tail (· < ·) nodeSize

theorem eqW_size_not_context_orienting :
    ¬ StrictContextLex2 eqWCount nodeSize :=
  root_failure_blocks_context (· < ·) eqWCount nodeSize
    eqW_size_not_root_orienting

theorem eqW_recCounterDepthSum_size_not_root_orienting :
    ¬ StrictRootLex3 eqWCount recCounterDepthSum nonVoidSize :=
  eqWCount_first_blocks_any_tail Lex2Order
    (fun t => (recCounterDepthSum t, nonVoidSize t))

theorem eqW_recCounterDepthSum_size_not_context_orienting :
    ¬ StrictContextLex3 eqWCount recCounterDepthSum nonVoidSize :=
  root_failure_blocks_context Lex2Order eqWCount
    (fun t => (recCounterDepthSum t, nonVoidSize t))
    eqW_recCounterDepthSum_size_not_root_orienting

theorem eqW_delta_size_not_root_orienting :
    ¬ StrictRootLex3 eqWCount deltaCount nodeSize :=
  eqWCount_first_blocks_any_tail Lex2Order
    (fun t => (deltaCount t, nodeSize t))

theorem eqW_delta_size_not_context_orienting :
    ¬ StrictContextLex3 eqWCount deltaCount nodeSize :=
  root_failure_blocks_context Lex2Order eqWCount
    (fun t => (deltaCount t, nodeSize t))
    eqW_delta_size_not_root_orienting

/-- Exact observed four-coordinate count tuple
(eqW count, delta count, recDelta count, size). -/
theorem constructor_count_4tuple_not_root_orienting :
    ¬ StrictRootLex4 eqWCount deltaCount recDeltaCount nodeSize :=
  eqWCount_first_blocks_any_tail Lex3Order
    (fun t => (deltaCount t, (recDeltaCount t, nodeSize t)))

theorem constructor_count_4tuple_not_context_orienting :
    ¬ StrictContextLex4 eqWCount deltaCount recDeltaCount nodeSize :=
  root_failure_blocks_context Lex3Order eqWCount
    (fun t => (deltaCount t, (recDeltaCount t, nodeSize t)))
    constructor_count_4tuple_not_root_orienting

/-- Exact observed five-coordinate constructor count tuple
(eqW, merge, integrate, recDelta, delta). -/
theorem constructor_count_5tuple_not_root_orienting :
    ¬ StrictRootLex5 eqWCount mergeCount integrateCount recDeltaCount deltaCount :=
  eqWCount_first_blocks_any_tail Lex4Order
    (fun t =>
      (mergeCount t, (integrateCount t, (recDeltaCount t, deltaCount t))))

theorem constructor_count_5tuple_not_context_orienting :
    ¬ StrictContextLex5 eqWCount mergeCount integrateCount recDeltaCount deltaCount :=
  root_failure_blocks_context Lex4Order eqWCount
    (fun t =>
      (mergeCount t, (integrateCount t, (recDeltaCount t, deltaCount t))))
    constructor_count_5tuple_not_root_orienting

/-- Global delta count can itself be inflated by the copied payload, so placing
it first does not rescue a lexicographic tuple. -/
theorem deltaCount_first_blocks_any_tail {β : Type}
    (tailRel : β → β → Prop) (tail : Trace → β) :
    ¬ StrictRootLex tailRel deltaCount tail := by
  apply first_coordinate_increase_blocks_root tailRel deltaCount tail
    (Step.R_rec_succ void (delta (delta void)) void)
  decide

theorem delta_eqW_size_not_root_orienting :
    ¬ StrictRootLex3 deltaCount eqWCount nodeSize :=
  deltaCount_first_blocks_any_tail Lex2Order
    (fun t => (eqWCount t, nodeSize t))

theorem delta_eqW_size_not_context_orienting :
    ¬ StrictContextLex3 deltaCount eqWCount nodeSize :=
  root_failure_blocks_context Lex2Order deltaCount
    (fun t => (eqWCount t, nodeSize t))
    delta_eqW_size_not_root_orienting

/-- The summed recDelta-counter-depth coordinate also grows when the payload
contains a deeper recDelta and is copied. -/
theorem recCounterDepthSum_first_blocks_any_tail {β : Type}
    (tailRel : β → β → Prop) (tail : Trace → β) :
    ¬ StrictRootLex tailRel recCounterDepthSum tail := by
  let payload := recDelta void void (delta (delta void))
  apply first_coordinate_increase_blocks_root tailRel recCounterDepthSum tail
    (Step.R_rec_succ void payload void)
  decide

theorem recCounterDepthSum_size_not_root_orienting :
    ¬ StrictRootLex2 recCounterDepthSum nonVoidSize :=
  recCounterDepthSum_first_blocks_any_tail (· < ·) nonVoidSize

theorem recCounterDepthSum_size_not_context_orienting :
    ¬ StrictContextLex2 recCounterDepthSum nonVoidSize :=
  root_failure_blocks_context (· < ·) recCounterDepthSum nonVoidSize
    recCounterDepthSum_size_not_root_orienting

/-! ## Maximum counter depth plus size -/

/-- For the observed maximum-counter-depth pair, the primary coordinate can
tie on rec_succ while ordinary size grows because the payload is copied. -/
theorem recCounterDepthMax_nodeSize_not_root_orienting :
    ¬ StrictRootLex2 recCounterDepthMax nodeSize := by
  intro h
  let payload := recDelta void void (delta void)
  have hlex := h (Step.R_rec_succ void payload void)
  rcases Prod.lex_def.mp hlex with hfirst | ⟨_, hsecond⟩
  · simp [payload, recCounterDepthMax, leadingDeltaDepth] at hfirst
  · simp [payload, nodeSize] at hsecond

theorem recCounterDepthMax_nodeSize_not_context_orienting :
    ¬ StrictContextLex2 recCounterDepthMax nodeSize :=
  root_failure_blocks_context (· < ·) recCounterDepthMax nodeSize
    recCounterDepthMax_nodeSize_not_root_orienting

/-! ## Root-redex position first: an exact root-only success -/

/-- Whether the root position is reducible by at least one Test01 root rule. -/
@[simp] def isRootRedex : Trace → Bool
  | .integrate (.delta _) => true
  | .merge .void _ => true
  | .merge _ .void => true
  | .merge a b => decide (a = b)
  | .recDelta _ _ .void => true
  | .recDelta _ _ (.delta _) => true
  | .eqW _ _ => true
  | _ => false

/-- There is one root position, so the observed root-redex count is a 0/1
coordinate. It does not count overlapping rules separately. -/
def rootRedexPositionCount (t : Trace) : Nat :=
  if isRootRedex t = true then 1 else 0

theorem rootRedexPositionCount_zero_or_one (t : Trace) :
    rootRedexPositionCount t = 0 ∨ rootRedexPositionCount t = 1 := by
  unfold rootRedexPositionCount
  split
  · exact Or.inr rfl
  · exact Or.inl rfl

@[simp] theorem rootRedex_merge_void_left (t : Trace) :
    rootRedexPositionCount (merge void t) = 1 := by
  cases t <;> simp [rootRedexPositionCount, isRootRedex]

@[simp] theorem rootRedex_merge_void_right (t : Trace) :
    rootRedexPositionCount (merge t void) = 1 := by
  cases t <;> simp [rootRedexPositionCount, isRootRedex]

@[simp] theorem rootRedex_merge_cancel (t : Trace) :
    rootRedexPositionCount (merge t t) = 1 := by
  cases t <;> simp [rootRedexPositionCount, isRootRedex]

@[simp] theorem rootRedex_rec_zero (b s : Trace) :
    rootRedexPositionCount (recDelta b s void) = 1 := by
  rfl

@[simp] theorem rootRedex_rec_succ (b s n : Trace) :
    rootRedexPositionCount (recDelta b s (delta n)) = 1 := by
  rfl

@[simp] theorem rootRedex_eqW (a b : Trace) :
    rootRedexPositionCount (eqW a b) = 1 := by
  rfl

@[simp] theorem rootRedex_int_delta (t : Trace) :
    rootRedexPositionCount (integrate (delta t)) = 1 := by
  rfl

@[simp] theorem rootRedex_app (a b : Trace) :
    rootRedexPositionCount (app a b) = 0 := by
  rfl

@[simp] theorem rootRedex_eq_diff_target (a b : Trace) :
    rootRedexPositionCount (integrate (merge a b)) = 0 := by
  rfl

/-- Exact additive secondary coordinate from the observed root-only response:
recDelta receives offset two, all other non-void constructors offset one. -/
@[simp] def rootResponseMu : Trace → Nat
  | .void => 0
  | .delta t => rootResponseMu t + 1
  | .integrate t => rootResponseMu t + 1
  | .merge a b => rootResponseMu a + rootResponseMu b + 1
  | .app a b => rootResponseMu a + rootResponseMu b + 1
  | .recDelta b s n =>
      rootResponseMu b + rootResponseMu s + rootResponseMu n + 2
  | .eqW a b => rootResponseMu a + rootResponseMu b + 1

theorem rootResponseMu_nonconstant :
    rootResponseMu void = 0 ∧ rootResponseMu (delta void) = 1 := by
  decide

private theorem lex_rootFlag_source_one
    (secondary : Trace → Nat) (source target : Trace)
    (hs : rootRedexPositionCount source = 1)
    (hsecondary : secondary target < secondary source) :
    Prod.Lex (· < ·) (· < ·)
      (rootRedexPositionCount target, secondary target)
      (rootRedexPositionCount source, secondary source) := by
  rcases rootRedexPositionCount_zero_or_one target with ht | ht
  · apply Prod.Lex.left
    omega
  · rw [ht, hs]
    exact Prod.Lex.right _ hsecondary

theorem nodeSize_pos (t : Trace) : 0 < nodeSize t := by
  induction t <;> simp_all [nodeSize]

private theorem rootRedex_rootResponseMu_orients_root_raw :
    ∀ {a b : Trace}, Step a b →
      Prod.Lex (· < ·) (· < ·)
        (rootRedexPositionCount b, rootResponseMu b)
        (rootRedexPositionCount a, rootResponseMu a)
  | _, _, Step.R_int_delta t =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_int_delta t) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_merge_void_left t =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_merge_void_left t) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_merge_void_right t =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_merge_void_right t) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_merge_cancel t =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_merge_cancel t) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_rec_zero b s =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_rec_zero b s) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_rec_succ b s n =>
      Prod.Lex.left _ _ (by simp)
  | _, _, Step.R_eq_refl a =>
      lex_rootFlag_source_one rootResponseMu _ _
        (rootRedex_eqW a a) (by
          simp only [rootResponseMu]
          omega)
  | _, _, Step.R_eq_diff a b =>
      Prod.Lex.left _ _ (by simp)

/-- The exact root-redex-position and response-mu pair strictly orients every
one of the eight root rules. -/
theorem rootRedex_rootResponseMu_orients_root :
    StrictRootLex2 rootRedexPositionCount rootResponseMu :=
  rootRedex_rootResponseMu_orients_root_raw

private theorem rootRedex_nodeSize_orients_root_raw :
    ∀ {a b : Trace}, Step a b →
      Prod.Lex (· < ·) (· < ·)
        (rootRedexPositionCount b, nodeSize b)
        (rootRedexPositionCount a, nodeSize a)
  | _, _, Step.R_int_delta t =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_int_delta t) (by
          simp only [nodeSize]
          omega)
  | _, _, Step.R_merge_void_left t =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_merge_void_left t) (by
          simp only [nodeSize]
          omega)
  | _, _, Step.R_merge_void_right t =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_merge_void_right t) (by
          simp only [nodeSize]
          omega)
  | _, _, Step.R_merge_cancel t =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_merge_cancel t) (by
          simp only [nodeSize]
          omega)
  | _, _, Step.R_rec_zero b s =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_rec_zero b s) (by
          simp only [nodeSize]
          omega)
  | _, _, Step.R_rec_succ b s n =>
      Prod.Lex.left _ _ (by simp)
  | _, _, Step.R_eq_refl a =>
      lex_rootFlag_source_one nodeSize _ _
        (rootRedex_eqW a a) (by
          have hp := nodeSize_pos a
          simp only [nodeSize]
          omega)
  | _, _, Step.R_eq_diff a b =>
      Prod.Lex.left _ _ (by simp)

/-- The same root-redex-position idea also works with ordinary node size at
the root relation. -/
theorem rootRedex_nodeSize_orients_root :
    StrictRootLex2 rootRedexPositionCount nodeSize :=
  rootRedex_nodeSize_orients_root_raw

def RootStepRev : Trace → Trace → Prop := fun a b => Step b a

theorem rootRedex_rootResponseMu_root_wf :
    WellFounded RootStepRev := by
  have hsub :
      Subrelation RootStepRev
        (InvImage Lex2Order
          (fun t => (rootRedexPositionCount t, rootResponseMu t))) := by
    intro a b hab
    exact rootRedex_rootResponseMu_orients_root hab
  exact Subrelation.wf hsub
    (InvImage.wf
      (fun t => (rootRedexPositionCount t, rootResponseMu t))
      wf_Lex2Order)

/-- Context closure defeats the root-position pair: under an outer app both
root-position counts are zero while rec_succ duplicates a nonempty payload and
raises the observed secondary coordinate. -/
theorem rootRedex_rootResponseMu_not_contextual :
    ¬ StrictContextLex2 rootRedexPositionCount rootResponseMu := by
  intro h
  have hs :
      StepCtx
        (app void (recDelta void (delta void) (delta void)))
        (app void (app (delta void) (recDelta void (delta void) void))) :=
    StepCtx.appRight
      (StepCtx.root (Step.R_rec_succ void (delta void) void))
  have hlex := h hs
  rcases Prod.lex_def.mp hlex with hfirst | ⟨_, hsecond⟩
  · simp at hfirst
  · simp [rootResponseMu] at hsecond

theorem rootRedex_nodeSize_not_contextual :
    ¬ StrictContextLex2 rootRedexPositionCount nodeSize := by
  intro h
  have hs :
      StepCtx
        (app void (recDelta void (delta void) (delta void)))
        (app void (app (delta void) (recDelta void (delta void) void))) :=
    StepCtx.appRight
      (StepCtx.root (Step.R_rec_succ void (delta void) void))
  have hlex := h hs
  rcases Prod.lex_def.mp hlex with hfirst | ⟨_, hsecond⟩
  · simp at hfirst
  · simp [nodeSize] at hsecond

/-! ## Contextual non-vacuity: lexicographic measures are not ruled out -/

/-- A working contextual measure can be used as the first coordinate of a
lexicographic tuple with any tail relation and any tail function. This is the
necessity control against overgeneralizing the failures above. -/
theorem exponential_first_orients_context_with_any_tail {β : Type}
    (tailRel : β → β → Prop) (tail : Trace → β) :
    StrictContextLex tailRel
      KO7Benchmark.KO7ExponentialInterpretationWitness.expInterp tail := by
  intro a b hs
  apply Prod.Lex.left
  exact
    KO7Benchmark.KO7ExponentialInterpretationWitness.expInterp_stepCtx_decreases hs

theorem contextual_lex_pair_inhabited :
    StrictContextLex2
      KO7Benchmark.KO7ExponentialInterpretationWitness.expInterp nodeSize :=
  exponential_first_orients_context_with_any_tail (· < ·) nodeSize

end KO7Benchmark.ScoringAnchors.LexicographicFamilies
