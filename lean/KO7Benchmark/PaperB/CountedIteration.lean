/-
  Counted iteration (ICLR Appendix C, Proposition 1).

  Relation: the two-rule schema of `SchemaKernel`.
  Closure: full contextual closure `Step`; the reflexive-transitive closure
    `Relation.ReflTransGen Step` for the multi-step statement.
  Property: `F(x, y, S^m(Z))` reduces to `h_y^m(x)`, where `h_y(v) = G(y, v)`;
    the recursive rule fires once per unit of the counter and the base rule
    once at the end. The index-carrying presentation
    `H(i, v) = (i + 1, g(y, i, v))` iterates to `(m, a_m)` for any `g`.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import Mathlib.Logic.Relation
import KO7Benchmark.SchemaTests.SchemaKernel

set_option autoImplicit false

namespace KO7Benchmark.PaperB.CountedIteration

open KO7Benchmark.SchemaTests
open SKTerm

/-- The numeral `S^m(Z)`. -/
def counter : Nat → SKTerm
  | 0 => z
  | m + 1 => s (counter m)

/-- `hIter y m x = G(y, G(y, ... G(y, x)))` with `m` occurrences of `G`. -/
def hIter (y : SKTerm) : Nat → SKTerm → SKTerm
  | 0, x => x
  | m + 1, x => g y (hIter y m x)

/-- Multi-step reduction. -/
abbrev StepStar : SKTerm → SKTerm → Prop := Relation.ReflTransGen Step

theorem stepStar_g_right {a t u : SKTerm} (h : StepStar t u) : StepStar (g a t) (g a u) :=
  Relation.ReflTransGen.lift (fun w => g a w) (fun _ _ hs => Step.g_right hs) h

/-- Proposition 1: `F(x, y, S^m(Z)) ->* h_y^m(x)`. -/
theorem counted_iteration (x y : SKTerm) :
    ∀ m : Nat, StepStar (f x y (counter m)) (hIter y m x)
  | 0 => Relation.ReflTransGen.single (Step.root (RootStep.base x y))
  | m + 1 => by
      have h1 : Step (f x y (counter (m + 1))) (g y (f x y (counter m))) :=
        Step.root (RootStep.succ x y (counter m))
      have h2 : StepStar (g y (f x y (counter m))) (g y (hIter y m x)) :=
        stepStar_g_right (counted_iteration x y m)
      exact Relation.ReflTransGen.head h1 h2

/-- Number of steps in the reduction: one recursive step per counter unit and
    one base step. Stated through an explicit step-indexed chain. -/
inductive StepN : Nat → SKTerm → SKTerm → Prop
  | refl (t : SKTerm) : StepN 0 t t
  | cons {k : Nat} {t u v : SKTerm} : Step t u → StepN k u v → StepN (k + 1) t v

theorem stepN_g_right {a t u : SKTerm} {k : Nat} (h : StepN k t u) :
    StepN k (g a t) (g a u) := by
  induction h with
  | refl t => exact StepN.refl _
  | cons hs _ ih => exact StepN.cons (Step.g_right hs) ih

/-- The reduction of Proposition 1 takes exactly `m + 1` steps. -/
theorem counted_iteration_length (x y : SKTerm) :
    ∀ m : Nat, StepN (m + 1) (f x y (counter m)) (hIter y m x)
  | 0 => StepN.cons (Step.root (RootStep.base x y)) (StepN.refl _)
  | m + 1 =>
      StepN.cons (Step.root (RootStep.succ x y (counter m)))
        (stepN_g_right (counted_iteration_length x y m))

/-! ## The index-carrying presentation -/

section Indexed

variable {α : Type}

/-- One iteration step: advance the index and apply `gf` at the current index. -/
def indexedStep (gf : Nat → α → α) : Nat × α → Nat × α :=
  fun p => (p.1 + 1, gf p.1 p.2)

/-- The sequence `a_0 = x`, `a_{i+1} = gf i a_i`. -/
def aSeq (gf : Nat → α → α) (x : α) : Nat → α
  | 0 => x
  | i + 1 => gf i (aSeq gf x i)

/-- `H^m(0, x) = (m, a_m)`: the iteration reads its own index off the pair. -/
theorem iterate_indexedStep (gf : Nat → α → α) (x : α) :
    ∀ m : Nat, (indexedStep gf)^[m] (0, x) = (m, aSeq gf x m)
  | 0 => rfl
  | m + 1 => by
      rw [Function.iterate_succ_apply', iterate_indexedStep gf x m]
      rfl

end Indexed

end KO7Benchmark.PaperB.CountedIteration
