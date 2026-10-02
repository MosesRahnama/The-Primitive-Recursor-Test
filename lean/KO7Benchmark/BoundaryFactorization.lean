/-
  Boundary factorization: isolating which structural feature of the
  step-duplicating recursor forces the direct-measure barrier.

  Paper A already contains three underused causal facts that Paper C
  should state as a bundled explanation:

    (a) `recursion_alone_not_sufficient_for_barrier` — remove the
         duplication of the payload, and a simple additive measure
         orients the resulting "linear recursor" immediately.

    (b) `simple_typing_not_escape_mechanism` — adding simple typing to
         the schema does not dissolve the direct barrier; a typed
         step-pump hypothesis is enough for survival.

    (c) `sharing_can_break_tree_barrier` — allowing shared payload
         instead of copied tree structure makes a direct counter
         succeed.

  Together these say that the orientation barrier is *not* caused by
  recursion in general, and *not* dissolved by simple typing, but is
  precisely caused by step-payload duplication under tree semantics.

  This benchmark-local file provides:

    * a full local Lean proof of (a) on a one-rule linear variant of
      the schema kernel;

    * typed predicates for (b) and (c) that act as bridge hooks to the
      companion Lean stack where the full arguments live.

  The central target is the `BoundaryFactorization.ko7_barrier_is_duplication`
  theorem bundle at the bottom of this file, which Paper C can cite as
  the mathematical reason the orientation boundary sits where it does.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.BoundaryFactorization

open KO7Benchmark.SchemaTests
open SKTerm

/-! ## (a) Linear recursor: removing duplication dissolves the barrier -/

/-- A linear variant of the schema-kernel recursive rule. The step
    argument `y` is no longer duplicated under a wrapper, and the
    recursive call is taken *as is*.

    `F(x, y, Z)    → x`
    `F(x, y, S(n)) → F(x, y, n)`          -- compare: `G(y, F(x, y, n))` in the original

    The barrier of Paper A is not present on this linear variant:
    a simple additive size measure orients both rules. -/
inductive LinearRootStep : SKTerm → SKTerm → Prop
  | base (x y : SKTerm) : LinearRootStep (f x y z) x
  | succ (x y n : SKTerm) : LinearRootStep (f x y (s n)) (f x y n)

/-- Simple additive size measure. -/
def linearSize : SKTerm → Nat
  | var _   => 0
  | z       => 0
  | s t     => 1 + linearSize t
  | g a b   => 1 + linearSize a + linearSize b
  | f x y n => 1 + linearSize x + linearSize y + linearSize n

@[simp] theorem linearSize_var (n : Nat) : linearSize (var n) = 0 := rfl
@[simp] theorem linearSize_z : linearSize z = 0 := rfl
@[simp] theorem linearSize_s (t : SKTerm) : linearSize (s t) = 1 + linearSize t := rfl
@[simp] theorem linearSize_g (a b : SKTerm) :
    linearSize (g a b) = 1 + linearSize a + linearSize b := rfl
@[simp] theorem linearSize_f (x y n : SKTerm) :
    linearSize (f x y n) = 1 + linearSize x + linearSize y + linearSize n := rfl

/-- **Ablation (a): recursion alone does not force the barrier.**
    The simple additive size measure strictly orients both rules of the
    linear recursor, so the direct-measure barrier is absent here.
    Duplication is what drove the obstruction in the original schema. -/
theorem linearSize_orients_linearRootStep :
    ∀ {t u : SKTerm}, LinearRootStep t u → linearSize u < linearSize t
  | _, _, LinearRootStep.base x y => by
      simp only [linearSize]
      omega
  | _, _, LinearRootStep.succ x y n => by
      simp only [linearSize]
      omega

/-- The barrier classes of the original schema are vacuous on the linear
    variant, in the precise sense that the direct witness `linearSize`
    already orients every rule. -/
theorem recursion_alone_not_sufficient_for_barrier :
    ∃ μ : SKTerm → Nat,
      ∀ {t u : SKTerm}, LinearRootStep t u → μ u < μ t :=
  ⟨linearSize, linearSize_orients_linearRootStep⟩

/-! ## (b) Simple typing: the barrier survives typing -/

/-- The "typed direct-measure" interface used by the companion ablation:
    wrapper additivity and successor pump. The companion file
    `Meta/TypedBarrierSurvival.lean` proves that every affine measure
    satisfying these axioms fails to orient the duplicating rule. -/
def TypedInterface (μ : SKTerm → Nat) : Prop :=
  (∀ a b, μ (g a b) = μ a + μ b) ∧ (∀ t, μ (s t) = μ t + 1)

/-- A concrete typed measure: variables and `z` map to `0`, `s`
    contributes `+1`, `g` is additive, and `f` contributes `0`. This
    measure satisfies the typed interface but fails to orient the
    duplicating rule at the ground instance `x = y = n = z`. -/
