/-
  Subterm measures on the SANS TRS, as one family rather than one measure.

  (VAR x y n)
  (RULES
    F(x, y, Z)    -> x
    F(x, y, S(n)) -> G(F(x, y, n))
  )

  Many answers to this benchmark item give no polynomial interpretation.  They
  collect, over every `F` subterm of the whole term, a size of that subterm's
  third argument, and claim the collection falls at every step of the
  context-closed relation.  The collection is read either as a multiset under
  the Dershowitz-Manna order or as a sum of naturals, and the size is read
  either as the count of constructor symbols or as the count of `S` symbols.

  Those readings differ in two places only, so this file proves the family once
  and instantiates it, instead of proving each reading on its own.  The family
  is `ThirdArgSize`, and it has exactly two clauses:

    succ_eq : val (S t) = val t + 1
    mono    : Step t u -> val u <= val t

  `succ_eq` is what makes the step rule drop the entry.  `mono` is what a step
  inside a third argument needs, because that argument is both an element of
  the collection and a subterm carrying its own elements; without it the family
  theorem is false, since nothing else constrains `val` on a rewritten term.
  Both clauses are load-bearing: `succ_eq` closes the root step case and `mono`
  closes `f_arg3`.

  Duplication stress test (LASOT section 4.B).  The step rule's right side is
  `G(F(x, y, n))` with `G` unary, so each of `x`, `y`, `n` occurs exactly once
  on each side and the rule copies nothing.  The after-before identity is

    bag(after) = bag(before) - {val (S n)} + {val n},   val (S n) = val n + 1,

  with no `+ M(S)` term.  `fBag_succ_rule_is_single_replacement` below is that
  identity as a theorem.  This is the point of difference from the duplicating
  Schema A kernel, where the same collection fails.

  Relation: Step, the context closure of RootStep, both rules.
  Closure: context.
  Strategy: full.
  Property: one_step strict decrease, and SN through well-foundedness.
  Trust: kernel only, over Mathlib's Dershowitz-Manna order and its
  well-foundedness theorem.
-/
import Mathlib.Data.Multiset.DershowitzManna
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SANSTests.SANSKernel

set_option autoImplicit false

namespace KO7Benchmark.SANSTests.SubtermMeasureWitness

open KO7Benchmark.SANSTests
open SANSTerm

/-- A size taken on the third argument of `F`.  Its value on any particular
shape is unconstrained apart from the two clauses below, so this structure is
the family of readings and not one measure. -/
structure ThirdArgSize where
  val : SANSTerm → Nat
  succ_eq : ∀ t : SANSTerm, val (s t) = val t + 1
  mono : ∀ {t u : SANSTerm}, Step t u → val u ≤ val t

/-- The multiset holding, for every `F` subterm of `t`, the size of that
subterm's third argument.  This is the "all recursive subterms" scope. -/
def fBag (q : ThirdArgSize) : SANSTerm → Multiset Nat
  | var _ => 0
  | z => 0
  | s t => fBag q t
  | g t => fBag q t
  | f x y n => {q.val n} + (fBag q x + fBag q y + fBag q n)

/-- The same collection read as a sum instead of a multiset. -/
def fSum (q : ThirdArgSize) (t : SANSTerm) : Nat := (fBag q t).sum

@[simp] theorem fBag_var (q : ThirdArgSize) (k : Nat) : fBag q (var k) = 0 := rfl
@[simp] theorem fBag_z (q : ThirdArgSize) : fBag q z = 0 := rfl
@[simp] theorem fBag_s (q : ThirdArgSize) (t : SANSTerm) : fBag q (s t) = fBag q t := rfl
@[simp] theorem fBag_g (q : ThirdArgSize) (t : SANSTerm) : fBag q (g t) = fBag q t := rfl
@[simp] theorem fBag_f (q : ThirdArgSize) (x y n : SANSTerm) :
    fBag q (f x y n) = {q.val n} + (fBag q x + fBag q y + fBag q n) := rfl

@[simp] theorem fSum_var (q : ThirdArgSize) (k : Nat) : fSum q (var k) = 0 := rfl
@[simp] theorem fSum_z (q : ThirdArgSize) : fSum q z = 0 := rfl
@[simp] theorem fSum_s (q : ThirdArgSize) (t : SANSTerm) : fSum q (s t) = fSum q t := rfl
@[simp] theorem fSum_g (q : ThirdArgSize) (t : SANSTerm) : fSum q (g t) = fSum q t := rfl

