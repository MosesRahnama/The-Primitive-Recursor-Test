/-
  KO7/PaperC/SovereigntyAndMetaHalt.lean

  Lean 4 statements for the benchmark-local supervisory formalization used by
  Paper C. The current file deliberately drops the older "Sovereignty
  Trichotomy" target and instead formalizes the stronger, cleaner version that
  emerged from the later discussion:

    * honest terminal verdicts factor through either structural classification
      or external provenance;
    * below-threshold internal search licenses lift / typed C3 only;
    * false certification is therefore a typed-output discipline violation,
      not a third honest deductive state.

  This is designed to be machine-checkable in Lean without a local Löb theorem
  or a full Gödel coding layer.

  Companion documents:
    - sovereignty_trichotomy_and_paperC_formalization.md
    - Leobian-Conversation.md
-/

-- Minimal imports; extend as needed when building in a full Mathlib project.
-- import Mathlib.Data.List.Basic
-- import Mathlib.Logic.Basic

namespace PaperC

/-! ## Language and obligation signatures (P1) -/

/-- Finite enumeration of witness-language structural shapes. -/
inductive LangShape where
  | directWholeTerm
  | pathOrder
  | polynomialInterp
  | matrixInterp
  | depPairProjection
  | sizeChange
  | custom (name : String)
  deriving DecidableEq, Repr

/-- Finite set of structural features a witness language declares.
    Each field is a type-level property, not a proof object. -/
structure LangSig where
  shape                 : LangShape
  monotone              : Bool
  duplicationCompatible : Bool
  linearityRequired     : Bool
  projectionSupport     : Bool
  signatureExtension    : Bool
  deriving DecidableEq, Repr

/-- Finite enumeration of obligation structural shapes. -/
inductive ObShape where
  | leftLinear
  | rightLinear
  | duplicating
  | collapsing
  | dpReduced
  | custom (name : String)
  deriving DecidableEq, Repr

/-- Finite set of structural features an obligation carries. -/
structure ObSig where
  shape              : ObShape
  hasSelfDuplication : Bool
  cycleFree          : Bool
  finiteSignature    : Bool
  deriving DecidableEq, Repr

/-- Admissibility verdict for a (language, obligation) signature pair.
    `unknown` is permitted and is the reason MetaHalt is conservative
    rather than complete. -/
inductive Adm where
  | compatible
  | blocked
  | unknown
  deriving DecidableEq, Repr

/-- The benchmark-local admissibility table, declared once by the benchmark
    author from the twelve impossibility theorems of Paper A. -/
structure AdmissibilityTable where
  table : LangSig → ObSig → Adm

/-! ## META-HALT as a typed lookup (P1) -/

/-- Meta-halt predicate: binary inadequacy judgment, computed by table lookup.
    Takes signatures, not proofs. This closes the meta-halt-for-meta-halt
    regress constructively. -/
def MetaHalt (A : AdmissibilityTable) (σL : LangSig) (σO : ObSig) : Bool :=
  match A.table σL σO with
  | Adm.blocked => true   -- inadequate
  | _           => false  -- not-yet-inadequate (compatible or unknown)

/-- **Proposition 1 (Information-Unit Theorem).**
    `MetaHalt` is total, consumes only finite structural signatures, and
    terminates on any finite admissibility table. -/
theorem MetaHalt_is_total
    (A : AdmissibilityTable) (σL : LangSig) (σO : ObSig) :
    ∃ b : Bool, MetaHalt A σL σO = b := by
  exact ⟨MetaHalt A σL σO, rfl⟩

/-- Catalog-soundness of an admissibility table
    (Paper C Principle 2, §6). A table is sound on a blocked-class predicate
    if it never returns `compatible` on a genuinely blocked pair. -/
def CatalogSound (A : AdmissibilityTable)
    (blockedClass : LangSig → ObSig → Prop) : Prop :=
  ∀ σL σO, A.table σL σO = Adm.compatible → ¬ blockedClass σL σO

/-- **Proposition 1.1.** Soundness is preserved through `MetaHalt` on the
    compatible/blocked cases. The `unknown` case is intentionally left as
    `sorry`: `MetaHalt` is *conservative*, and on unknown entries it
    returns `false` (not-yet-inadequate) without claiming the pair is safe. -/
