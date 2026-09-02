/-
  Semantic layers, verifiers, Galois-style layer interfaces, and witness
  transport.

  Mechanizes the semantic-tower and verifier-transport layer of
  Rahnama_PRT_Benchmark.tex §3 (semantic layer, verifier, layer
  interface, witness transport, transport-delivers-the-property,
  canonical transport via the Galois unit, interface composition,
  property transport, cross-layer transfer, interface bottleneck).
  Before this module those definitions were manuscript-level; the
  benchmark stack now carries them as Lean objects, and the schema
  instance is populated by benchmark-local proofs:

    * the direct layer's witness family is the additive
      constructor-weight class; its adequate-witness set is empty at
      every instance (`schema_direct_layer_empty`, via the additive
      obstruction of `SchemaAdditiveObstruction`);
    * the transformed layer's adequate-witness set is inhabited
      (`schema_dp_layer_inhabited`, via the dependency-pair
      pair-problem well-foundedness `CandidateD.wf_DPPairRev`);
    * the transport function is inhabited
      (`schemaDPWitnessTransport`); its realization supplies the
      full-TRS strong-normalization fact through the benchmark-local
      nonlinear witness `NonlinearWitness.wf_StepRev`, matching the
      certificate-bridge realization pattern. The Arts-Giesl
      dependency-pair soundness metatheorem itself is not mechanized
      in this stack; see the docstring of `schemaDPWitnessTransport`.

  Relation: SchemaTests.Step (context-closed schema step) on the low
  layer; CandidateD.DPPair on the transformed layer.
  Property: SN stated as well-foundedness of the reversed relations.
  Trust: kernel-only; baseline axioms.
-/
import KO7Benchmark.PaperB.SchemaAdditiveObstruction
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.SemanticTransport

open KO7Benchmark.SchemaTests
open KO7Benchmark.PaperB

/-! ## Layers, verifiers, and adequate witnesses -/

/-- A semantic layer: a state space with a one-step transition relation.
    (PRT manuscript, Def. "semantic layer".) -/
structure SemanticLayer where
  State : Type
  Step : State → State → Prop

/-- A verifier for a layer and a fixed target property: a witness family
    indexed by instances, an acceptance predicate, and a soundness proof.
    (PRT manuscript, Def. "verifier".) -/
structure Verifier (L : SemanticLayer) (P : L.State → Prop) where
  Witness : L.State → Type
  accepts : ∀ {x : L.State}, Witness x → Prop
  sound   : ∀ {x : L.State} (w : Witness x), accepts w → P x

/-- The adequate-witness set at an instance is nonempty. -/
def AdequateExists {L : SemanticLayer} {P : L.State → Prop}
    (V : Verifier L P) (x : L.State) : Prop :=
  ∃ w : V.Witness x, V.accepts w

/-- Verifier soundness transfers adequacy to the property. -/
theorem adequate_implies_property {L : SemanticLayer} {P : L.State → Prop}
    (V : Verifier L P) {x : L.State} (h : AdequateExists V x) : P x := by
  obtain ⟨w, hw⟩ := h
  exact V.sound w hw

/-! ## Layer interfaces and witness transport -/

/-- A layer interface: abstraction map, concretization relation, and the
    Galois unit. (PRT manuscript, Def. "layer interface".) -/
structure LayerInterface (Llo Lhi : SemanticLayer) where
  alpha : Llo.State → Lhi.State
  gamma : Lhi.State → Llo.State → Prop
  unit  : ∀ x : Llo.State, gamma (alpha x) x

/-- The canonical abstracted property over an interface. -/
def canonicalAbstraction {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi) (P : Llo.State → Prop) :
    Lhi.State → Prop :=
  fun t => ∀ zlo : Llo.State, Φ.gamma t zlo → P zlo

/-- Canonical property transport via the Galois unit (PRT manuscript,
    Prop. "canonical transport via the Galois unit"). -/
theorem canonical_property_transport {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi) (P : Llo.State → Prop) (x : Llo.State)
    (h : canonicalAbstraction Φ P (Φ.alpha x)) : P x :=
  h x (Φ.unit x)

/-- A witness transport: adequate higher-layer witnesses for the
    abstracted property yield the low-layer property at every instance.
    (PRT manuscript, Def. "witness transport".) -/
def WitnessTransport {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi)
    {Pabs : Lhi.State → Prop} (Vhi : Verifier Lhi Pabs)
    (P : Llo.State → Prop) : Prop :=
  ∀ x : Llo.State, ∀ w : Vhi.Witness (Φ.alpha x), Vhi.accepts w → P x