@[simp] theorem fSum_f (q : ThirdArgSize) (x y n : SANSTerm) :
    fSum q (f x y n) = q.val n + (fSum q x + fSum q y + fSum q n) := by
  simp [fSum, fBag]

/-- The step rule removes one element and puts back one element smaller by one.
Nothing is copied.  This discharges the duplication stress test for this rule. -/
theorem fBag_succ_rule_is_single_replacement (q : ThirdArgSize) (x y n : SANSTerm) :
    fBag q (f x y (s n)) = {q.val n + 1} + (fBag q x + fBag q y + fBag q n)
      ∧ fBag q (g (f x y n)) = {q.val n} + (fBag q x + fBag q y + fBag q n) := by
  refine ⟨?_, ?_⟩
  · simp only [fBag_f, fBag_s, q.succ_eq]
  · simp only [fBag_g, fBag_f]

/-- One entry weakly smaller, a common part, and the rest strictly down in the
Dershowitz-Manna order.  Every context case of the family theorem is this
lemma. -/
theorem isDershowitzMannaLT_cons_of_le {a b : Nat} (hab : a ≤ b)
    (W : Multiset Nat) {M N M' N' : Multiset Nat}
    (hM' : M' = {a} + (W + M)) (hN' : N' = {b} + (W + N))
    (h : Multiset.IsDershowitzMannaLT M N) :
    Multiset.IsDershowitzMannaLT M' N' := by
  subst hM'
  subst hN'
  obtain ⟨X, Y, Z, hZ, hM, hN, hYZ⟩ := h
  rcases lt_or_eq_of_le hab with hlt | heq
  · refine ⟨W + X, {a} + Y, {b} + Z, ?_, ?_, ?_, ?_⟩
    · intro hcon
      have hc := congrArg Multiset.card hcon
      simp at hc
    · rw [hM]; abel
    · rw [hN]; abel
    · intro w hw
      simp only [Multiset.singleton_add, Multiset.mem_cons] at hw
      rcases hw with rfl | hw
      · exact ⟨b, by simp, hlt⟩
      · obtain ⟨zz, hzz, hlt'⟩ := hYZ w hw
        exact ⟨zz, by simp [hzz], hlt'⟩
  · subst heq
    refine ⟨{a} + (W + X), Y, Z, hZ, ?_, ?_, hYZ⟩
    · rw [hM]; abel
    · rw [hN]; abel

/-- The family theorem.  For every size in `ThirdArgSize`, the multiset of
third-argument sizes over all `F` subterms falls in the Dershowitz-Manna order
at every step of the context-closed SANS relation, base rule included. -/
theorem fBag_ctxStep_isDershowitzMannaLT (q : ThirdArgSize) :
    ∀ {t u : SANSTerm}, Step t u →
      Multiset.IsDershowitzMannaLT (fBag q u) (fBag q t)
  | _, _, Step.root (RootStep.base x y) => by
      -- The base rule deletes the `F` node's own entry and everything under `y`.
      refine ⟨fBag q x, 0, {q.val z} + (fBag q y + fBag q z), ?_, ?_, ?_, ?_⟩
      · intro hcon
        have hc := congrArg Multiset.card hcon
        simp at hc
      · simp
      · simp only [fBag_f]; abel
      · intro w hw
        simp at hw
  | _, _, Step.root (RootStep.succ x y n) => by
      -- The step rule replaces `val (S n)` by `val n`, one smaller.
      refine ⟨fBag q x + fBag q y + fBag q n, {q.val n}, {q.val (s n)}, ?_, ?_, ?_, ?_⟩
      · simp
      · simp only [fBag_g, fBag_f]; abel
      · simp only [fBag_f, fBag_s]; abel
      · intro w hw
        simp only [Multiset.mem_singleton] at hw
        subst hw
        refine ⟨q.val (s n), by simp, ?_⟩
        rw [q.succ_eq]
        omega
  | _, _, Step.s_arg h => by
      simpa using fBag_ctxStep_isDershowitzMannaLT q h
  | _, _, Step.g_arg h => by
      simpa using fBag_ctxStep_isDershowitzMannaLT q h
  | _, _, Step.f_arg1 (b := b) (c := c) h =>
      isDershowitzMannaLT_cons_of_le (le_refl (q.val c)) (fBag q b + fBag q c)
        (by simp only [fBag_f]; abel) (by simp only [fBag_f]; abel)
        (fBag_ctxStep_isDershowitzMannaLT q h)
  | _, _, Step.f_arg2 (a := a) (c := c) h =>
      isDershowitzMannaLT_cons_of_le (le_refl (q.val c)) (fBag q a + fBag q c)
        (by simp only [fBag_f]; abel) (by simp only [fBag_f]; abel)
        (fBag_ctxStep_isDershowitzMannaLT q h)
  | _, _, Step.f_arg3 (a := a) (b := b) h =>
      -- The rewritten argument is both an element and a subterm: `mono` moves
      -- the element, the recursive call moves the sub-bag.
      -- `fBag_f` alone closes both rearrangements here: the varying argument is
      -- already the rightmost summand.
      isDershowitzMannaLT_cons_of_le (q.mono h) (fBag q a + fBag q b)
        (by simp only [fBag_f]) (by simp only [fBag_f])
        (fBag_ctxStep_isDershowitzMannaLT q h)