theorem MetaHalt_sound_on_decided
    (A : AdmissibilityTable) (blockedClass : LangSig → ObSig → Prop)
    (hA : CatalogSound A blockedClass) :
    ∀ σL σO,
      A.table σL σO = Adm.compatible →
      MetaHalt A σL σO = false →
      ¬ blockedClass σL σO := by
  intro σL σO hTab _hMH
  exact hA σL σO hTab

/-! ## Cycle-observation sub-clause (P2) -/

/-- A declared loop pattern: a finite graph-pattern matcher plus a minimum
    observation count. -/
structure LoopPattern (Term : Type) where
  isMatch  : Term → Bool
  minCount : Nat

/-- Pre-declared finite family of loop patterns. -/
structure LoopPatternFamily (Term : Type) where
  patterns : List (LoopPattern Term)

/-- A search trace is a list of terms encountered during object-level search. -/
structure SearchTrace (Term : Type) where
  steps : List Term

/-- Count occurrences of a pattern in a trace. (Overlap-friendly version;
    a disjoint-occurrence counter would be a small refinement.) -/
def SearchTrace.countMatches {Term : Type}
    (τ : SearchTrace Term) (p : LoopPattern Term) : Nat :=
  (τ.steps.filter p.isMatch).length

/-- The cycle-observation clause fires "inadequate" when at least one
    declared pattern has been observed at or above its minimum count. -/
def CycleObservationMH {Term : Type}
    (Pi : LoopPatternFamily Term) (τ : SearchTrace Term) : Bool :=
  Pi.patterns.any (fun p => decide (τ.countMatches p ≥ p.minCount))

/-- **Proposition 2 (Cycle-observation soundness, conditional).**
    If every pattern in the family has been externally certified to block
    the declared target property on the patterns it matches, then any firing
    of `CycleObservationMH` witnesses a genuine block. -/
theorem CycleObservationMH_sound {Term : Type}
    (Pi : LoopPatternFamily Term)
    (blocksTarget : LoopPattern Term → Prop)
    (hCert : ∀ p, p ∈ Pi.patterns → blocksTarget p)
    (τ : SearchTrace Term) :
    CycleObservationMH Pi τ = true →
    ∃ p, p ∈ Pi.patterns ∧ τ.countMatches p ≥ p.minCount ∧ blocksTarget p := by
  intro h
  simp only [CycleObservationMH, List.any_eq_true, decide_eq_true_eq] at h
  obtain ⟨p, hMem, hCount⟩ := h
  exact ⟨p, hMem, hCount, hCert p hMem⟩

/-! ## Benchmark-local supervisory dichotomy -/

/-- Abstract deductive system with provenance-tagged rules.
    `baseRules` are internal (ℛ₀); `fullRules ⊇ baseRules` is the full rule set (ℛ). -/
structure DeductiveSystem where
  Term      : Type
  Rule      : Type
  baseRules : List Rule
  fullRules : List Rule
  derives   : List Rule → Term → Prop

/-- A derivation records its used rules and its conclusion. -/
structure Derivation (𝒟 : DeductiveSystem) where
  usedRules  : List 𝒟.Rule
  conclusion : 𝒟.Term

/-- External provenance: at least one rule used is outside the base set. -/
def Derivation.hasExternalProvenance {𝒟 : DeductiveSystem}
    (π : Derivation 𝒟) : Prop :=
  ∃ r, r ∈ π.usedRules ∧ r ∉ 𝒟.baseRules

/-- Internal-only derivation: every rule used is in the base set. -/
def Derivation.isInternal {𝒟 : DeductiveSystem}
    (π : Derivation 𝒟) : Prop :=
  ∀ r, r ∈ π.usedRules → r ∈ 𝒟.baseRules

/-- A self-application instance encodes 𝒟 applied to its own description.
    The `encodesSelf` field is a placeholder; in a full formalization it
    would be an explicit Gödel-numbering or fixed-point combinator
    construction in Term. -/
structure SelfAppInstance (𝒟 : DeductiveSystem) where
  term        : 𝒟.Term
  encodesSelf : True -- placeholder for a Gödel/fixed-point encoding

