/-
  Exact-scope receipts for the hallucination-detection theory ledger.

  These declarations deliberately separate the formal kernel of each
  detector-facing claim from its empirical or cross-domain interpretation.
  In particular, this file does not claim that the Arts--Giesl dependency-
  pair soundness theorem is mechanized in this stack, that finite masses are
  normalized probabilities, or that synthetic benchmark records label
  open-domain hallucinations.

  Relation: mixed, as stated by each imported theorem.
  Property: exact-scope audit receipts only.
  Trust: kernel-only; baseline axioms inherited from Mathlib.
-/
import KO7Benchmark.PaperB.ContractCoherence
import KO7Benchmark.FalseFormalLegitimacy
import KO7Benchmark.PaperB.SemanticTransport
import KO7Benchmark.PaperB.PseudoWitnessMass
import KO7Benchmark.PaperB.EntropyMonotone
import KO7Benchmark.OperationalIncompleteness
import KO7Benchmark.MetaHaltWitnessBridge

set_option autoImplicit false

namespace KO7Benchmark.PaperB.HallucinationDetectionReceipts

open KO7Benchmark.Benchmark
open KO7Benchmark.SchemaTests
open KO7Benchmark.WitnessOrder
open KO7Benchmark.PaperB.SemanticTransport
open KO7Benchmark.PaperB.PseudoWitnessMass
open KO7Benchmark.PaperB.EntropyMonotone
open KO7Benchmark.OperationalIncompleteness
open KO7Benchmark.MetaHaltWitnessBridge
open KO7Benchmark.PseudoWitness

/-! ## HD-PRT-07: finite answer-key coherence -/

/-- Exact receipt for the finite answer-key lattice. This theorem says
    nothing about response-level co-mention aggregation. -/
theorem hd_prt_07_finite_answer_key_coherence :
    And
      (forall (t : Task) (m : MethodFamily),
        (answerKey t m).admissible = true -> (answerKey t m).adequate = true)
      (And
        (forall (t : Task) (m : MethodFamily),
          (answerKey t m).adequate = true -> (answerKey t m).truth = true)
        (forall (t : Task) (m : MethodFamily),
          ContractCoherence.classify (answerKey t m) ≠
            ContractCoherence.OutcomeClass.incoherent)) := by
  exact ⟨ContractCoherence.answerKey_admissible_implies_adequate,
    ContractCoherence.answerKey_adequate_implies_truth,
    ContractCoherence.answerKey_never_incoherent⟩

/-! ## HD-PRT-08: benchmark-owned false-formal-legitimacy schema -/

/-- Exact receipt for the benchmark-owned equivalence and its synthetic
    separating fixtures. No link to an external hallucination label is
    asserted by this theorem. -/
theorem hd_prt_08_synthetic_false_formal_legitimacy_receipt :
    And
      (forall E : PaperC.PRTEvaluation,
        Iff (PaperC.PRTStrongPass E)
          (And (Not (PaperC.FalseFormalLegitimacy E))
            (Or (PaperC.WellFormedConfession E.output)
              (PaperC.WellFormedTypedAbstention E.output))))
      (And (PaperC.FalseFormalLegitimacy PaperC.boundaryExternalYes)
        (Not (PaperC.FalseFormalLegitimacy PaperC.dependencyPairsPass))) := by
  exact ⟨PaperC.prtStrongPass_iff_not_false_formal_legitimacy_and_validOutput,
    PaperC.ffl_nonvacuous.1, PaperC.ffl_nonvacuous.2⟩

/-! ## HD-PRT-09 and HD-PRT-11: transport and composition gates -/

/-- A verified higher-layer witness reaches the low-layer property only
    through the supplied witness transport. -/
theorem hd_prt_09_transport_gate
    {Llo Lhi : SemanticLayer}
    {Phi : LayerInterface Llo Lhi}
    {Pabs : Lhi.State -> Prop} {Vhi : Verifier Lhi Pabs}
    {P : Llo.State -> Prop}
    (T : WitnessTransport Phi Vhi P) {x : Llo.State}
    (h : AdequateExists Vhi (Phi.alpha x)) : P x :=
  transport_delivers_property T h

/-- Consecutive property transports compose only when both edge receipts
    are supplied. This is the exact formal core of the end-to-end gate. -/
