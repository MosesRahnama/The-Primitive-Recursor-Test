/-
  Reviewer-grep claim ledger for Paper B appendix theorems.
  Every supports_app_* and supports_body_* alias maps one appendix
  claim to the theorem that backs it.

  Architectural spec: lean-dev.md §4.7.
-/
import KO7Benchmark.PaperB.SchemaAdditiveObstruction
import KO7Benchmark.PaperB.BoundaryWitness
import KO7Benchmark.PaperB.SchemaWitnessTower
import KO7Benchmark.PaperB.SchemaPartition
import KO7Benchmark.PaperB.Bottleneck

namespace KO7Benchmark.PaperB

open KO7Benchmark.WitnessOrder

/-- Supports body §3 and Appendix Lemma A.6: additive-layer duplication obstruction. -/
theorem supports_app_lemma_A6_duplication_obstruction
    (M : AdditiveSKMeasure) :
    ¬ (∀ x y n : KO7Benchmark.SchemaTests.SKTerm,
        M.eval (KO7Benchmark.SchemaTests.SKTerm.g y
          (KO7Benchmark.SchemaTests.SKTerm.f x y n))
        < M.eval (KO7Benchmark.SchemaTests.SKTerm.f x y
          (KO7Benchmark.SchemaTests.SKTerm.s n))) :=
  AdditiveSKMeasure.no_additive_orients_schema_recursive_root M

/-- Supports Appendix Proposition A.8: DP route is boundary-admissible at κ=2. -/
theorem supports_app_prop_A8_dp_admissible : RuleExtractedDPWitness :=
  schema_dp_rule_extracted_witness

/-- Supports Appendix Proposition A.10: primitive-recursion schema witness partition. -/
theorem supports_app_prop_A10_schema_partition :
    schemaMethodStatus .pathOrder       = ⟨true,  false, .boundaryExternal⟩ ∧
    schemaMethodStatus .dependencyPairs = ⟨true,  true,  .ruleExtracted⟩    ∧
    schemaMethodStatus .polynomial      = ⟨false, false, .mathematicallyFalse⟩ ∧
    schemaMethodStatus .kboStyle        = ⟨false, false, .mathematicallyFalse⟩ ∧
    schemaMethodStatus .directMeasure   = ⟨false, false, .mathematicallyFalse⟩ :=
  primitive_recursion_schema_witness_partition

/-- Supports Appendix Theorem A.12: R and KO7 satisfy the bottleneck definition. -/
theorem supports_app_theorem_A12_bottleneck :
    BottleneckInstance schemaTower benchmarkContract ∧
    BottleneckInstance ko7Tower benchmarkContract :=
  ⟨schema_bottleneck_instance, ko7_bottleneck_instance⟩

/-- Supports Appendix Corollary A.13: single-step gap κ_math=1, κ_bdy=2. -/
theorem supports_app_corollary_A13_single_step_gap :
    (kappaGt (contractTower schemaTower benchmarkContract) .importedWhole ∧
     kappaLe (contractTower schemaTower benchmarkContract) .transformedCall) ∧
    (kappaGt (contractTower ko7Tower benchmarkContract) .importedWhole ∧
     kappaLe (contractTower ko7Tower benchmarkContract) .transformedCall) :=
  ⟨schema_boundary_gap_skips_importedWhole, ko7_boundary_gap_skips_importedWhole⟩

/-- Bundle of every Paper-B-facing core theorem. Reviewers checking "is the
    appendix theory backed by Lean" can hit this single name. -/
theorem paperB_theory_core_supported :
    BottleneckInstance schemaTower benchmarkContract ∧
    BottleneckInstance ko7Tower benchmarkContract ∧
    Nonempty RuleExtractedDPWitness ∧
    (∀ M : AdditiveSKMeasure,
       ¬ (∀ x y n : KO7Benchmark.SchemaTests.SKTerm,
           M.eval (KO7Benchmark.SchemaTests.SKTerm.g y
             (KO7Benchmark.SchemaTests.SKTerm.f x y n))
           < M.eval (KO7Benchmark.SchemaTests.SKTerm.f x y
             (KO7Benchmark.SchemaTests.SKTerm.s n)))) :=
  ⟨schema_bottleneck_instance,
   ko7_bottleneck_instance,
   ⟨schema_dp_rule_extracted_witness⟩,
   AdditiveSKMeasure.no_additive_orients_schema_recursive_root⟩

end KO7Benchmark.PaperB