/-- Benchmark-local supervisory semantics. This replaces the earlier global
    axioms by making the halting predicate and structural-classification
    predicate explicit interface data. The typed-output theorems below are
    therefore parametric in the supervisory semantics they assume. -/
structure SupervisorySemantics (𝒟 : DeductiveSystem) where
  /-- Halting predicate on self-application instances. Left abstract here
      because the typed-output results below do not depend on a concrete
      reduction relation. -/
  halts : SelfAppInstance 𝒟 → Prop
  /-- A derivation is a structural classification of `tD` if it concludes a
      verdict on `tD` without expanding any redex whose subterm contains `tD`. -/
  isStructuralClassification : SelfAppInstance 𝒟 → Derivation 𝒟 → Prop

/-- Local abbreviation for the halting predicate supplied by the benchmark-local
    supervisory semantics. -/
def Halts
    {𝒟 : DeductiveSystem} (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟) : Prop :=
  Ssem.halts tD

/-- Local abbreviation for structural classification under a declared
    supervisory semantics. -/
def IsStructuralClassification
    {𝒟 : DeductiveSystem} (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟) (π : Derivation 𝒟) : Prop :=
  Ssem.isStructuralClassification tD π

/-- Verdict tags from the typed output schema. Only `c1` and `c2` count as
    terminal object-level verdicts. -/
inductive VerdictTag where
  | c1
  | c2
  | c3
  | c4
  deriving DecidableEq, Repr

/-- A verdict record for the supervisory contract. -/
structure Verdict where
  tag : VerdictTag
  deriving DecidableEq, Repr

/-- Terminal object-level verdicts are exactly `c1` and `c2`. -/
def EmitsTerminal (v : Verdict) : Prop :=
  v.tag = VerdictTag.c1 ∨ v.tag = VerdictTag.c2

/-- Honest terminal licenses in the benchmark-local supervisory setting. -/
def HasTerminalLicense
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) : Prop :=
  IsStructuralClassification Ssem tD π ∨ π.hasExternalProvenance

/-- Typed-output discipline for terminal verdicts: any `c1/c2` verdict must be
    backed by one of the two honest license channels. -/
def TypedOutputDiscipline
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict) : Prop :=
  EmitsTerminal v → HasTerminalLicense 𝒟 Ssem tD π

/-- Typed-output violation: a verdict-shaped output is emitted without either
    honest license channel. This is the benchmark-local replacement for the
    discarded "third honest case". -/
def TypedOutputViolation
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict) : Prop :=
  EmitsTerminal v ∧ ¬ HasTerminalLicense 𝒟 Ssem tD π

/-- Internal derivations cannot also have external provenance. -/
theorem internal_excludes_external
    {𝒟 : DeductiveSystem} {π : Derivation 𝒟}
    (hInt : π.isInternal) :
    ¬ π.hasExternalProvenance := by
  intro hExt
  rcases hExt with ⟨r, hUsed, hNotBase⟩
  exact hNotBase (hInt r hUsed)

/-- Any terminal verdict accepted under the typed discipline must factor
    through one of the two honest channels. This is the benchmark-local
    dichotomy. -/
theorem terminal_verdict_requires_license
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict)
    (hDisc : TypedOutputDiscipline 𝒟 Ssem tD π v)
    (hTerm : EmitsTerminal v) :
    HasTerminalLicense 𝒟 Ssem tD π := by
  exact hDisc hTerm

/-- Internal non-structural terminal emission is automatically a typed-output
    violation: the derivation has neither honest license channel. -/
theorem internal_nonstructural_terminal_is_violation
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict)
    (hInt : π.isInternal)
    (hNonStructural : ¬ IsStructuralClassification Ssem tD π)
    (hTerm : EmitsTerminal v) :
    TypedOutputViolation 𝒟 Ssem tD π v := by
  refine ⟨hTerm, ?_⟩
  intro hLic
  cases hLic with
  | inl hStruct =>
      exact hNonStructural hStruct
  | inr hExt =>
      exact internal_excludes_external hInt hExt

/-- Under audit, a terminal violation exhibits the negative form of the
    supervisory contract: neither structural classification nor external
    provenance is present. -/