theorem hd_prt_11_two_edge_transport_receipt
    {Llo Lmid Lhi : SemanticLayer}
    {Phi : LayerInterface Llo Lmid} {Psi : LayerInterface Lmid Lhi}
    {P : Llo.State -> Prop} {Pmid : Lmid.State -> Prop}
    {PhiP : Lhi.State -> Prop}
    (tPhi : PropertyTransport Phi P Pmid)
    (tPsi : PropertyTransport Psi Pmid PhiP) :
    PropertyTransport (Phi.comp Psi) P PhiP :=
  crossLayerTransfer tPhi tPsi

/-! ## HD-PRT-10: provenance of the schema transport realization -/

/-- The live schema transport is definitionally realized by the independent
    nonlinear full-system witness. This receipt does not mechanize the
    Arts--Giesl dependency-pair soundness metatheorem. -/
theorem hd_prt_10_schema_transport_realization
    (x : SKTerm)
    (w : schemaDPVerifier.Witness (schemaDPInterface.alpha x))
    (hw : schemaDPVerifier.accepts w) :
    schemaDPWitnessTransport x w hw = NonlinearWitness.wf_StepRev :=
  rfl

/-! ## HD-PRT-12 and HD-PRT-13: finite-mass and bottleneck scope -/

/-- Exact finite-mass equivalence. Positivity is explicit; normalization and
    verifier-to-Boolean soundness are not assumptions or conclusions here. -/
theorem hd_prt_12_finite_mass_equivalence
    {iota : Type} [Fintype iota]
    (Gm : GenerationModel iota) (lo hi : WLevel)
    (hp : 0 < pseudoMass Gm lo) (hc : 0 < checkMass Gm hi) :
    BottleneckSignature Gm lo hi <-> checkMass Gm hi < pseudoMass Gm lo :=
  bottleneckSignature_iff_pseudoDomination Gm lo hi hp hc

/-- Formal part of the three-part bottleneck record: the schema interface
    record and the finite toy mass fixture. Rerun instability is empirical
    and is intentionally absent from this theorem. -/
theorem hd_prt_13_formal_bottleneck_components (x : SKTerm) :
    And
      (InterfaceBottleneck schemaDPInterface schemaDirectVerifier
        schemaDPVerifier x)
      (BottleneckSignature toyModel WLevel.directWhole WLevel.transformedCall) :=
  And.intro (schema_interface_bottleneck x) bottleneckSignature_satisfiable

/-! ## HD-PRT-21: one-way entropy direction -/

/-- Exact one-way pushforward bound. It does not infer verdict-first causal
    generation from observed entropies. -/
theorem hd_prt_21_verdict_method_entropy_bound
    (g : MethodFamily -> Bool) (p : MethodFamily -> Real)
    (hp : forall m, 0 <= p m) :
    shannonEntropy (pushforward g p) <= shannonEntropy p :=
  verdict_entropy_le_method_entropy g p hp

/-! ## HD-PRT-23: licensed forgetting at the displayed scopes -/

/-- Exact owned package: a root-rule certified-forgetting witness exists,
    and the canonical imported-whole witness has the synthetic external-
    provenance terminal license. No universal feature-dropping theorem or
    source-system dependency-pair soundness theorem is concluded. -/
theorem hd_prt_23_owned_forgetting_and_license :
    And (Nonempty CertifiedForgettingWitness)
      (PaperC.TypedOutputDiscipline WitnessLevelSystem witnessLevelSemantics
        witnessSelfAppInstance (externalWitnessDerivation muWExternal)
        terminalAccept) :=
  And.intro (PayloadOperationalIncompleteness.hasCertifiedForgetting
    ko7PayloadOperationalIncompleteness)
    muWExternal_has_typed_terminal_output

#check hd_prt_07_finite_answer_key_coherence
#check hd_prt_08_synthetic_false_formal_legitimacy_receipt
#check hd_prt_09_transport_gate
#check hd_prt_10_schema_transport_realization
#check hd_prt_11_two_edge_transport_receipt
#check hd_prt_12_finite_mass_equivalence
#check hd_prt_13_formal_bottleneck_components
#check hd_prt_21_verdict_method_entropy_bound
#check hd_prt_23_owned_forgetting_and_license

#print axioms hd_prt_07_finite_answer_key_coherence
#print axioms hd_prt_08_synthetic_false_formal_legitimacy_receipt
#print axioms hd_prt_09_transport_gate
#print axioms hd_prt_10_schema_transport_realization
#print axioms hd_prt_11_two_edge_transport_receipt
#print axioms hd_prt_12_finite_mass_equivalence
#print axioms hd_prt_13_formal_bottleneck_components
#print axioms hd_prt_21_verdict_method_entropy_bound
#print axioms hd_prt_23_owned_forgetting_and_license

end KO7Benchmark.PaperB.HallucinationDetectionReceipts
