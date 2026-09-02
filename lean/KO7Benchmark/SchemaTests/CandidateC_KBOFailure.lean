/-
  Candidate (C): KBO with uniform symbol weights w = 1.

  Status: FAILS.

  Two independent failure witnesses:
  1. Variable-condition obstruction: variable y appears once on LHS,
     twice on RHS of the recursive rule.
  2. Concrete uniform-weight ground counterexample: the RHS is heavier.
-/
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.CandidateC

open KO7Benchmark.SchemaTests
open SKTerm

/-- Count occurrences of a given variable in a term. -/
def countVar (v : Nat) : SKTerm → Nat
  | var w => if v = w then 1 else 0
  | z => 0
  | s t => countVar v t
  | g a b => countVar v a + countVar v b
  | f x y n => countVar v x + countVar v y + countVar v n

/-- LHS of the recursive rule: F(x, y, S(n)) with vars x=0, y=1, n=2. -/
def succLhs : SKTerm := f (var 0) (var 1) (s (var 2))
/-- RHS of the recursive rule: G(y, F(x, y, n)). -/
def succRhs : SKTerm := g (var 1) (f (var 0) (var 1) (var 2))

@[simp] theorem countVar_succLhs_y : countVar 1 succLhs = 1 := by
  simp [succLhs, countVar]

@[simp] theorem countVar_succRhs_y : countVar 1 succRhs = 2 := by
  simp [succRhs, countVar]

/-- Any ordering respecting the KBO variable condition cannot orient the
    recursive rule, because y occurs more often on the RHS. -/
structure RespectsVariableCondition (gt : SKTerm → SKTerm → Prop) : Prop where
  count_mono : ∀ {s t : SKTerm} {v : Nat}, gt s t → countVar v t ≤ countVar v s

theorem no_variable_condition_orientation :
    ¬ ∃ gt : SKTerm → SKTerm → Prop,
        RespectsVariableCondition gt ∧ gt succLhs succRhs := by
  intro h
  rcases h with ⟨gt, hvc, horient⟩
  have hmono := hvc.count_mono (v := 1) horient
  simp at hmono

/-- Uniform weight function: every symbol gets weight 1. -/
def weight1 : SKTerm → Nat
  | var _ => 1
  | z => 1
  | s t => weight1 t + 1
  | g a b => weight1 a + weight1 b + 1
  | f x y n => weight1 x + weight1 y + weight1 n + 1

def groundLhs : SKTerm := f z z (s z)
def groundRhs : SKTerm := g z (f z z z)

@[simp] theorem weight1_groundLhs : weight1 groundLhs = 5 := by
  simp [groundLhs, weight1]

@[simp] theorem weight1_groundRhs : weight1 groundRhs = 6 := by
  simp [groundRhs, weight1]

/-- Ground counterexample: the RHS is strictly heavier than the LHS
    under uniform weights. -/
theorem uniform_weight_ground_counterexample :
    weight1 groundLhs < weight1 groundRhs := by
  simp [weight1, groundLhs, groundRhs]

end KO7Benchmark.SchemaTests.CandidateC

