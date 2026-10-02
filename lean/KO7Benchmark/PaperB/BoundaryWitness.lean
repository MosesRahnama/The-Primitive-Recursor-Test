/-
  Dependency-pairs route as rule-extracted boundary witness.
  Mechanizes Proposition A.8 in Rahnama_PRT_Benchmark_NeurIPS.tex.

  Architectural spec: lean-dev.md §4.3.

  Name note: CandidateD_SoundnessBridge lives under namespace
  KO7Benchmark.SchemaTests.CandidateDBridge (not CandidateD_SoundnessBridge).
-/
import KO7Benchmark.PaperB.Basic
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SchemaTests.CandidateD_SoundnessBridge
import KO7Benchmark.BenchmarkContract

namespace KO7Benchmark.PaperB

inductive BoundaryStatus where
  | ruleExtracted
  | boundaryExternal
  | mathematicallyFalse
deriving DecidableEq, Repr

inductive SchemaMethod where
  | pathOrder
  | polynomial
  | kboStyle
  | dependencyPairs
  | directMeasure
deriving DecidableEq, Repr

def schemaMethodBoundaryStatus : SchemaMethod → BoundaryStatus
  | .pathOrder       => .boundaryExternal
  | .polynomial      => .mathematicallyFalse
  | .kboStyle        => .mathematicallyFalse
  | .dependencyPairs => .ruleExtracted
  | .directMeasure   => .mathematicallyFalse

-- Answer-key reflexivity theorems
theorem schema_pathOrder_adequate_not_admissible :
    KO7Benchmark.Benchmark.answerKey .schemaB .pathOrder
      = KO7Benchmark.Benchmark.Verdict.adequateNotAdmissible := rfl

theorem schema_dependencyPairs_ok :
    KO7Benchmark.Benchmark.answerKey .schemaB .dependencyPairs
      = KO7Benchmark.Benchmark.Verdict.ok := rfl

theorem schema_polynomial_not_adequate :
    (KO7Benchmark.Benchmark.answerKey .schemaB .polynomial).adequate = false := rfl

-- Rule-extracted DP witness as a Lean object.
--
-- Four-field structure backing Proposition A.8 ("the dependency-pairs route
-- supplies an adequate termination witness"):
--   1. extractsPair          ─ the recursive rule emits the canonical DP pair
--   2. projectionDecreases   ─ third-argument projection strictly decreases
--   3. pairProblemWF         ─ the projected pair problem is well-founded
--   4. fullSystemWF          ─ this lifts to SN of the original schema TRS
--                              (CandidateDBridge.candidateD_full_trs_wf)
--
-- Field 4 is what makes the witness "adequate for the original system":
-- without it, the structure would only certify the extracted pair object.
-- With it, the manuscript attribution to "an adequate termination witness"
-- is mechanically backed.
structure RuleExtractedDPWitness where
  extractsPair : ∀ x y n : SchemaTerm,
    KO7Benchmark.SchemaTests.CandidateD.DPPair
      (.f x y (.s n))
      (.f x y n)
  projectionDecreases : ∀ x y n : SchemaTerm,
    KO7Benchmark.SchemaTests.CandidateD.sDepth (.f x y n)
      < KO7Benchmark.SchemaTests.CandidateD.sDepth (.f x y (.s n))
  pairProblemWF :
    WellFounded KO7Benchmark.SchemaTests.CandidateD.DPPairRev
  fullSystemWF :
    WellFounded KO7Benchmark.SchemaTests.NonlinearWitness.StepRev

theorem schema_dp_rule_extracted_witness : RuleExtractedDPWitness := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro x y n
    exact KO7Benchmark.SchemaTests.CandidateD.DPPair.succ x y n
  · intro x y n
    exact KO7Benchmark.SchemaTests.CandidateDBridge.candidateD_projection_decreases x y n
  · exact KO7Benchmark.SchemaTests.CandidateD.wf_DPPairRev
  · exact KO7Benchmark.SchemaTests.CandidateDBridge.candidateD_full_trs_wf

/-- The DP route supplies an adequate termination witness for the original
    duplicating-schema TRS. Unfolds the `fullSystemWF` field of the witness
    structure for direct citation by Proposition A.8 in the manuscript. -/
theorem schema_dp_full_adequacy :
    WellFounded KO7Benchmark.SchemaTests.NonlinearWitness.StepRev :=
  schema_dp_rule_extracted_witness.fullSystemWF

end KO7Benchmark.PaperB
