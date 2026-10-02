/-
  Structural-descent contract for scoring dependency-pair responses.

  Relation: the two-rule duplicating schema of SchemaKernel, its extracted
    dependency pair, and the nonduplicating SANS control.
  Closure: full contextual Step for the source termination theorem; root
    transformed-call relation for the projection contract.
  Property: a simple projection is a valid transformed-call certificate
    exactly at the third argument; the full contextual source is strongly
    normalizing by the rule-derived DPSoundness theorem; the projection is
    not a direct whole-term ranking. A generic reduction lemma records the
    two hypotheses needed to transfer well-foundedness between relations,
    with explicit controls showing that each hypothesis is necessary.
  Trust: mathlib and existing benchmark modules only; no sorry, no axiom,
    no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.PaperB.DPSoundness
import KO7Benchmark.PaperB.Demarcation
import KO7Benchmark.SANSTests.LinearWitness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.StructuralDescentContract

open KO7Benchmark.SchemaTests
open KO7Benchmark.SchemaTests.CandidateD
open KO7Benchmark.PaperB
open SKTerm

/-! ## The exact scorer contract on the duplicating schema -/

structure SimpleProjectionCertificate (i : Fin 3) : Prop where
  extractsPair : ∀ x y n : SKTerm,
    DPPair (f x y (s n)) (f x y n)
  projectionStrict : ∀ x y n : SKTerm,
    Demarcation.size (Demarcation.proj i (f x y n)) <
      Demarcation.size (Demarcation.proj i (f x y (s n)))

theorem simpleProjectionCertificate_iff_third (i : Fin 3) :
    SimpleProjectionCertificate i ↔ i.val = 2 := by
  constructor
  · intro h
    exact (Demarcation.projection_strict_iff i z z z).1
      (h.projectionStrict z z z)
  · intro hi
    refine ⟨?_, ?_⟩
    · intro x y n
      exact DPPair.succ x y n
    · intro x y n
      exact (Demarcation.projection_strict_iff i x y n).2 hi

theorem thirdProjectionCertificate :
    SimpleProjectionCertificate ⟨2, by decide⟩ :=
  (simpleProjectionCertificate_iff_third ⟨2, by decide⟩).2 rfl

theorem firstProjectionRejected :
    ¬ SimpleProjectionCertificate ⟨0, by decide⟩ := by
  rw [simpleProjectionCertificate_iff_third]
  decide

theorem secondProjectionRejected :
    ¬ SimpleProjectionCertificate ⟨1, by decide⟩ := by
  rw [simpleProjectionCertificate_iff_third]
  decide

theorem extractedPairProblemWF :
    WellFounded DPPairRev :=
  CandidateD.wf_DPPairRev

theorem sourceContextualSystemWF :
    WellFounded DPSoundness.StepRev :=
  DPSoundness.wf_StepRev

theorem acceptedSimpleProjection_iff_third (i : Fin 3) :
    (SimpleProjectionCertificate i ∧ WellFounded DPSoundness.StepRev) ↔
      i.val = 2 := by
  constructor
  · intro h
    exact (simpleProjectionCertificate_iff_third i).1 h.1
  · intro hi
    exact ⟨(simpleProjectionCertificate_iff_third i).2 hi,
      DPSoundness.wf_StepRev⟩

/-! ## Why the projection is not a direct whole-term measure -/

theorem projection_payload_independent (x y₁ y₂ n : SKTerm) :
    sDepth (f x y₁ n) = sDepth (f x y₂ n) := rfl

theorem projection_wrapper_inert (a b : SKTerm) :
    sDepth (g a b) = 0 := rfl

theorem projection_not_direct_step_rank :
    ¬ (∀ {a b : SKTerm}, Step a b → sDepth b < sDepth a) := by
  intro h
  have hbad := h (Step.root (RootStep.base (s z) z))
  simp [sDepth] at hbad

/-! ## Minimal generic relation-transfer hypotheses and necessity controls -/

theorem wf_of_edge_transport
    {α : Type} {source pair : α → α → Prop}
    (hPair : WellFounded (fun a b => pair b a))
    (hTransport : ∀ {a b : α}, source a b → pair a b) :
    WellFounded (fun a b => source b a) := by
  exact Subrelation.wf (fun {_ _} h => hTransport h) hPair

inductive LoopStep : Unit → Unit → Prop
  | loop : LoopStep () ()

def EmptyPair (_ _ : Unit) : Prop := False

theorem emptyPairWF :
    WellFounded (fun a b : Unit => EmptyPair b a) := by
  refine ⟨?_⟩
  intro a
  constructor
  intro b h
  exact False.elim h

theorem loopSourceNotWF :
    ¬ WellFounded (fun a b : Unit => LoopStep b a) := by
  intro h
  exact WellFounded.induction (C := fun _ => False) h () (fun _ ih => ih () LoopStep.loop)

theorem dropping_transport_breaks_transfer :
    WellFounded (fun a b : Unit => EmptyPair b a) ∧
      ¬ WellFounded (fun a b : Unit => LoopStep b a) :=
  ⟨emptyPairWF, loopSourceNotWF⟩

theorem loop_identity_transport :
    ∀ {a b : Unit}, LoopStep a b → LoopStep a b :=
  fun h => h

theorem dropping_pair_wf_breaks_transfer :
    (∀ {a b : Unit}, LoopStep a b → LoopStep a b) ∧
      ¬ WellFounded (fun a b : Unit => LoopStep b a) :=
  ⟨loop_identity_transport, loopSourceNotWF⟩

/-! ## Nonduplicating control -/

namespace Control

open KO7Benchmark.SANSTests
open SANSTerm

inductive DPPairS : SANSTerm → SANSTerm → Prop
  | succ (x y n : SANSTerm) :
      DPPairS (f x y (s n)) (f x y n)

def counterDepth : SANSTerm → Nat
  | .var _ => 0
  | .z => 0
  | .s t => counterDepth t + 1
  | .g _ => 0
  | .f _ _ n => counterDepth n

theorem controlPairDecreases :
    ∀ {a b : SANSTerm}, DPPairS a b → counterDepth b < counterDepth a
  | _, _, DPPairS.succ x y n => by
      simp [counterDepth]

theorem controlHasDirectLinearRank :
    ∀ {a b : SANSTerm}, Step a b →
      LinearWitness.mu b < LinearWitness.mu a :=
  LinearWitness.mu_step_decreases

theorem controlContextualSystemWF :
    WellFounded LinearWitness.StepRev :=
  LinearWitness.wf_StepRev

end Control

end KO7Benchmark.ScoringAnchors.StructuralDescentContract