/-- The sum reading.  The base rule discards the `F` node's own entry, so the
sum falls strictly only when that entry is positive on `Z`; `sCount` fails that
and `termSize` meets it, which is why only the size reading is proved here. -/
theorem fSum_ctxStep_lt (q : ThirdArgSize) (hz : 0 < q.val z) :
    ∀ {t u : SANSTerm}, Step t u → fSum q u < fSum q t
  | _, _, Step.root (RootStep.base x y) => by
      simp only [fSum_f]
      omega
  | _, _, Step.root (RootStep.succ x y n) => by
      simp only [fSum_g, fSum_f, fSum_s, q.succ_eq]
      omega
  | _, _, Step.s_arg h => by
      simpa using fSum_ctxStep_lt q hz h
  | _, _, Step.g_arg h => by
      simpa using fSum_ctxStep_lt q hz h
  | _, _, Step.f_arg1 h => by
      have := fSum_ctxStep_lt q hz h
      simp only [fSum_f]
      omega
  | _, _, Step.f_arg2 h => by
      have := fSum_ctxStep_lt q hz h
      simp only [fSum_f]
      omega
  | _, _, Step.f_arg3 h => by
      have hlt := fSum_ctxStep_lt q hz h
      have hle := q.mono h
      simp only [fSum_f]
      omega

/-- Strong normalization of the context-closed relation from the multiset
reading, for every member of the family. -/
theorem wf_ctxStepRev_of_fBag (q : ThirdArgSize) :
    WellFounded (fun a b : SANSTerm => Step b a) := by
  have hsub : Subrelation (fun a b : SANSTerm => Step b a)
      (InvImage Multiset.IsDershowitzMannaLT (fBag q)) := by
    intro a b hab
    exact fBag_ctxStep_isDershowitzMannaLT q hab
  exact Subrelation.wf hsub
    (InvImage.wf (fun t : SANSTerm => fBag q t) Multiset.wellFounded_isDershowitzMannaLT)

/-! ### The two members of the family that the benchmark answers name -/

/-- Number of constructor symbols. -/
def termSize : SANSTerm → Nat
  | var _ => 1
  | z => 1
  | s t => termSize t + 1
  | g t => termSize t + 1
  | f x y n => termSize x + termSize y + termSize n + 1

/-- Number of `S` symbols. -/
def sCount : SANSTerm → Nat
  | var _ => 0
  | z => 0
  | s t => sCount t + 1
  | g t => sCount t
  | f x y n => sCount x + sCount y + sCount n

