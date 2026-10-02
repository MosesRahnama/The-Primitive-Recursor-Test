/-
  Paper B Lean Bridge: shared abbreviations and namespace.
  Architectural spec: lean-dev.md §4.1.
  This file introduces no theorem content; it sets up names used
  by every other PaperB module.
-/
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SchemaTests.CandidateA_PathOrderSupport
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SchemaTests.CandidateD_SoundnessBridge
import KO7Benchmark.WitnessOrder
import KO7Benchmark.BenchmarkContract

namespace KO7Benchmark.PaperB

abbrev SchemaTerm     := KO7Benchmark.SchemaTests.SKTerm
abbrev SchemaRootStep := KO7Benchmark.SchemaTests.RootStep
abbrev SchemaStep     := KO7Benchmark.SchemaTests.Step
abbrev SchemaStepRev  := KO7Benchmark.SchemaTests.NonlinearWitness.StepRev
abbrev WLevel         := KO7Benchmark.WitnessOrder.WLevel
abbrev WitnessTower   := KO7Benchmark.WitnessOrder.WitnessTower

end KO7Benchmark.PaperB