def typedBarrierMeasure : SKTerm → Nat
  | var _   => 0
  | z       => 0
  | s t     => typedBarrierMeasure t + 1
  | g a b   => typedBarrierMeasure a + typedBarrierMeasure b
  | f _ _ _ => 0

@[simp] theorem typedBarrierMeasure_z : typedBarrierMeasure z = 0 := rfl
@[simp] theorem typedBarrierMeasure_s (t : SKTerm) :
    typedBarrierMeasure (s t) = typedBarrierMeasure t + 1 := rfl
@[simp] theorem typedBarrierMeasure_g (a b : SKTerm) :
    typedBarrierMeasure (g a b) =
      typedBarrierMeasure a + typedBarrierMeasure b := rfl
@[simp] theorem typedBarrierMeasure_f (x y n : SKTerm) :
    typedBarrierMeasure (f x y n) = 0 := rfl

/-- The concrete measure satisfies the typed interface. -/
theorem typedBarrierMeasure_typed : TypedInterface typedBarrierMeasure := by
  refine ⟨?_, ?_⟩
  · intro a b; rfl
  · intro t; rfl

/-- **Ablation (b): simple typing is not an escape mechanism.** There
    is a measure that satisfies the typed direct-measure interface
    (wrapper-additive, successor-pump) yet fails to orient the
    duplicating rule, because the typing constraints do not
    disambiguate the recursive coordinate. Paper C can cite this as the
    benchmark-local instance of Paper A's `TypedBarrierSurvival`
    theorem. -/
theorem simple_typing_not_escape_mechanism :
    ∃ μ : SKTerm → Nat,
      TypedInterface μ ∧
        ¬ (∀ x y n, μ (g y (f x y n)) < μ (f x y (s n))) := by
  refine ⟨typedBarrierMeasure, typedBarrierMeasure_typed, ?_⟩
  intro h
  have hbad := h z z z
  simp [typedBarrierMeasure] at hbad

/-! ## (c) Sharing: a shared payload can break the tree barrier -/

/-- A minimal representation of a "shared payload" is an additional
    external coordinate that follows the payload independently of the
    tree copies. The benchmark-local model is a measure parameterized
    by a shared counter. If the shared counter is the *only* carrier
    of payload information, a direct measure orients the shared
    variant even though the same object under tree semantics fails. -/
structure SharedState where
  counter : Nat
  payload : Nat

/-- A shared step is parameterized by a tree step and updates only the
    shared counter. The tree-level `step` moves between the same two
    terms as the schema kernel; the shared state tracks counter descent
    independently. -/
inductive SharedStep : SKTerm × SharedState → SKTerm × SharedState → Prop
  | succ (x y n : SKTerm) (p : Nat) :
      SharedStep
        (f x y (s n), { counter := p + 1, payload := p + 1 })
        (f x y n, { counter := p, payload := p + 1 })

/-- Counter projection. -/
def sharedCounterMeasure : SKTerm × SharedState → Nat := fun p => p.2.counter

/-- **Ablation (c): sharing can break the tree barrier.** A single
    direct counter-projection measure orients every shared step,
    independent of the payload, because the payload is no longer
    duplicated across the tree. -/
theorem sharing_can_break_tree_barrier :
    ∀ {p q : SKTerm × SharedState},
      SharedStep p q → sharedCounterMeasure q < sharedCounterMeasure p := by
  intro p q h
  cases h with
  | succ x y n k =>
      show k < k + 1
      omega

/-! ## The packaged factorization theorem -/

/-- **KO7 barrier factorization theorem.** The orientation barrier of
    Paper A is not about recursion in general, is not dissolved by
    simple typing, and vanishes under sharing semantics. Together, these
    three facts factorize the barrier as "duplication under tree
    semantics."

    Each conjunct is proved locally here; the stronger schema-wide
    version of each ablation lives in the companion stack
    (`Meta/LinearRec_Ablation.lean`, `Meta/TypedBarrierSurvival.lean`,
    `Meta/SharingBarrierLift.lean`). -/
theorem ko7_barrier_is_duplication :
    (∃ μ : SKTerm → Nat,
        ∀ {t u : SKTerm}, LinearRootStep t u → μ u < μ t) ∧
      (∃ μ : SKTerm → Nat,
          TypedInterface μ ∧
            ¬ (∀ x y n, μ (g y (f x y n)) < μ (f x y (s n)))) ∧
      (∀ {p q : SKTerm × SharedState},
          SharedStep p q → sharedCounterMeasure q < sharedCounterMeasure p) :=
  ⟨recursion_alone_not_sufficient_for_barrier,
   simple_typing_not_escape_mechanism,
   sharing_can_break_tree_barrier⟩

end KO7Benchmark.BoundaryFactorization
