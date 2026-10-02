/-
  Bottleneck structure and instances.
  Mechanizes Theorem A.12 and Corollary A.13 in Rahnama_PRT_Benchmark_NeurIPS.tex.

  Architectural spec: lean-dev.md §4.6.
-/
import KO7Benchmark.PaperB.SchemaWitnessTower
import KO7Benchmark.WitnessOrder

namespace KO7Benchmark.PaperB

open KO7Benchmark.WitnessOrder

-- Definition A.7: Structural representation-shift bottleneck at the κ-predicate level.
structure BottleneckInstance
    (T : WitnessTower)
    (Γ : TaskContract) : Prop where
  noDirect              : kappaGt T .directWhole
  truthAtImported       : kappaLe T .importedWhole
  contractAboveImported : kappaGt (contractTower T Γ) .importedWhole
  contractAtTransformed : kappaLe (contractTower T Γ) .transformedCall

theorem schema_bottleneck_instance :
    BottleneckInstance schemaTower benchmarkContract := by
  obtain ⟨h1, h2, h3, h4⟩ := schema_three_kappa_summary
  exact ⟨h1, h2, h3, h4⟩

theorem ko7_bottleneck_instance :
    BottleneckInstance ko7Tower benchmarkContract := by
  obtain ⟨h1, h2, h3, h4⟩ := ko7_three_kappa_summary
  exact ⟨h1, h2, h3, h4⟩

-- Corollary A.13: single-step gap κ_math = 1, κ_bdy = 2.
theorem schema_boundary_gap_skips_importedWhole :
    kappaGt (contractTower schemaTower benchmarkContract) .importedWhole ∧
    kappaLe (contractTower schemaTower benchmarkContract) .transformedCall :=
  ⟨schema_bottleneck_instance.contractAboveImported,
   schema_bottleneck_instance.contractAtTransformed⟩

theorem ko7_boundary_gap_skips_importedWhole :
    kappaGt (contractTower ko7Tower benchmarkContract) .importedWhole ∧
    kappaLe (contractTower ko7Tower benchmarkContract) .transformedCall :=
  ⟨ko7_bottleneck_instance.contractAboveImported,
   ko7_bottleneck_instance.contractAtTransformed⟩

end KO7Benchmark.PaperB
