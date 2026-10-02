/-
  Failure families for scoring: measures a response can propose, and the
  ground instance that refutes each one.

  Relation: the two-rule schema of `SchemaKernel`.
  Closure: the root rules for the family statements, the full contextual
    closure `Step` for the corollaries.
  Property:
    1. No additive constructor-weight measure orients the recursive rule, with
       no hypothesis on the weights at all. The published obstruction assumed a
       positive weight on `G`; the substitution `y := S(Z)` refutes the whole
       family, zero weights included, so the class is empty rather than merely
       thin. `PaperB.AdditiveSKMeasure` is the special case.
    2. Term size increases across the recursive rule by exactly the size of
       the copied argument.
    3. The `S`-count measure, which carries weight zero on `G` and so sits
       outside the published family, increases whenever the copied argument
       carries two or more `S` symbols.
    4. The pair (counter, size) read lexicographically fails on the base rule.
    5. The right side of the recursive rule is not a subterm of the left side,
       so a subterm or embedding order gives no step.
    6. The copied variable occurs once on the left and twice on the right.
  Trust: mathlib only; no sorry, no axiom, no native_decide. Every numeric
    claim is a closed computation checked by `decide` or `rfl`.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.PaperB.SchemaAdditiveObstruction

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.MeasureFailures

open KO7Benchmark.SchemaTests
open KO7Benchmark.SchemaTests.CandidateD (sDepth)
open SKTerm

/-! ## 1. The additive family, with no hypothesis on the weights -/

/-- Constructor weights for an additive whole-term measure. No positivity is
    assumed anywhere, so this covers the all-zero assignment and every
    assignment that carries weight zero on `G`. -/
structure GenAdditive where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace GenAdditive

def eval (M : GenAdditive) : SKTerm → Nat
  | var _ => M.wVar
  | z => M.wZ
  | s t => M.wS + M.eval t
  | g a b => M.wG + M.eval a + M.eval b
  | f x y n => M.wF + M.eval x + M.eval y + M.eval n

@[simp] theorem eval_var (M : GenAdditive) (v : Nat) : M.eval (var v) = M.wVar := rfl
@[simp] theorem eval_z (M : GenAdditive) : M.eval z = M.wZ := rfl
@[simp] theorem eval_s (M : GenAdditive) (t : SKTerm) : M.eval (s t) = M.wS + M.eval t := rfl
@[simp] theorem eval_g (M : GenAdditive) (a b : SKTerm) :
    M.eval (g a b) = M.wG + M.eval a + M.eval b := rfl
@[simp] theorem eval_f (M : GenAdditive) (x y n : SKTerm) :
    M.eval (f x y n) = M.wF + M.eval x + M.eval y + M.eval n := rfl

/-- The refuting instance: `x := Z`, `y := S(Z)`, `n := Z`. The copied
    argument contributes its weight twice on the right and once on the left,
    and the remaining requirement is `wG + wZ < 0`. -/
theorem no_gen_additive_orients_recursive_root (M : GenAdditive) :
    ¬ (∀ x y n : SKTerm, M.eval (g y (f x y n)) < M.eval (f x y (s n))) := by
  intro h
  have hlt := h z (s z) z
  simp only [eval_g, eval_f, eval_s, eval_z] at hlt
  omega

/-- No additive whole-term measure orients the schema under context closure. -/
theorem no_gen_additive_orients_step (M : GenAdditive) :
    ¬ (∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a) := by
  intro h
  apply no_gen_additive_orients_recursive_root M
  intro x y n
  exact h (Step.root (RootStep.succ x y n))

/-- The published family with a positive `G` weight sits inside this one. -/
def ofPositiveG (M : KO7Benchmark.PaperB.AdditiveSKMeasure) : GenAdditive :=
  ⟨M.wVar, M.wZ, M.wS, M.wG, M.wF⟩

