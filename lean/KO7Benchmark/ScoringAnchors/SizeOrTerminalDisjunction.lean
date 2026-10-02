/-
  Refutation of the size-or-terminal termination shortcut.

  Relation: KO7ContextClosure.StepCtx on KO7Kernel.Trace, and
    SchemaTests.Step on SKTerm.
  Closure: full one-hole contextual closure in both refutations. The root-only
    KO7Kernel.Step relation is kept separate by an explicit boundary control.
  Property: the recursive rule increases structural size by exactly the size
    of the copied argument, while its wrapped recursive call can still reduce.
    Hence "size decreases or the reduct is terminal" is false.
  Trust: mathlib and existing KO7Benchmark modules only; ordinary kernel
    checking, with no extra assumptions or native evaluation.

  Provenance: this benchmark-local scoring anchor specializes the duplication
  obstruction developed in the Orientation Boundary programme. The master
  package contains size-increase results, but not this size-or-terminal
  contextual disjunction.
-/
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7ContextClosure
import KO7Benchmark.SchemaTests.SchemaKernel

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.SizeOrTerminalDisjunction

/-- A one-step relation satisfies the size-or-terminal shortcut when every
    step either strictly lowers size or lands at an R-normal term. -/
def SizeOrTerminal {α : Type*} (R : α → α → Prop) (size : α → Nat) : Prop :=
  ∀ a b, R a b → size b < size a ∨ (∀ c, ¬ R b c)

namespace KO7

open KO7Benchmark.KO7Kernel
open KO7Benchmark.KO7ContextClosure
open Trace

/-- Structural size on the KO7 trace syntax, one unit per constructor. -/
def size : Trace → Nat
  | void => 1
  | delta t => size t + 1
  | integrate t => size t + 1
  | merge a b => size a + size b + 1
  | app a b => size a + size b + 1
  | recDelta b s n => size b + size s + size n + 1
  | eqW a b => size a + size b + 1

@[simp] theorem size_void : size void = 1 := rfl
@[simp] theorem size_delta (t : Trace) : size (delta t) = size t + 1 := rfl
@[simp] theorem size_integrate (t : Trace) : size (integrate t) = size t + 1 := rfl
@[simp] theorem size_merge (a b : Trace) : size (merge a b) = size a + size b + 1 := rfl
@[simp] theorem size_app (a b : Trace) : size (app a b) = size a + size b + 1 := rfl
@[simp] theorem size_recDelta (b s n : Trace) :
    size (recDelta b s n) = size b + size s + size n + 1 := rfl
@[simp] theorem size_eqW (a b : Trace) : size (eqW a b) = size a + size b + 1 := rfl

theorem size_pos (t : Trace) : 0 < size t := by
  induction t with
  | void => simp only [size_void]; omega
  | delta t ih => simp only [size_delta]; omega
  | integrate t ih => simp only [size_integrate]; omega
  | merge a b iha ihb => simp only [size_merge]; omega
  | app a b iha ihb => simp only [size_app]; omega
  | recDelta b s n ihb ihs ihn => simp only [size_recDelta]; omega
  | eqW a b iha ihb => simp only [size_eqW]; omega

/--
Proves: the KO7 recursive successor rule raises structural size by exactly the
size of the duplicated step argument.
Does not prove: anything about termination by this size.
Relation: KO7Kernel.Step for the root rule shape.
Closure: root rule equation only.
Strategy: full.
Trust: kernel checked from the local structural definition and Nat arithmetic.
Scope: all b, s, and n.
-/
theorem rec_succ_size_gap (b s n : Trace) :
    size (app s (recDelta b s n)) =
      size (recDelta b s (delta n)) + size s := by
  simp only [size_app, size_recDelta, size_delta]
  omega

theorem rec_succ_size_increases (b s n : Trace) :
    size (recDelta b s (delta n)) < size (app s (recDelta b s n)) := by
  have hgap := rec_succ_size_gap b s n
  have hpos := size_pos s
  omega

/--
Proves: whenever the recursive call on the right side can take a KO7 root
step, the whole right side can take the corresponding contextual step.
Does not prove: a root step from the outer app.
Relation: KO7ContextClosure.StepCtx.
Closure: full one-hole contextual closure.
Strategy: full.
Trust: kernel checked from StepCtx.appRight and StepCtx.root.
Scope: every root successor of the recursive call.
-/
theorem rec_succ_rhs_continues {b s n r : Trace}
    (h : Step (recDelta b s n) r) :
    StepCtx (app s (recDelta b s n)) (app s r) :=
  StepCtx.appRight (StepCtx.root h)

/-- Closed ground computation used by the counterexample: sizes 5 and 6. -/
theorem ground_sizes :
    size (recDelta void void (delta void)) = 5 ∧
      size (app void (recDelta void void void)) = 6 := by
  constructor <;> rfl

/-- The two contextual steps in the ground counterexample. -/
theorem ground_steps :
    StepCtx (recDelta void void (delta void))
        (app void (recDelta void void void)) ∧
      StepCtx (app void (recDelta void void void)) (app void void) := by
  constructor
  · exact StepCtx.root (Step.R_rec_succ void void void)
  · exact rec_succ_rhs_continues (Step.R_rec_zero void void)

/--
Boundary control: the same wrapped reduct is normal only for the deliberately
root-only KO7Kernel.Step. This prevents the contextual refutation from being
mis-cited as a root-relation theorem.
-/
theorem ground_rhs_root_normal :
    ∀ c, ¬ Step (app void (recDelta void void void)) c := by
  intro c h
  cases h