theorem termSize_ctxStep_le : ∀ {t u : SANSTerm}, Step t u → termSize u ≤ termSize t
  | _, _, Step.root (RootStep.base x y) => by simp [termSize]; omega
  | _, _, Step.root (RootStep.succ x y n) => by simp [termSize]; omega
  | _, _, Step.s_arg h => by
      have := termSize_ctxStep_le h
      simp only [termSize]; omega
  | _, _, Step.g_arg h => by
      have := termSize_ctxStep_le h
      simp only [termSize]; omega
  | _, _, Step.f_arg1 h => by
      have := termSize_ctxStep_le h
      simp only [termSize]; omega
  | _, _, Step.f_arg2 h => by
      have := termSize_ctxStep_le h
      simp only [termSize]; omega
  | _, _, Step.f_arg3 h => by
      have := termSize_ctxStep_le h
      simp only [termSize]; omega

theorem sCount_ctxStep_le : ∀ {t u : SANSTerm}, Step t u → sCount u ≤ sCount t
  | _, _, Step.root (RootStep.base x y) => by simp [sCount]
  | _, _, Step.root (RootStep.succ x y n) => by simp [sCount]
  | _, _, Step.s_arg h => by
      have := sCount_ctxStep_le h
      simp only [sCount]; omega
  | _, _, Step.g_arg h => by
      have := sCount_ctxStep_le h
      simp only [sCount]; omega
  | _, _, Step.f_arg1 h => by
      have := sCount_ctxStep_le h
      simp only [sCount]; omega
  | _, _, Step.f_arg2 h => by
      have := sCount_ctxStep_le h
      simp only [sCount]; omega
  | _, _, Step.f_arg3 h => by
      have := sCount_ctxStep_le h
      simp only [sCount]; omega

/-- The family at the constructor-count reading. -/
def sizeArg : ThirdArgSize where
  val := termSize
  succ_eq := fun _ => rfl
  mono := termSize_ctxStep_le

/-- The family at the successor-count reading. -/
def successorCountArg : ThirdArgSize where
  val := sCount
  succ_eq := fun _ => rfl
  mono := sCount_ctxStep_le

/-! ### The four readings the benchmark answers state -/

/-- Reading: quantity `term_size`, scope all recursive subterms, aggregate
multiset, strict, every step, contextual target. -/
theorem termSize_bag_ctxStep_isDershowitzMannaLT {t u : SANSTerm} (h : Step t u) :
    Multiset.IsDershowitzMannaLT (fBag sizeArg u) (fBag sizeArg t) :=
  fBag_ctxStep_isDershowitzMannaLT sizeArg h

/-- Reading: quantity `total_S`, scope all recursive subterms, aggregate
multiset, strict, every rule application, contextual target. -/
theorem sCount_bag_ctxStep_isDershowitzMannaLT {t u : SANSTerm} (h : Step t u) :
    Multiset.IsDershowitzMannaLT (fBag successorCountArg u) (fBag successorCountArg t) :=
  fBag_ctxStep_isDershowitzMannaLT successorCountArg h

/-- Reading: quantity `term_size`, scope all recursive subterms, aggregate sum,
strict, every step, contextual target. -/
theorem termSize_sum_ctxStep_lt {t u : SANSTerm} (h : Step t u) :
    fSum sizeArg u < fSum sizeArg t :=
  fSum_ctxStep_lt sizeArg (by decide) h

/-- The successor count is not positive on `Z`, so the sum reading is not
available for it.  This records the boundary rather than leaving it implicit. -/
theorem sCount_z_not_positive : successorCountArg.val z = 0 := rfl

/-- Strong normalization of the context-closed SANS relation, through the
constructor-count member of the family. -/
theorem wf_ctxStepRev_termSize : WellFounded (fun a b : SANSTerm => Step b a) :=
  wf_ctxStepRev_of_fBag sizeArg

/-- Strong normalization of the context-closed SANS relation, through the
successor-count member of the family. -/
theorem wf_ctxStepRev_sCount : WellFounded (fun a b : SANSTerm => Step b a) :=
  wf_ctxStepRev_of_fBag successorCountArg

/-! ### Non-vacuity: the relation this is about is inhabited -/

theorem step_inhabited : Step (f z z (s z)) (g (f z z z)) :=
  Step.root (RootStep.succ z z z)

theorem fBag_strictly_falls_on_that_step :
    Multiset.IsDershowitzMannaLT (fBag sizeArg (g (f z z z))) (fBag sizeArg (f z z (s z))) :=
  termSize_bag_ctxStep_isDershowitzMannaLT step_inhabited

end KO7Benchmark.SANSTests.SubtermMeasureWitness