theorem eval_ofPositiveG (M : KO7Benchmark.PaperB.AdditiveSKMeasure) (t : SKTerm) :
    (ofPositiveG M).eval t = M.eval t := by
  induction t with
  | var v => rfl
  | z => rfl
  | s t ih =>
      show (ofPositiveG M).wS + (ofPositiveG M).eval t = M.wS + M.eval t
      rw [ih]
      rfl
  | g a b iha ihb =>
      show (ofPositiveG M).wG + (ofPositiveG M).eval a + (ofPositiveG M).eval b
        = M.wG + M.eval a + M.eval b
      rw [iha, ihb]
      rfl
  | f x y n ihx ihy ihn =>
      show (ofPositiveG M).wF + (ofPositiveG M).eval x + (ofPositiveG M).eval y
          + (ofPositiveG M).eval n
        = M.wF + M.eval x + M.eval y + M.eval n
      rw [ihx, ihy, ihn]
      rfl

/-- The published obstruction restated: it is the `wG > 0` case of the family
    above, and the positivity hypothesis was never needed. -/
theorem positiveG_case (M : KO7Benchmark.PaperB.AdditiveSKMeasure) :
    ¬ (∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a) := by
  intro h
  apply no_gen_additive_orients_step (ofPositiveG M)
  intro a b hs
  rw [eval_ofPositiveG, eval_ofPositiveG]
  exact h hs

end GenAdditive

/-! ## 2. Term size increases -/

/-- Term size: one unit per symbol occurrence, variables included. -/
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
  | var v => simp
  | z => simp
  | s t ih => simp only [size_s]; omega
  | g a b iha ihb => simp only [size_g]; omega
  | f x y n ihx ihy ihn => simp only [size_f]; omega

/-- The recursive rule raises term size by the size of the copied argument. -/
theorem size_gap (x y n : SKTerm) :
    size (g y (f x y n)) = size (f x y (s n)) + size y := by
  simp only [size_g, size_f, size_s]
  omega

/-- Term size increases across the recursive rule, for every instance. -/
theorem size_increases (x y n : SKTerm) :
    size (f x y (s n)) < size (g y (f x y n)) := by
  have h := size_gap x y n
  have hy := size_pos y
  omega

/-- A ground instance, for citation in scoring: sizes 5 and 6. -/
theorem size_ground_instance :
    size (f z z (s z)) = 5 ∧ size (g z (f z z z)) = 6 ∧
      RootStep (f z z (s z)) (g z (f z z z)) := by
  refine ⟨rfl, rfl, RootStep.succ z z z⟩

theorem size_not_step_orienting :
    ¬ (∀ {a b : SKTerm}, Step a b → size b < size a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z z z))
  simp [size] at hlt

/-! ## 3. The `S`-count measure: weight zero on `G` -/

/-- Number of `S` symbols in a term. Its `G` weight is zero, so it sits
    outside the published positive-weight family and inside `GenAdditive`. -/
def sCount : SKTerm → Nat
  | var _ => 0
  | z => 0
  | s t => sCount t + 1
  | g a b => sCount a + sCount b
  | f x y n => sCount x + sCount y + sCount n

@[simp] theorem sCount_s (t : SKTerm) : sCount (s t) = sCount t + 1 := rfl
@[simp] theorem sCount_g (a b : SKTerm) : sCount (g a b) = sCount a + sCount b := rfl
@[simp] theorem sCount_f (x y n : SKTerm) :
    sCount (f x y n) = sCount x + sCount y + sCount n := rfl

/-- The gap is the `S`-count of the copied argument, less one. -/
theorem sCount_gap (x y n : SKTerm) :
    sCount (g y (f x y n)) + 1 = sCount (f x y (s n)) + sCount y := by
  simp only [sCount_g, sCount_f, sCount_s]
  omega

/-- With two `S` symbols in the copied argument the measure increases. -/
theorem sCount_ground_counterexample :
    RootStep (f z (s (s z)) (s z)) (g (s (s z)) (f z (s (s z)) z)) ∧
      sCount (f z (s (s z)) (s z)) = 3 ∧ sCount (g (s (s z)) (f z (s (s z)) z)) = 4 :=
  ⟨RootStep.succ z (s (s z)) z, rfl, rfl⟩

theorem sCount_not_step_orienting :
    ¬ (∀ {a b : SKTerm}, Step a b → sCount b < sCount a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z (s (s z)) z))
  simp [sCount] at hlt

