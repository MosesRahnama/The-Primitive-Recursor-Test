import KO7Benchmark.PseudoWitness
import KO7Benchmark.SovereigntyAndMetaHalt

/-!
  Benchmark-local bridge between pseudo-witness externality and the
  Paper-C META-HALT / typed-output discipline layer.

  This file lives in `KO7Benchmark` because the typed-output discipline,
  benchmark admissibility contract, and paper-facing pseudo-witness
  classification are all benchmark-local concepts. It consumes the
  witness-order and pseudo-witness layers and is fully self-contained
  inside this Lean stack.
-/

namespace KO7Benchmark.MetaHaltWitnessBridge

open KO7Benchmark.PseudoWitness
open KO7Benchmark.WitnessOrder
open PaperC

/-- Benchmark-local deductive system on witness-language levels.
    The base rule set is exactly the set of levels admissible under the
    benchmark contract. Imported-whole witnesses therefore appear as
    external provenance in the typed-output calculus. -/
def WitnessLevelSystem : DeductiveSystem where
  Term := WLevel
  Rule := WLevel
  baseRules := [WLevel.transformedCall, WLevel.externalCert]
  fullRules := [WLevel.directWhole, WLevel.importedWhole, WLevel.transformedCall, WLevel.externalCert]
  derives := fun Γ ℓ => ℓ ∈ Γ

/-- Dummy self-application instance for the benchmark-local witness-level
    discipline. The typed-output bridge only uses the license side of the
    calculus, not the concrete self-encoding. -/
def witnessSelfAppInstance : SelfAppInstance WitnessLevelSystem where
  term := WLevel.directWhole
  encodesSelf := trivial

/-- Benchmark-local supervisory semantics for the witness-level bridge.
    The bridge only needs the external-provenance branch of the typed-output
    calculus, so structural classification is taken to be absent here. -/
def witnessLevelSemantics : SupervisorySemantics WitnessLevelSystem where
  halts := fun _ => True
  isStructuralClassification := fun _ _ => False

/-- A benchmark-local derivation that cites exactly the witness-language level
    used by an adequate-but-inadmissible witness. -/
def externalWitnessDerivation (ew : ExternalWitness) : Derivation WitnessLevelSystem where
  usedRules := [ew.level]
  conclusion := ew.level

/-- Canonical terminal verdict tag used for the typed-output bridge. -/
def terminalAccept : PaperC.Verdict := ⟨VerdictTag.c1⟩

theorem terminalAccept_emits_terminal :
    EmitsTerminal terminalAccept := by
  left
  rfl

theorem importedWhole_not_in_baseRules :
    WLevel.importedWhole ∉ WitnessLevelSystem.baseRules := by
  simp [WitnessLevelSystem]

/-- Any imported-whole external witness is formally an external-provenance
    derivation in the Paper-C typed-output calculus. -/
theorem externalWitness_has_external_provenance
    (ew : ExternalWitness)
    (hLevel : ew.level = WLevel.importedWhole) :
    (externalWitnessDerivation ew).hasExternalProvenance := by
  refine ⟨ew.level, ?_, ?_⟩
  · simp [externalWitnessDerivation]
  · simp [WitnessLevelSystem, hLevel]

/-- Imported-whole external witnesses cannot be typed as benchmark-internal
    derivations, because the benchmark base rule set excludes that level. -/
theorem externalWitness_not_internal
    (ew : ExternalWitness)
    (hLevel : ew.level = WLevel.importedWhole) :
    ¬ (externalWitnessDerivation ew).isInternal := by
  intro hInt
  have hBase : ew.level ∈ WitnessLevelSystem.baseRules := by
    exact hInt ew.level (by simp [externalWitnessDerivation])
  simp [WitnessLevelSystem, hLevel] at hBase

/-- Therefore, any honest terminal verdict emitted for an imported-whole
    external witness must travel through the external-provenance branch of
    the typed-output discipline. -/
theorem externalWitness_requires_external_provenance_license
    (ew : ExternalWitness)
    (hLevel : ew.level = WLevel.importedWhole) :
    HasTerminalLicense WitnessLevelSystem witnessLevelSemantics witnessSelfAppInstance
      (externalWitnessDerivation ew) := by
  exact Or.inr (externalWitness_has_external_provenance ew hLevel)

/-- The typed-output discipline is satisfied for the canonical imported-whole
    witness exactly because it is externally tagged, not because it can be
    misreported as an internal direct proof. -/
theorem muWExternal_has_typed_terminal_output :
    TypedOutputDiscipline WitnessLevelSystem witnessLevelSemantics witnessSelfAppInstance
      (externalWitnessDerivation muWExternal) terminalAccept := by
  intro _hTerm
  exact externalWitness_requires_external_provenance_license muWExternal rfl

/-- The canonical imported-whole witness cannot be honestly presented as a
    benchmark-internal terminal derivation. -/
theorem muWExternal_cannot_be_internal :
    ¬ (externalWitnessDerivation muWExternal).isInternal := by
  exact externalWitness_not_internal muWExternal rfl

end KO7Benchmark.MetaHaltWitnessBridge
