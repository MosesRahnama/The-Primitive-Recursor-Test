/-
Relation: CandidateD.DPPair on the transformed schema and SchemaTests.Step on the source system.
Closure: exact extracted pair edges on the transformed side and full contextual Step on the source side.
Property: exact extraction, strict pair projection, pair WF, and a source-WF implication are separate scorer gates. The fixed-schema implication is discharged by an independent source termination theorem, so this module does not claim generic dependency-pair soundness.
Trust: kernel-only through Mathlib and named KO7Benchmark theorems; no sorry, admit, new axiom, native_decide, unsafe, partial, or opaque.
-/
import KO7Benchmark.SchemaTests.CandidateD_SoundnessBridge
import KO7Benchmark.PaperB.BoundaryWitness
import KO7Benchmark.PaperB.SemanticTransport
import KO7Benchmark.CertificateBridge
import KO7Benchmark.PaperB.DPSoundness
import KO7Benchmark.ScoringAnchors.ProjectionRoute
import KO7Benchmark.ScoringAnchors.ProcessorFamilyDecisions
import KO7Benchmark.PaperB.KO7DPSoundness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.DependencyPairSoundnessGap

open KO7Benchmark.SchemaTests
open KO7Benchmark.PaperB

def Reverse {α : Type} (R : α → α → Prop) : α → α → Prop :=
  fun a b => R b a

def ExactExtraction {α : Type}
    (Pair Extracted : α → α → Prop) : Prop :=
  ∀ {a b : α}, Pair a b ↔ Extracted a b

def SourceSoundnessTransport {α : Type}
    (Pair Source : α → α → Prop) : Prop :=
  WellFounded (Reverse Pair) → WellFounded (Reverse Source)

inductive Gate where
  | exactExtraction
  | strictProjection
  | pairWF
  | sourceTransport
deriving DecidableEq, Repr

def GateHolds {α : Type}
    (Pair Extracted Source : α → α → Prop) (rank : α → Nat) :
    Gate → Prop
  | .exactExtraction => ExactExtraction Pair Extracted
  | .strictProjection =>
      ProjectionRoute.StrictNatProjection Pair rank
  | .pairWF => WellFounded (Reverse Pair)
  | .sourceTransport => SourceSoundnessTransport Pair Source

def FullRoute {α : Type}
    (Pair Extracted Source : α → α → Prop) (rank : α → Nat) : Prop :=
  ∀ g : Gate, GateHolds Pair Extracted Source rank g

theorem full_route_receipt {α : Type}
    {Pair Extracted Source : α → α → Prop} {rank : α → Nat}
    (h : FullRoute Pair Extracted Source rank) :
    ExactExtraction Pair Extracted ∧
      ProjectionRoute.StrictNatProjection Pair rank ∧
      WellFounded (Reverse Pair) ∧
      WellFounded (Reverse Source) := by
  refine ⟨h .exactExtraction, h .strictProjection, h .pairWF, ?_⟩
  exact (h .sourceTransport) (h .pairWF)

theorem source_wf_of_full_route {α : Type}
    {Pair Extracted Source : α → α → Prop} {rank : α → Nat}
    (h : FullRoute Pair Extracted Source rank) :
    WellFounded (Reverse Source) :=
  (h .sourceTransport) (h .pairWF)

namespace PairOnlyCountermodel

abbrev Pair : Unit → Unit → Prop :=
  ProjectionRoute.TransportCountermodel.Empty

abbrev Source : Unit → Unit → Prop :=
  ProjectionRoute.TransportCountermodel.Loop

theorem pair_wf : WellFounded (Reverse Pair) := by
  simpa [Reverse, Pair] using
    ProjectionRoute.TransportCountermodel.empty_wf

theorem source_not_wf : ¬ WellFounded (Reverse Source) := by
  simpa [Reverse, Source] using
    ProjectionRoute.TransportCountermodel.loop_not_wf

theorem pair_wf_with_source_non_wf :
    WellFounded (Reverse Pair) ∧ ¬ WellFounded (Reverse Source) :=
  ⟨pair_wf, source_not_wf⟩