/-! ## 4. The lexicographic pair (counter, size) -/

/-- The pair a response proposes when it reads the counter first and breaks
    ties by size. -/
def lexPair (t : SKTerm) : Nat × Nat := (sDepth t, size t)

/-- The pair decreases on the recursive rule. -/
theorem lexPair_ok_on_recursive (x y n : SKTerm) :
    (lexPair (g y (f x y n))).1 < (lexPair (f x y (s n))).1 := by
  simp [lexPair, sDepth]

/-- The pair fails on the base rule: the first component rises when the
    returned argument carries an `S`. -/
theorem lexPair_fails_on_base :
    RootStep (f (s z) z z) (s z) ∧
      (lexPair (f (s z) z z)).1 = 0 ∧ (lexPair (s z)).1 = 1 :=
  ⟨RootStep.base (s z) z, rfl, rfl⟩

theorem lexPair_not_root_orienting :
    ¬ (∀ {a b : SKTerm}, RootStep a b →
        (lexPair b).1 < (lexPair a).1 ∨
          ((lexPair b).1 = (lexPair a).1 ∧ (lexPair b).2 < (lexPair a).2)) := by
  intro h
  rcases h (RootStep.base (s z) z) with hlt | ⟨heq, _⟩
  · simp [lexPair, sDepth] at hlt
  · simp [lexPair, sDepth] at heq

/-! ## 5. Subterm and embedding orders -/

/-- Reflexive subterm relation. -/
inductive Sub : SKTerm → SKTerm → Prop
  | refl (t : SKTerm) : Sub t t
  | s_arg {a t : SKTerm} : Sub a t → Sub a (s t)
  | g_left {a t b : SKTerm} : Sub a t → Sub a (g t b)
  | g_right {a t b : SKTerm} : Sub a t → Sub a (g b t)
  | f_arg1 {a t b c : SKTerm} : Sub a t → Sub a (f t b c)
  | f_arg2 {a t b c : SKTerm} : Sub a t → Sub a (f b t c)
  | f_arg3 {a t b c : SKTerm} : Sub a t → Sub a (f b c t)

theorem size_le_of_sub {a t : SKTerm} (h : Sub a t) : size a ≤ size t := by
  induction h with
  | refl => exact Nat.le_refl _
  | s_arg _ ih => simp only [size_s]; omega
  | g_left _ ih => simp only [size_g]; omega
  | g_right _ ih => simp only [size_g]; omega
  | f_arg1 _ ih => simp only [size_f]; omega
  | f_arg2 _ ih => simp only [size_f]; omega
  | f_arg3 _ ih => simp only [size_f]; omega

/-- The right side of the recursive rule is not a subterm of the left side,
    so a subterm order supplies no step there. -/
theorem rhs_not_subterm (x y n : SKTerm) :
    ¬ Sub (g y (f x y n)) (f x y (s n)) := by
  intro h
  have hle := size_le_of_sub h
  have hlt := size_increases x y n
  omega

/-! ## 6. The copied argument -/

/-- Occurrences of one variable in a term. -/
def occ (v : Nat) : SKTerm → Nat
  | var w => if v = w then 1 else 0
  | z => 0
  | s t => occ v t
  | g a b => occ v a + occ v b
  | f x y n => occ v x + occ v y + occ v n

/-- The copied argument occurs once on the left and twice on the right. This
    is the single structural fact that every failure above traces back to. -/
theorem copied_argument_doubles :
    occ 1 (f (var 0) (var 1) (s (var 2))) = 1 ∧
      occ 1 (g (var 1) (f (var 0) (var 1) (var 2))) = 2 := by
  constructor <;> rfl

/-- The counter occurs once on each side; the copying is confined to the
    second argument. -/
theorem counter_occurs_once :
    occ 2 (f (var 0) (var 1) (s (var 2))) = 1 ∧
      occ 2 (g (var 1) (f (var 0) (var 1) (var 2))) = 1 := by
  constructor <;> rfl

end KO7Benchmark.ScoringAnchors.MeasureFailures
