/-
  Paper B Lean Bridge: witness-order lemmas layered on top of the
  benchmark answer-key core.

  These theorems are intentionally kept out of `BenchmarkContract.lean`
  so the answer-key module stays frozen and can be exported mechanically
  without depending on the theory-side witness-order workspace.
-/
import KO7Benchmark.BenchmarkContract
import KO7Benchmark.WitnessOrder

namespace KO7Benchmark.Benchmark

open KO7Benchmark.WitnessOrder

/-- The nonlinear-polynomial `test1` row is mathematically adequate at the
truth layer but remains outside the benchmark contract. -/
theorem test1_nonlinearPoly_row_backed :
    answerKey .test1 .nonlinearPoly = Verdict.adequateNotAdmissible ∧
      HasWitness ko7Tower WLevel.importedWhole ∧
      ¬ benchmarkContract.admissible WLevel.importedWhole := by
  refine ⟨rfl, ko7_has_importedWhole_witness, ?_⟩
  exact benchmarkContract_disallows_importedWhole

/-- The KO7-specialized MPO row has the same witness-order status as the
nonlinear polynomial row: truth-level adequate, benchmark-inadmissible.
Both witnesses populate the same imported-whole layer and the contract
rejects that layer uniformly. -/
theorem test1_mpo_row_backed :
    answerKey .test1 .mpoSpecialized = Verdict.adequateNotAdmissible ∧
      HasWitness ko7Tower WLevel.importedWhole ∧
      ¬ benchmarkContract.admissible WLevel.importedWhole := by
  refine ⟨rfl, ko7_has_importedWhole_witness, ?_⟩
  exact benchmarkContract_disallows_importedWhole

/-- The benchmark-local direct-measure row is refuted by the authoritative KO7
direct-witness exclusion. -/
theorem test1_directMeasure_row_refuted :
    answerKey .test1 .directMeasure = Verdict.truthOnly ∧
      ¬ HasWitness ko7Tower WLevel.directWhole := by
  exact ⟨rfl, ko7_no_directWhole_witness⟩

/-- Every benchmark row in the answer key that is `admissible = true`
    corresponds to a level at or above `transformedCall` in the
    benchmark-local witness tower. This is the formal bridge between
    the triaxial verdict algebra (`BenchmarkContract`) and the coarse
    witness-language hierarchy (`WitnessOrder`). -/
theorem admissible_row_requires_contract_witness :
    (answerKey .schemaB .dependencyPairs).admissible = true →
      HasContractWitness ko7Tower benchmarkContract := by
  intro _hadm
  exact ko7_kappaContract_has_transformedCall

/-- Conversely, the Paper C repair: a row can be `adequate = true` while
    `admissible = false` because `κ_truth ≤ importedWhole` even though
    `κ_contract = transformedCall`. The nonlinearPoly row in Test 1 is
    the canonical example. -/
theorem nonlinearPoly_row_exemplifies_repair :
    (answerKey .test1 .nonlinearPoly).truth = true ∧
      (answerKey .test1 .nonlinearPoly).admissible = false ∧
      HasWitness ko7Tower WLevel.importedWhole ∧
      ¬ benchmarkContract.admissible WLevel.importedWhole := by
  refine ⟨rfl, rfl, ko7_has_importedWhole_witness, ?_⟩
  show ¬ False
  intro h; exact h

end KO7Benchmark.Benchmark
