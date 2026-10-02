/-
  Paper B Lean Bridge: root import.
  Architectural spec: lean-dev.md §2.3.
  Each module is uncommented as it lands and its build passes.
-/
import KO7Benchmark.PaperB.Basic
import KO7Benchmark.PaperB.BenchmarkContractWitnessOrderBridge
import KO7Benchmark.PaperB.SchemaAdditiveObstruction
import KO7Benchmark.PaperB.BoundaryWitness
import KO7Benchmark.PaperB.SchemaWitnessTower
import KO7Benchmark.PaperB.SchemaPartition
import KO7Benchmark.PaperB.Bottleneck
import KO7Benchmark.PaperB.ClaimLedger
import KO7Benchmark.PaperB.SemanticTransport
import KO7Benchmark.PaperB.PseudoWitnessMass
import KO7Benchmark.PaperB.ExhaustionGap
import KO7Benchmark.PaperB.SearchBudgetInvariance
import KO7Benchmark.PaperB.EntropyMonotone
import KO7Benchmark.PaperB.ContractCoherence
-- 2026-09-17 theory upgrades U1 to U5: paper propositions, the Section 5
-- demarcation, rule-derived dependency-pair soundness on both systems, the
-- contextual KO7 tower, and the scoring-anchor counterexamples.
import KO7Benchmark.PaperB.Demarcation
import KO7Benchmark.PaperB.CountedIteration
import KO7Benchmark.PaperB.CounterErasure
import KO7Benchmark.PaperB.PaperPolynomial
import KO7Benchmark.PaperB.RefutedClassSearch
import KO7Benchmark.PaperB.DPSoundness
import KO7Benchmark.PaperB.KO7DPSoundness
import KO7Benchmark.PaperB.KO7ContextTower
