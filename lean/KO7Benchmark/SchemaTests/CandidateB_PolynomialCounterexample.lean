/-
  Candidate (B): Polynomial interpretation over N.

    [F(x,y,n)] = x + n + 1
    [S(n)]     = n + 1
    [G(a,b)]   = b
    [Z]        = 0

  Status: FAILS on the context-closed TRS.

  The interpretation orients both root rules, but [G(a,b)] = b is not
  monotone in its first argument. A reduction inside G's left argument
  is invisible to the measure.

  Counterexample:
    G(F(S(Z), Z, Z), Z)  →  G(S(Z), Z)    (by base rule in G-left context)
    interpB(source) = 0 = interpB(target)   (no strict decrease)
-/
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.CandidateB

open KO7Benchmark.SchemaTests
open SKTerm

def interpB (σ : Nat → Nat) : SKTerm → Nat
  | var n => σ n
  | z => 0
  | s t => interpB σ t + 1
  | g _ b => interpB σ b
  | f x _ n => interpB σ x + interpB σ n + 1

@[simp] theorem interpB_var (σ : Nat → Nat) (n : Nat) : interpB σ (var n) = σ n := rfl
@[simp] theorem interpB_z (σ : Nat → Nat) : interpB σ z = 0 := rfl
@[simp] theorem interpB_s (σ : Nat → Nat) (t : SKTerm) : interpB σ (s t) = interpB σ t + 1 := rfl
@[simp] theorem interpB_g (σ : Nat → Nat) (a b : SKTerm) : interpB σ (g a b) = interpB σ b := rfl
@[simp] theorem interpB_f (σ : Nat → Nat) (x y n : SKTerm) :
    interpB σ (f x y n) = interpB σ x + interpB σ n + 1 := rfl

/-- The interpretation does orient the base root rule. -/
theorem interpB_root_base_decreases (σ : Nat → Nat) (x y : SKTerm) :
    interpB σ x < interpB σ (f x y z) := by
  simp [interpB]

/-- The interpretation does orient the recursive root rule. -/
theorem interpB_root_succ_decreases (σ : Nat → Nat) (x y n : SKTerm) :
    interpB σ (g y (f x y n)) < interpB σ (f x y (s n)) := by
  simp [interpB]

/-- But it fails under context closure: reducing inside G's left argument
    produces equal values because [G(a,b)] = b ignores a. -/
theorem interpB_context_counterexample :
    Step (g (f (s z) z z) z) (g (s z) z) ∧
      ∀ σ : Nat → Nat, interpB σ (g (f (s z) z z) z) = interpB σ (g (s z) z) := by
  constructor
  · exact Step.g_left (Step.root (RootStep.base (s z) z))
  · intro σ
    simp [interpB]

/-- Therefore the interpretation does not orient the full context-closed TRS. -/
theorem interpB_not_step_orienting :
    ¬ (∀ (σ : Nat → Nat) {t u : SKTerm}, Step t u → interpB σ u < interpB σ t) := by
  intro h
  have hstep : Step (g (f (s z) z z) z) (g (s z) z) :=
    Step.g_left (Step.root (RootStep.base (s z) z))
  have hlt := h (fun _ => 0) hstep
  simp [interpB] at hlt

end KO7Benchmark.SchemaTests.CandidateB

