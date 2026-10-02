/-
  A row-specific polynomial counterexample for Schema A.

  The interpretation below is the concrete shape proposed in session
  `gpt-5.4-pro__2026-06-25T01-30-13-00019`:

    [Z]        = 0
    [S(t)]     = [t] + 1
    [G(a,b)]   = [a] + [b] + 1
    [F(a,b,c)] = [a] + [c] * ([b] + 2) + 1

  It strictly decreases on the two root rules, so a root-only check can look
  successful. It does not strictly decrease on the full context-closed `Step`
  relation: at third argument Z, the F-clause ignores the second argument, so
  reducing inside that payload position ties the interpretation.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.ContextClosurePolynomialCounterexample

open KO7Benchmark.SchemaTests
open SKTerm

def interp (sigma : Nat -> Nat) : SKTerm -> Nat
  | var n => sigma n
  | z => 0
  | s t => interp sigma t + 1
  | g a b => interp sigma a + interp sigma b + 1
  | f a b c => interp sigma a + interp sigma c * (interp sigma b + 2) + 1

@[simp] theorem interp_var (sigma : Nat -> Nat) (n : Nat) :
    interp sigma (var n) = sigma n := rfl
@[simp] theorem interp_z (sigma : Nat -> Nat) : interp sigma z = 0 := rfl
@[simp] theorem interp_s (sigma : Nat -> Nat) (t : SKTerm) :
    interp sigma (s t) = interp sigma t + 1 := rfl
@[simp] theorem interp_g (sigma : Nat -> Nat) (a b : SKTerm) :
    interp sigma (g a b) = interp sigma a + interp sigma b + 1 := rfl
@[simp] theorem interp_f (sigma : Nat -> Nat) (a b c : SKTerm) :
    interp sigma (f a b c) =
      interp sigma a + interp sigma c * (interp sigma b + 2) + 1 := rfl

/-- The polynomial passes the base root-rule check. -/
theorem root_base_decreases (sigma : Nat -> Nat) (x y : SKTerm) :
    interp sigma x < interp sigma (f x y z) := by
  simp [interp]

/-- The polynomial passes the recursive root-rule check. -/
theorem root_succ_decreases (sigma : Nat -> Nat) (x y n : SKTerm) :
    interp sigma (g y (f x y n)) < interp sigma (f x y (s n)) := by
  have hEq :
      interp sigma (f x y (s n)) =
        interp sigma (g y (f x y n)) + 1 := by
    simp [interp]
    ring
  rw [hEq]
  omega

def contextSource : SKTerm := f (var 0) (f (var 0) (var 0) z) z
def contextTarget : SKTerm := f (var 0) (var 0) z

/-- Context-closure exposes the failure: rewriting in F's second argument ties. -/
theorem context_counterexample :
    Step contextSource contextTarget
      ∧ ∀ sigma : Nat -> Nat, interp sigma contextSource = interp sigma contextTarget := by
  constructor
  · exact Step.f_arg2 (Step.root (RootStep.base (var 0) (var 0)))
  · intro sigma
    simp [contextSource, contextTarget, interp]

/-- Therefore this polynomial is not a termination witness for full `Step`. -/
theorem not_step_orienting :
    ¬ (∀ (sigma : Nat -> Nat) {t u : SKTerm},
        Step t u -> interp sigma u < interp sigma t) := by
  intro h
  have hstep : Step contextSource contextTarget := context_counterexample.1
  have hlt := h (fun _ => 0) hstep
  simp [contextSource, contextTarget, interp] at hlt

end KO7Benchmark.SchemaTests.ContextClosurePolynomialCounterexample
