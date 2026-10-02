import Lake
open Lake DSL

package KO7Benchmark where
  moreLeanArgs := #["-Dpp.notation=true"]

@[default_target]
lean_lib KO7Benchmark where
  roots := #[`KO7Benchmark]

lean_lib KO7BenchmarkTheory where
  roots := #[`KO7BenchmarkTheory]

-- Test 07 external-battery obstructions: the two factorial direct-method
-- theorems cited by the propagation arms and their packaged adapters.
lean_lib Test07Verification where
  roots := #[`Test07Verification]

-- Payload-scaling arms: the additive obstruction as a function of the
-- duplication count k, with the k = 0 control witness.
lean_lib PayloadScaling where
  roots := #[`PayloadScaling]

lean_exe ko7_answer_key_export where
  root := `KO7Benchmark.AnswerKeyExport

require mathlib from git "https://github.com/leanprover-community/mathlib4.git" @ "632465e4b02cb70a5dfa4cfe15468e8a62c2bd85"
