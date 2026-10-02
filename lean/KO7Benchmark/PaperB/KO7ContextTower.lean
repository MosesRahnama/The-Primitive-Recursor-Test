/-
  KO7 witness tower at the contextual relation (upgrade U4 of the 2026-09-17
  Lean audit).

  Relation: the eight KO7 root rules on `Trace`.
  Closure: full one-hole context closure `StepCtx`.
  Property: the four-level tower `ko7TowerCtx` mirrors `WitnessOrder.ko7Tower`
    with every level stated at `StepCtx`. The direct whole-term level is
    refuted through the root instance (a contextual certificate restricts to a
    root certificate); the imported-whole level is the exponential
    interpretation; the transformed-call level is the dependency-pair problem
    together with the rule-derived contextual strong normalization of
    `KO7DPSoundness`; the three-kappa summary and the bottleneck instance
    follow exactly as at the root relation.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import KO7Benchmark.WitnessOrder
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.KO7ExponentialInterpretationWitness
import KO7Benchmark.PaperB.Bottleneck
import KO7Benchmark.PaperB.KO7DPSoundness

set_option autoImplicit false

namespace KO7Benchmark.PaperB.KO7ContextTower

open KO7Benchmark.WitnessOrder
open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

/-- A direct whole-term certificate at the contextual relation. -/
def DirectWholeWitnessCtx : Prop :=
  ∃ M : AdditiveTraceMeasure, ∀ {a b : Trace}, StepCtx a b → M.eval b < M.eval a

/-- The KO7 tower with every level read at `StepCtx`. -/
def ko7TowerCtx : WitnessTower
  | .directWhole => DirectWholeWitnessCtx
  | .importedWhole => WellFounded StepCtxRev
  | .transformedCall =>
      WellFounded KO7Benchmark.KO7DependencyPairs.DPPairRev ∧ WellFounded StepCtxRev
  | .externalCert => True

/-- A contextual additive certificate would restrict to a root certificate,
    which `ko7_no_directWhole_witness` excludes. -/
theorem ko7Ctx_no_directWhole_witness :
    ¬ HasWitness ko7TowerCtx WLevel.directWhole := by
  rintro ⟨M, h⟩
  exact ko7_no_directWhole_witness ⟨M, fun hs => h (StepCtx.root hs)⟩

/-- Imported-whole certificate: the exponential interpretation. -/
theorem ko7Ctx_has_importedWhole_witness :
    HasWitness ko7TowerCtx WLevel.importedWhole := by
  show WellFounded StepCtxRev
  exact KO7Benchmark.KO7ExponentialInterpretationWitness.wf_StepCtxRev_expInterp

/-- Transformed-call certificate: the dependency-pair problem is well founded
    and the full contextual system is strongly normalizing on the rule-derived
    route. -/
theorem ko7Ctx_has_transformedCall_witness :
    HasWitness ko7TowerCtx WLevel.transformedCall := by
  show WellFounded KO7Benchmark.KO7DependencyPairs.DPPairRev ∧ WellFounded StepCtxRev
  exact ⟨KO7Benchmark.KO7DependencyPairs.wf_DPPairRev,
    KO7DPSoundness.wf_StepCtxRev_rule_derived⟩

theorem ko7Ctx_has_externalCert_witness :
    HasWitness ko7TowerCtx WLevel.externalCert := by
  show True
  trivial

theorem ko7Ctx_kappaDirect_gt_directWhole :
    kappaGt ko7TowerCtx WLevel.directWhole := by
  intro j hj
  cases j with
  | directWhole => simpa [HasWitness] using ko7Ctx_no_directWhole_witness
  | importedWhole => simp [WLevel.toNat] at hj
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert => simp [WLevel.toNat] at hj

theorem ko7Ctx_kappaTruth_le_importedWhole :
    kappaLe ko7TowerCtx WLevel.importedWhole :=
  ⟨WLevel.importedWhole, by decide, ko7Ctx_has_importedWhole_witness⟩

theorem ko7Ctx_kappaContract_gt_importedWhole :
    kappaGt (contractTower ko7TowerCtx benchmarkContract) WLevel.importedWhole := by
  intro j hj
  cases j with
  | directWhole => intro h; exact h.1
  | importedWhole => intro h; exact h.1
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert => simp [WLevel.toNat] at hj

theorem ko7Ctx_kappaContract_le_transformedCall :
    kappaLe (contractTower ko7TowerCtx benchmarkContract) WLevel.transformedCall := by
  refine ⟨WLevel.transformedCall, by decide, ?_⟩
  refine ⟨?_, ko7Ctx_has_transformedCall_witness⟩
  show benchmarkContract.admissible WLevel.transformedCall
  trivial

/-- The bottleneck instance at the contextual relation. -/
theorem ko7Ctx_bottleneck_instance :
    BottleneckInstance ko7TowerCtx benchmarkContract :=
  ⟨ko7Ctx_kappaDirect_gt_directWhole,
   ko7Ctx_kappaTruth_le_importedWhole,
   ko7Ctx_kappaContract_gt_importedWhole,
   ko7Ctx_kappaContract_le_transformedCall⟩

/-- The two certificates of full contextual termination agree; the
    rule-derived one uses no interpretation. -/
theorem contextual_termination_two_routes :
    WellFounded StepCtxRev ∧ WellFounded StepCtxRev :=
  ⟨KO7Benchmark.KO7ExponentialInterpretationWitness.wf_StepCtxRev_expInterp,
   KO7DPSoundness.wf_StepCtxRev_rule_derived⟩

end KO7Benchmark.PaperB.KO7ContextTower