theorem pair_wf_alone_cannot_imply_source_wf :
    ¬ (∀ (P S : Unit → Unit → Prop),
      WellFounded (Reverse P) → WellFounded (Reverse S)) := by
  intro h
  exact source_not_wf (h Pair Source pair_wf)

end PairOnlyCountermodel

namespace Schema

open SKTerm

abbrev Pair : SKTerm → SKTerm → Prop := CandidateD.DPPair
abbrev Extracted : SKTerm → SKTerm → Prop :=
  ProjectionRoute.Schema.RuleDerivedPair
abbrev Source : SKTerm → SKTerm → Prop := Step
abbrev Rank : SKTerm → Nat := CandidateD.sDepth

theorem exact_extraction : ExactExtraction Pair Extracted := by
  intro a b
  exact ProjectionRoute.Schema.candidateD_iff_ruleDerivedPair

theorem strict_projection :
    ProjectionRoute.StrictNatProjection Pair Rank :=
  ProjectionRoute.Schema.projection_strict

theorem pair_wf : WellFounded (Reverse Pair) := by
  simpa [Reverse, Pair] using
    ProjectionRoute.Schema.pair_problem_wf_from_projection

/--
This is the explicit source-transport slot for the fixed schema.
Its current proof supplies the source conclusion from the independently proved
schema-specialized DPSoundness.wf_StepRev. The pair-WF premise is therefore not
a mechanization of the generic Arts-Giesl dependency-pair soundness theorem.
-/
theorem fixed_schema_source_implication_from_independent_wf :
    SourceSoundnessTransport Pair Source := by
  intro _pairWF
  simpa [SourceSoundnessTransport, Reverse, Source] using
    DPSoundness.wf_StepRev

theorem scorer_contract : FullRoute Pair Extracted Source Rank := by
  intro g
  cases g with
  | exactExtraction => exact exact_extraction
  | strictProjection => exact strict_projection
  | pairWF => exact pair_wf
  | sourceTransport => exact fixed_schema_source_implication_from_independent_wf

theorem full_route_source_wf : WellFounded (Reverse Source) :=
  source_wf_of_full_route scorer_contract

end Schema

namespace Legacy

open SKTerm

theorem candidateBridge_source_relation_eq_nonlinear :
    CandidateDBridge.StepRev = NonlinearWitness.StepRev := rfl

theorem nonlinear_source_relation_eq_ruleDerived :
    NonlinearWitness.StepRev = DPSoundness.StepRev := rfl

theorem candidateBridge_full_source_proof_eq_nonlinear :
    CandidateDBridge.candidateD_full_trs_wf =
      NonlinearWitness.wf_StepRev := rfl

theorem boundaryWitness_full_field_eq_candidateBridge :
    schema_dp_rule_extracted_witness.fullSystemWF =
      CandidateDBridge.candidateD_full_trs_wf := rfl

theorem boundaryWitness_full_adequacy_eq_candidateBridge :
    schema_dp_full_adequacy =
      CandidateDBridge.candidateD_full_trs_wf := rfl

theorem semanticTransport_result_eq_nonlinear
    (x : SKTerm)
    (w : SemanticTransport.schemaDPVerifier.Witness
      (SemanticTransport.schemaDPInterface.alpha x))
    (hw : SemanticTransport.schemaDPVerifier.accepts w) :
    SemanticTransport.schemaDPWitnessTransport x w hw =
      NonlinearWitness.wf_StepRev := rfl

theorem certificateBridge_root_source_proof_eq_independent :
    KO7Benchmark.CertificateBridge.ko7FastSummary_full_trs_wf =
      KO7Benchmark.Test03Ordinal.strong_normalization_closed := rfl

theorem ruleDerived_source_available :
    WellFounded DPSoundness.StepRev :=
  DPSoundness.wf_StepRev

theorem ko7_ruleDerived_source_available :
    WellFounded KO7Benchmark.KO7ContextClosure.StepCtxRev :=
  KO7DPSoundness.wf_StepCtxRev_rule_derived

end Legacy

end KO7Benchmark.ScoringAnchors.DependencyPairSoundnessGap