/--
Proves: the literal size-or-terminal predicate holds for the root-only KO7
kernel relation. The two size-increasing rules land at root-normal wrappers.
Does not prove: the corresponding claim for contextual rewriting.
Relation: KO7Kernel.Step.
Closure: root-only.
Strategy: full eight-rule case split.
Trust: kernel checked from constructor disjointness and Nat arithmetic.
Scope: the structural size defined in this namespace.
-/
theorem sizeOrTerminal_root_holds :
    SizeOrTerminal Step size := by
  intro a b h
  cases h with
  | R_int_delta t =>
      left
      have ht := size_pos t
      simp only [size_integrate, size_delta, size_void]
      omega
  | R_merge_void_left t =>
      left
      simp only [size_merge, size_void]
      omega
  | R_merge_void_right t =>
      left
      simp only [size_merge, size_void]
      omega
  | R_merge_cancel =>
      left
      simp only [size_merge]
      omega
  | R_rec_zero b s =>
      left
      have hs := size_pos s
      simp only [size_recDelta, size_void]
      omega
  | R_rec_succ b s n =>
      right
      intro c hc
      cases hc
  | R_eq_refl a =>
      left
      have ha := size_pos a
      simp only [size_eqW, size_void]
      omega
  | R_eq_diff a b =>
      right
      intro c hc
      cases hc

/--
Proves: the size-or-terminal disjunction is false for the full contextual KO7
relation.
Does not prove: failure for the root-only KO7Kernel.Step.
Relation: KO7ContextClosure.StepCtx.
Closure: full one-hole contextual closure.
Strategy: full.
Trust: kernel checked by one ground two-step witness.
Scope: the structural size defined in this namespace.
-/
theorem sizeOrTerminal_false :
    ¬ SizeOrTerminal StepCtx size := by
  intro h
  rcases ground_steps with ⟨hfirst, hsecond⟩
  rcases h _ _ hfirst with hdecrease | hterminal
  · rcases ground_sizes with ⟨hleft, hright⟩
    rw [hleft, hright] at hdecrease
    omega
  · exact hterminal (app void void) hsecond

end KO7

namespace SchemaA

open KO7Benchmark.SchemaTests
open SKTerm

/-- Structural size on the Schema A syntax, one unit per symbol occurrence. -/
def size : SKTerm → Nat
  | var _ => 1
  | z => 1
  | s t => size t + 1
  | g a b => size a + size b + 1
  | f x y n => size x + size y + size n + 1

@[simp] theorem size_var (v : Nat) : size (var v) = 1 := rfl
@[simp] theorem size_z : size z = 1 := rfl
@[simp] theorem size_s (t : SKTerm) : size (s t) = size t + 1 := rfl
@[simp] theorem size_g (a b : SKTerm) : size (g a b) = size a + size b + 1 := rfl
@[simp] theorem size_f (x y n : SKTerm) :
    size (f x y n) = size x + size y + size n + 1 := rfl

theorem size_pos (t : SKTerm) : 0 < size t := by
  induction t with
  | var v => simp only [size_var]; omega
  | z => simp only [size_z]; omega
  | s t ih => simp only [size_s]; omega
  | g a b iha ihb => simp only [size_g]; omega
  | f x y n ihx ihy ihn => simp only [size_f]; omega

/--
Proves: the Schema A recursive rule raises structural size by exactly the size
of the duplicated argument.
Does not prove: anything about termination by this size.
Relation: SchemaTests.RootStep for the root rule shape.
Closure: root rule equation only.
Strategy: full.
Trust: kernel checked from the local structural definition and Nat arithmetic.
Scope: all x, y, and n.
-/
theorem rec_succ_size_gap (x y n : SKTerm) :
    size (g y (f x y n)) = size (f x y (s n)) + size y := by
  simp only [size_g, size_f, size_s]
  omega

theorem rec_succ_size_increases (x y n : SKTerm) :
    size (f x y (s n)) < size (g y (f x y n)) := by
  have hgap := rec_succ_size_gap x y n
  have hpos := size_pos y
  omega

/--
Proves: whenever the recursive call on the right side can step, the G
wrapper transports that step.
Does not prove: a root rule for outer G.
Relation: SchemaTests.Step.
Closure: full contextual closure.
Strategy: full.
Trust: kernel checked from Step.g_right.
Scope: every successor of the recursive call.
-/
theorem rec_succ_rhs_continues {x y n r : SKTerm}
    (h : Step (f x y n) r) :
    Step (g y (f x y n)) (g y r) :=
  Step.g_right h

/-- Closed ground computation used by the counterexample: sizes 5 and 6. -/
theorem ground_sizes :
    size (f z z (s z)) = 5 ∧ size (g z (f z z z)) = 6 := by
  constructor <;> rfl

/-- The two contextual steps in the Schema A ground counterexample. -/
theorem ground_steps :
    Step (f z z (s z)) (g z (f z z z)) ∧
      Step (g z (f z z z)) (g z z) := by
  constructor
  · exact Step.root (RootStep.succ z z z)
  · exact rec_succ_rhs_continues (Step.root (RootStep.base z z))

/--
Proves: the size-or-terminal disjunction is false for Schema A Step.
Does not prove: failure for RootStep read without contextual closure.
Relation: SchemaTests.Step.
Closure: full contextual closure.
Strategy: full.
Trust: kernel checked by one ground two-step witness.
Scope: the structural size defined in this namespace.
-/
theorem sizeOrTerminal_false :
    ¬ SizeOrTerminal Step size := by
  intro h
  rcases ground_steps with ⟨hfirst, hsecond⟩
  rcases h _ _ hfirst with hdecrease | hterminal
  · rcases ground_sizes with ⟨hleft, hright⟩
    rw [hleft, hright] at hdecrease
    omega
  · exact hterminal (g z z) hsecond

end SchemaA

end KO7Benchmark.ScoringAnchors.SizeOrTerminalDisjunction