theorem terminal_violation_characterization
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict) :
    TypedOutputViolation 𝒟 Ssem tD π v ↔
      EmitsTerminal v ∧
      ¬ IsStructuralClassification Ssem tD π ∧
      ¬ π.hasExternalProvenance := by
  constructor
  · intro h
    rcases h with ⟨hTerm, hNoLic⟩
    refine ⟨hTerm, ?_, ?_⟩
    · intro hStruct
      exact hNoLic (Or.inl hStruct)
    · intro hExt
      exact hNoLic (Or.inr hExt)
  · intro h
    rcases h with ⟨hTerm, hNoStruct, hNoExt⟩
    refine ⟨hTerm, ?_⟩
    intro hLic
    cases hLic with
    | inl hStruct => exact hNoStruct hStruct
    | inr hExt => exact hNoExt hExt

-- Corollary 1.4 (C3 safety on self-reference).
-- A C3 emission on a self-application instance is never a Lobian short-circuit.
-- This is the formal content of the brainstorm's "superposition output" intuition:
/-- C3 emissions are non-terminal by definition and therefore cannot be
    typed-output violations in the benchmark-local sense. -/
theorem c3_is_not_terminal (v : Verdict) (h : v.tag = VerdictTag.c3) :
    ¬ EmitsTerminal v := by
  intro hTerm
  rcases hTerm with hC1 | hC2
  · rw [h] at hC1
    cases hC1
  · rw [h] at hC2
    cases hC2

/-- Corollary: C3 emissions are always safe with respect to terminal verdict
    discipline on self-reference, because they do not claim a terminal verdict
    at all. -/
theorem c3_is_not_typed_output_violation
    (𝒟 : DeductiveSystem) (Ssem : SupervisorySemantics 𝒟)
    (tD : SelfAppInstance 𝒟)
    (π : Derivation 𝒟) (v : Verdict)
    (h : v.tag = VerdictTag.c3) :
    ¬ TypedOutputViolation 𝒟 Ssem tD π v := by
  intro hViol
  exact c3_is_not_terminal v h hViol.1

/-! ## Questioner-Dominance C0 (P4) -/

/-- A reasoning system carries an internal language and an expressive-capacity
    relation among languages. `capacity L₁ L₂` reads as L₁ ⪯ L₂: L₁ embeds
    faithfully into L₂ for the targeted inference operations. -/
structure ReasoningSystem where
  Lang     : Type
  capacity : Lang → Lang → Prop

/-- An instance arrives with its own generating language. -/
structure InstanceWithLang (S : ReasoningSystem) where
  instanceLang : S.Lang
  instanceTerm : S.Lang -- the instance itself, expressed in its generating language

/-- A faithful internalization witness records that the instance language can
    be embedded into some usable target language of the reasoner. -/
structure FaithfulInternalizationWitness (S : ReasoningSystem)
    (x : InstanceWithLang S) where
  targetLang : S.Lang
  embeds     : S.capacity x.instanceLang targetLang

/-- **Capacity-deficit C0.** No faithful internalization witness exists. -/
def C0_CapacityDeficit (S : ReasoningSystem) (x : InstanceWithLang S) : Prop :=
  ¬ Nonempty (FaithfulInternalizationWitness S x)

/-- An internal verdict about `x` must carry a faithful internalization
    witness; otherwise it is only about a proxy. -/
structure InternalVerdictAbout (S : ReasoningSystem)
    (x : InstanceWithLang S) where
  verdict : S.Lang
  witness : FaithfulInternalizationWitness S x

/-- **Proposition 3 (Questioner-Dominance Principle).** If S is in
    capacity-deficit C0 on x, then no faithful S-internal verdict on x exists.
    Any emitted verdict is therefore about a proxy rather than the original
    instance. -/
theorem QuestionerDominance
    (S : ReasoningSystem) (x : InstanceWithLang S)
    (h : C0_CapacityDeficit S x) :
    ¬ Nonempty (InternalVerdictAbout S x) := by
  intro hVerdict
  rcases hVerdict with ⟨v⟩
  exact h ⟨v.witness⟩

end PaperC