/-- Transport delivers the property (PRT manuscript, Thm. "transport
    delivers the property"). -/
theorem transport_delivers_property {Llo Lhi : SemanticLayer}
    {Φ : LayerInterface Llo Lhi}
    {Pabs : Lhi.State → Prop} {Vhi : Verifier Lhi Pabs}
    {P : Llo.State → Prop}
    (T : WitnessTransport Φ Vhi P) {x : Llo.State}
    (h : AdequateExists Vhi (Φ.alpha x)) : P x := by
  obtain ⟨w, hw⟩ := h
  exact T x w hw

/-- Every layer interface admits a witness transport for the canonical
    abstracted property. -/
theorem canonicalTransport {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi)
    {P : Llo.State → Prop}
    (Vhi : Verifier Lhi (canonicalAbstraction Φ P)) :
    WitnessTransport Φ Vhi P :=
  fun x w hw => canonical_property_transport Φ P x (Vhi.sound w hw)

/-! ## Interface composition and cross-layer transfer -/

/-- Composition of layer interfaces. The Galois unit is preserved
    (PRT manuscript, Prop. "composition is well-defined"). -/
def LayerInterface.comp {Llo Lmid Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lmid) (Ψ : LayerInterface Lmid Lhi) :
    LayerInterface Llo Lhi where
  alpha := fun x => Ψ.alpha (Φ.alpha x)
  gamma := fun u z => ∃ m : Lmid.State, Ψ.gamma u m ∧ Φ.gamma m z
  unit  := fun x => ⟨Φ.alpha x, Ψ.unit (Φ.alpha x), Φ.unit x⟩

/-- A property transport along an interface (PRT manuscript,
    Def. "property transport"). -/
def PropertyTransport {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi)
    (P : Llo.State → Prop) (Pabs : Lhi.State → Prop) : Prop :=
  ∀ y : Llo.State, Pabs (Φ.alpha y) → P y

/-- Cross-layer transfer (PRT manuscript, Thm. "cross-layer transfer"):
    consecutive property transports compose along composed interfaces. -/
theorem crossLayerTransfer {Llo Lmid Lhi : SemanticLayer}
    {Φ : LayerInterface Llo Lmid} {Ψ : LayerInterface Lmid Lhi}
    {P : Llo.State → Prop} {Pmid : Lmid.State → Prop}
    {Phi : Lhi.State → Prop}
    (tΦ : PropertyTransport Φ P Pmid)
    (tΨ : PropertyTransport Ψ Pmid Phi) :
    PropertyTransport (Φ.comp Ψ) P Phi :=
  fun x h => tΦ x (tΨ (Φ.alpha x) h)

/-! ## Interface bottleneck -/

/-- Interface bottleneck (PRT manuscript, Def. "interface bottleneck"):
    the property holds, the low layer's adequate-witness set is empty,
    the high layer's is inhabited at the abstraction image, and a
    witness transport exists. -/
structure InterfaceBottleneck {Llo Lhi : SemanticLayer}
    (Φ : LayerInterface Llo Lhi)
    {P : Llo.State → Prop} (Vlo : Verifier Llo P)
    {Pabs : Lhi.State → Prop} (Vhi : Verifier Lhi Pabs)
    (x : Llo.State) : Prop where
  property_holds        : P x
  lo_adequate_empty     : ¬ AdequateExists Vlo x
  hi_adequate_inhabited : AdequateExists Vhi (Φ.alpha x)
  transport             : WitnessTransport Φ Vhi P

/-- An interface bottleneck delivers the property (PRT manuscript,
    Thm. "interface bottleneck delivers the property"), directly. -/
theorem interfaceBottleneck_delivers {Llo Lhi : SemanticLayer}
    {Φ : LayerInterface Llo Lhi}
    {P : Llo.State → Prop} {Vlo : Verifier Llo P}
    {Pabs : Lhi.State → Prop} {Vhi : Verifier Lhi Pabs}
    {x : Llo.State}
    (B : InterfaceBottleneck Φ Vlo Vhi x) : P x :=
  B.property_holds

/-- The same delivery through the transport and the high-layer adequate
    witness, exercising the transport clause. -/
theorem interfaceBottleneck_delivers_via_transport {Llo Lhi : SemanticLayer}
    {Φ : LayerInterface Llo Lhi}
    {P : Llo.State → Prop} {Vlo : Verifier Llo P}
    {Pabs : Lhi.State → Prop} {Vhi : Verifier Lhi Pabs}
    {x : Llo.State}
    (B : InterfaceBottleneck Φ Vlo Vhi x) : P x :=
  transport_delivers_property B.transport B.hi_adequate_inhabited

/-! ## Schema instantiation, populated benchmark-locally -/

/-- Low layer: schema terms under the context-closed step relation. -/
def schemaLayer : SemanticLayer := ⟨SKTerm, Step⟩

/-- Transformed layer: schema terms under the extracted dependency-pair
    relation (marked terms are identified with terms). -/
def dpLayer : SemanticLayer := ⟨SKTerm, fun a b => CandidateD.DPPair b a⟩

/-- Target property on the low layer: strong normalization of the schema
    TRS, stated as well-foundedness of the reversed context-closed step. -/
def SchemaTermination : SKTerm → Prop :=
  fun _ => WellFounded NonlinearWitness.StepRev

/-- Abstracted property on the transformed layer: well-foundedness of
    the reversed extracted dependency-pair relation. -/
def DPTermination : SKTerm → Prop :=
  fun _ => WellFounded CandidateD.DPPairRev

/-- An orienting additive measure yields strong normalization: the
    reversed step relation embeds into the inverse image of `<` on `ℕ`. -/
theorem wf_of_orienting_additive (M : AdditiveSKMeasure)
    (h : ∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a) :
    WellFounded NonlinearWitness.StepRev := by
  have hsub : Subrelation NonlinearWitness.StepRev
      (InvImage (· < ·) M.eval) := by
    intro a b hab
    exact h hab
  exact Subrelation.wf hsub (InvImage.wf M.eval Nat.lt_wfRel.wf)

/-- Direct-layer verifier: a witness is an orienting additive
    constructor-weight measure; soundness maps it to termination. The
    witness family is the additive class only, matching the
    benchmark-local scope of `schemaTower`'s directWhole layer. -/
def schemaDirectVerifier : Verifier schemaLayer SchemaTermination where
  Witness := fun _ =>
    {M : AdditiveSKMeasure //
      ∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a}
  accepts := fun _ => True
  sound := fun w _ => wf_of_orienting_additive w.1 w.2

/-- Transformed-layer verifier: a witness is a proof object of the
    pair-problem well-foundedness. -/
def schemaDPVerifier : Verifier dpLayer DPTermination where
  Witness := fun _ => PLift (WellFounded CandidateD.DPPairRev)
  accepts := fun _ => True
  sound := fun w _ => w.down

/-- The marked-term interface: identity abstraction with equality
    concretization. -/
def schemaDPInterface : LayerInterface schemaLayer dpLayer where
  alpha := id
  gamma := fun t zt => t = zt
  unit := fun _ => rfl

/-- The direct layer's adequate-witness set is empty at every instance:
    no additive constructor-weight measure orients the schema step.
    Benchmark-local mechanized clause of the interface bottleneck. -/
theorem schema_direct_layer_empty (x : SKTerm) :
    ¬ AdequateExists schemaDirectVerifier x := by
  rintro ⟨⟨M, hM⟩, -⟩
  exact AdditiveSKMeasure.no_additive_orients_schema_step M hM

/-- The transformed layer's adequate-witness set is inhabited at every
    abstraction image. -/
theorem schema_dp_layer_inhabited (x : SKTerm) :
    AdequateExists schemaDPVerifier (schemaDPInterface.alpha x) :=
  ⟨PLift.up CandidateD.wf_DPPairRev, trivial⟩

/-- Benchmark-local witness transport for the schema instance.

    Proves: the transport function type of the manuscript definition is
    inhabited for the schema instance.
    Does not prove: the Arts-Giesl dependency-pair soundness
    metatheorem. The realization supplies the full-TRS
    strong-normalization fact through the benchmark-local nonlinear
    witness `NonlinearWitness.wf_StepRev`, matching the realization
    pattern of `CertificateBridge`.
    Relation: Step (context-closed) target; DPPair source.
    Trust: kernel-only. -/
theorem schemaDPWitnessTransport :
    WitnessTransport schemaDPInterface schemaDPVerifier SchemaTermination :=
  fun _ _ _ => NonlinearWitness.wf_StepRev

/-- The schema instance satisfies the full interface-bottleneck record
    at every instance: the property holds, the direct layer is
    adequately empty, the transformed layer is adequately inhabited,
    and a transport exists. Non-vacuity witness for
    `InterfaceBottleneck` (release-gate R5). -/
theorem schema_interface_bottleneck (x : SKTerm) :
    InterfaceBottleneck schemaDPInterface schemaDirectVerifier
      schemaDPVerifier x where
  property_holds := NonlinearWitness.wf_StepRev
  lo_adequate_empty := schema_direct_layer_empty x
  hi_adequate_inhabited := schema_dp_layer_inhabited x
  transport := schemaDPWitnessTransport

end KO7Benchmark.PaperB.SemanticTransport
