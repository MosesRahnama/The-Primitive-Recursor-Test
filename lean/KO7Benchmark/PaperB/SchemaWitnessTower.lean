/-
  Schema instance of WitnessTower.
  Mechanizes the three-kappa summary for the primitive duplicating schema,
  parallel to ko7_three_kappa_summary in WitnessOrder.lean.

  Name note: WitnessOrder does not define kappaGt_of_no_witness /
  kappaLe_of_witness / contract_kappaGt_importedWhole /
  contract_kappaLe_transformedCall. Each clause is proved inline here
  using the same pattern as the ko7_kappa* theorems.

  Architectural spec: lean-dev.md §4.4.
-/
import KO7Benchmark.PaperB.SchemaAdditiveObstruction
import KO7Benchmark.PaperB.BoundaryWitness
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.WitnessOrder

namespace KO7Benchmark.PaperB

open KO7Benchmark.WitnessOrder
open KO7Benchmark.SchemaTests

/-! ## Schema witness tower

The directWhole layer in this local tower is **the additive
constructor-weight class only**. Broader W0 fragments (affine,
polynomial, max-plus, tracked-matrix, projection) are excluded by
the orientation-boundary paper [rahnama2025orientation] and are
not reproved locally. The bridge here is therefore:

  • `schema_no_directWhole_witness` :: no additive witness at W0
  • `schema_has_importedWhole_witness` :: a W1 witness exists
       (instantiated by the nonlinear witness `wf_StepRev`; the
       LPO realization is cited from the literature, not formalized
       here)
  • `schema_has_transformedCall_witness` :: a W2 witness exists
       (the dependency-pair pair problem is well-founded)

The manuscript text and lean attributions are scoped accordingly. -/

def SchemaDirectWholeWitness : Prop :=
  ∃ M : AdditiveSKMeasure,
    ∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a

def schemaTower : WitnessTower
  | .directWhole     => SchemaDirectWholeWitness
  | .importedWhole   => WellFounded NonlinearWitness.StepRev
  | .transformedCall => WellFounded CandidateD.DPPairRev
  | .externalCert    => True

/-! ## Witness theorems for the schema tower -/

/-- No additive constructor-weight measure orients the duplicating
    schema rule. This is the only W0 fragment proved locally; the
    broader W0 barrier (affine, polynomial, max-plus, tracked-matrix,
    projection) is inherited from [rahnama2025orientation]. -/
theorem schema_no_directWhole_witness :
    ¬ HasWitness schemaTower WLevel.directWhole := by
  rintro ⟨M, h⟩
  exact AdditiveSKMeasure.no_additive_orients_schema_step M h

/-- An imported-whole (W1) witness exists for the schema. Realized
    locally by the nonlinear polynomial witness `wf_StepRev`, which
    lies at W1 because its global comparison structure is supplied
    rather than rule-extracted. The LPO realization referenced in
    the literature [dershowitz1982orderings] is a different W1
    instance and is not separately formalized in this bridge. -/
theorem schema_has_importedWhole_witness :
    HasWitness schemaTower WLevel.importedWhole := by
  show WellFounded NonlinearWitness.StepRev
  exact NonlinearWitness.wf_StepRev

/-- A transformed-call (W2) witness exists for the schema. The
    dependency-pair pair problem is well-founded under the third-
    argument projection. -/
theorem schema_has_transformedCall_witness :
    HasWitness schemaTower WLevel.transformedCall := by
  show WellFounded CandidateD.DPPairRev
  exact CandidateD.wf_DPPairRev

/-! ## Three-kappa summary, proved inline (no helper aliases in WitnessOrder) -/

theorem schema_kappaDirect_gt_directWhole :
    kappaGt schemaTower WLevel.directWhole := by
  intro j hj
  cases j with
  | directWhole =>
      simpa [HasWitness] using schema_no_directWhole_witness
  | importedWhole  => simp [WLevel.toNat] at hj
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert   => simp [WLevel.toNat] at hj

theorem schema_kappaTruth_le_importedWhole :
    kappaLe schemaTower WLevel.importedWhole :=
  ⟨WLevel.importedWhole, by decide, schema_has_importedWhole_witness⟩

theorem schema_kappaContract_gt_importedWhole :
    kappaGt (contractTower schemaTower benchmarkContract) WLevel.importedWhole := by
  intro j hj
  cases j with
  | directWhole =>
      intro h
      exact h.1
  | importedWhole =>
      intro h
      exact h.1
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert    => simp [WLevel.toNat] at hj

theorem schema_kappaContract_le_transformedCall :
    kappaLe (contractTower schemaTower benchmarkContract) WLevel.transformedCall := by
  refine ⟨WLevel.transformedCall, by decide, ?_⟩
  refine ⟨?_, schema_has_transformedCall_witness⟩
  show benchmarkContract.admissible WLevel.transformedCall
  trivial

theorem schema_three_kappa_summary :
    kappaGt schemaTower WLevel.directWhole ∧
    kappaLe schemaTower WLevel.importedWhole ∧
    kappaGt (contractTower schemaTower benchmarkContract) WLevel.importedWhole ∧
    kappaLe (contractTower schemaTower benchmarkContract) WLevel.transformedCall :=
  ⟨schema_kappaDirect_gt_directWhole,
   schema_kappaTruth_le_importedWhole,
   schema_kappaContract_gt_importedWhole,
   schema_kappaContract_le_transformedCall⟩

end KO7Benchmark.PaperB
