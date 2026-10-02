/-
  Demarcation of the rule-derived route (ICLR Section 5, "Rule-derived and chosen").

  Relation: the two-rule schema of `SchemaKernel`,
      F(x, y, Z) -> x,   F(x, y, S(n)) -> G(y, F(x, y, n)),
    and its dependency pair F(x, y, S(n)) -> F(x, y, n).
  Closure: the root pair for the projection statements; the two root rules for
    the path-order statements (a path order is closed under contexts and
    substitutions by construction, so root orientation is the whole obligation).
  Property:
    1. Among the three simple projections of F#, only the third argument gives a
       strict step on the pair; the first two project to equal terms, so no
       measure of any kind separates them.
    2. A native lexicographic path order over a parametric precedence on the
       four function symbols orients both rules if and only if the precedence
       puts F above G. The base rule holds under every precedence, and the
       minimal precedence {F > G} already suffices.
    3. 12 of the 24 total orders on {Z, S, G, F} put F above G.
  Trust: mathlib only; `decide` on explicit finite lists; no sorry, no axiom,
    no native_decide. Orientation is proved; the well-foundedness of a
    lexicographic path order over a well-founded precedence is the classical
    theorem of Dershowitz (1982) and is not restated here.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness

set_option autoImplicit false

namespace KO7Benchmark.PaperB.Demarcation

open KO7Benchmark.SchemaTests
open KO7Benchmark.SchemaTests.CandidateD (sDepth DPPair dp_pair_decreases)
open SKTerm

/-! ## 1. Simple projections of the dependency pair -/

/-- Term size: one unit per symbol occurrence, variables included. -/
def size : SKTerm → Nat
  | var _ => 1
  | z => 1
  | s t => size t + 1
  | g a b => size a + size b + 1
  | f x y n => size x + size y + size n + 1

/-- Simple projection of an `F`-headed term to argument `i` (0-based).
    Any other term is returned unchanged. -/
def proj (i : Fin 3) : SKTerm → SKTerm
  | f x y n =>
      match i.val with
      | 0 => x
      | 1 => y
      | _ => n
  | t => t

@[simp] theorem proj_f_zero (x y n : SKTerm) : proj ⟨0, by omega⟩ (f x y n) = x := rfl
@[simp] theorem proj_f_one (x y n : SKTerm) : proj ⟨1, by omega⟩ (f x y n) = y := rfl
@[simp] theorem proj_f_two (x y n : SKTerm) : proj ⟨2, by omega⟩ (f x y n) = n := rfl

/-- Projections 1 and 2 send both sides of the dependency pair to the same term. -/
theorem proj_first_eq (x y n : SKTerm) :
    proj ⟨0, by omega⟩ (f x y (s n)) = proj ⟨0, by omega⟩ (f x y n) := rfl

theorem proj_second_eq (x y n : SKTerm) :
    proj ⟨1, by omega⟩ (f x y (s n)) = proj ⟨1, by omega⟩ (f x y n) := rfl

/-- Projection 3 sends the pair to `(S n, n)`, a strict `sDepth` step. -/
theorem proj_third_strict (x y n : SKTerm) :
    sDepth (proj ⟨2, by omega⟩ (f x y n)) < sDepth (proj ⟨2, by omega⟩ (f x y (s n))) := by
  show sDepth n < sDepth (s n)
  simp

/-- On the first two projections no measure whatsoever separates the pair,
    because the projected terms are equal. -/
theorem no_measure_separates_first_two (μ : SKTerm → Nat) (i : Fin 3) (hi : i.val < 2)
    (x y n : SKTerm) :
    ¬ μ (proj i (f x y n)) < μ (proj i (f x y (s n))) := by
  rcases i with ⟨i, hlt⟩
  interval_cases i <;> simp [proj]

/-- The demarcation in one statement: a simple projection gives a strict
    size step on the dependency pair exactly when it is the third argument. -/
theorem projection_strict_iff (i : Fin 3) (x y n : SKTerm) :
    size (proj i (f x y n)) < size (proj i (f x y (s n))) ↔ i.val = 2 := by
  rcases i with ⟨i, hlt⟩
  interval_cases i <;> simp [proj, size]

/-! ## 2. A native lexicographic path order on the four-symbol signature -/

/-- The four function symbols of the schema signature. Variables are not symbols. -/
inductive Sym
  | z
  | s
  | g
  | f
  deriving DecidableEq, Repr

/-- Root symbol of a term; a variable has none. -/
def root : SKTerm → Option Sym
  | var _ => none
  | z => some .z
  | s _ => some .s
  | g _ _ => some .g
  | f _ _ _ => some .f

/-- Immediate arguments of a term. -/
def args : SKTerm → List SKTerm
  | var _ => []
  | z => []
  | s t => [t]
  | g a b => [a, b]
  | f x y n => [x, y, n]

/-- `occurs v t = true` when the variable `v` occurs in `t`. -/
def occurs (v : Nat) : SKTerm → Bool
  | var w => decide (v = w)
  | z => false
  | s t => occurs v t
  | g a b => occurs v a || occurs v b
  | f x y n => occurs v x || occurs v y || occurs v n

mutual
/-- Lexicographic path order with precedence `P` on the function symbols and
    lexicographic status at every symbol (Kamin and Lévy; Dershowitz 1982;
    Baader and Nipkow, Definition 5.4.12). `LPO P t u` reads `t >_lpo u`. -/
inductive LPO (P : Sym → Sym → Prop) : SKTerm → SKTerm → Prop
  | var_below {t : SKTerm} {v : Nat} :
      t ≠ var v → occurs v t = true → LPO P t (var v)
  | sub_eq {t a : SKTerm} :
      a ∈ args t → LPO P t a
  | sub_lt {t u a : SKTerm} :
      a ∈ args t → LPO P a u → LPO P t u
  | prec {t u : SKTerm} {ft fu : Sym} :
      root t = some ft → root u = some fu → P ft fu →
      (∀ b ∈ args u, LPO P t b) → LPO P t u
  | lex {t u : SKTerm} {ft : Sym} :
      root t = some ft → root u = some ft →
      (∀ b ∈ args u, LPO P t b) → LexLPO P (args t) (args u) → LPO P t u

/-- Lexicographic extension of `LPO P` to argument lists. -/
inductive LexLPO (P : Sym → Sym → Prop) : List SKTerm → List SKTerm → Prop
  | head {a b : SKTerm} {as bs : List SKTerm} :
      LPO P a b → LexLPO P (a :: as) (b :: bs)
  | tail {a : SKTerm} {as bs : List SKTerm} :
      LexLPO P as bs → LexLPO P (a :: as) (a :: bs)
end

/-- A variable is minimal: nothing is `LPO`-below it... read the other way,
    a variable is never `LPO`-above any term. -/
theorem not_lpo_var_left (P : Sym → Sym → Prop) (v : Nat) (u : SKTerm) :
    ¬ LPO P (var v) u := by
  intro h
  cases h with
  | var_below hne hocc =>
      simp [occurs] at hocc
      subst hocc
      exact hne rfl
  | sub_eq hmem => simp [args] at hmem
  | sub_lt hmem _ => simp [args] at hmem
  | prec hr _ _ _ => simp [root] at hr
  | lex hr _ _ _ => simp [root] at hr

/-- The base rule `F(x, y, Z) -> x` is oriented under every precedence:
    `x` is an argument of the left side. -/
theorem lpo_orients_base (P : Sym → Sym → Prop) (x y : SKTerm) :
    LPO P (f x y z) x :=
  LPO.sub_eq (by simp [args])

theorem lpo_s_arg (P : Sym → Sym → Prop) (n : SKTerm) : LPO P (s n) n :=
  LPO.sub_eq (by simp [args])

/-- Sufficiency: with `F` above `G`, the recursive rule is oriented. Every other
    comparison inside the derivation is a subterm step or the same-symbol
    lexicographic step on the counter. -/
theorem lpo_orients_succ_of_F_gt_G (P : Sym → Sym → Prop) (hFG : P .f .g)
    (x y n : SKTerm) :
    LPO P (f x y (s n)) (g y (f x y n)) := by
  refine LPO.prec (ft := .f) (fu := .g) rfl rfl hFG ?_
  intro b hb
  simp only [args, List.mem_cons, List.mem_nil_iff, or_false] at hb
  rcases hb with hb | hb
  · subst hb
    exact LPO.sub_eq (by simp [args])
  · subst hb
    refine LPO.lex (ft := .f) rfl rfl ?_ ?_
    · intro c hc
      simp only [args, List.mem_cons, List.mem_nil_iff, or_false] at hc
      rcases hc with hc | hc | hc
      · subst hc
        exact LPO.sub_eq (by simp [args])
      · subst hc
        exact LPO.sub_eq (by simp [args])
      · subst hc
        exact LPO.sub_lt (a := s c) (by simp [args]) (lpo_s_arg P c)
    · simp only [args]
      exact LexLPO.tail (LexLPO.tail (LexLPO.head (lpo_s_arg P n)))

/-- `S(v2)` is not `LPO`-above `v1` for a distinct variable `v1`. -/
theorem not_lpo_s_var2_var1 (P : Sym → Sym → Prop) :
    ¬ LPO P (s (var 2)) (var 1) := by
  intro h
  cases h with
  | var_below _ hocc => simp [occurs] at hocc
  | sub_eq hmem => simp [args] at hmem
  | sub_lt hmem h =>
      simp only [args, List.mem_cons, List.mem_nil_iff, or_false] at hmem
      subst hmem
      exact not_lpo_var_left P 2 _ h
  | prec _ hru _ _ => simp [root] at hru
  | lex _ hru _ _ => simp [root] at hru

/-- `S(v2)` is not `LPO`-above the right side of the recursive rule at the
    variable instance, whatever the precedence says about `S`. -/
theorem not_lpo_s_var2_rhs (P : Sym → Sym → Prop) :
    ¬ LPO P (s (var 2)) (g (var 1) (f (var 0) (var 1) (var 2))) := by
  intro h
  cases h with
  | sub_eq hmem => simp [args] at hmem
  | sub_lt hmem h =>
      simp only [args, List.mem_cons, List.mem_nil_iff, or_false] at hmem
      subst hmem
      exact not_lpo_var_left P 2 _ h
  | prec _ _ _ hall =>
      exact not_lpo_s_var2_var1 P (hall (var 1) (by simp [args]))
  | lex hrt hru _ _ =>
      simp only [root, Option.some.injEq] at hrt hru
      subst hrt
      cases hru

/-- Necessity: if the lexicographic path order orients the recursive rule at
    the variable instance, the precedence puts `F` above `G`. -/
theorem F_gt_G_of_lpo_orients_succ (P : Sym → Sym → Prop)
    (h : LPO P (f (var 0) (var 1) (s (var 2))) (g (var 1) (f (var 0) (var 1) (var 2)))) :
    P .f .g := by
  cases h with
  | sub_eq hmem => simp [args] at hmem
  | sub_lt hmem h =>
      simp only [args, List.mem_cons, List.mem_nil_iff, or_false] at hmem
      rcases hmem with hmem | hmem | hmem
      · subst hmem
        exact absurd h (not_lpo_var_left P 0 _)
      · subst hmem
        exact absurd h (not_lpo_var_left P 1 _)
      · subst hmem
        exact absurd h (not_lpo_s_var2_rhs P)
  | prec hrt hru hP _ =>
      simp only [root, Option.some.injEq] at hrt hru
      subst hrt
      subst hru
      exact hP
  | lex hrt hru _ _ =>
      simp only [root, Option.some.injEq] at hrt hru
      subst hrt
      cases hru

/-- Both rules oriented, as a predicate on precedences. -/
def OrientsBothRules (P : Sym → Sym → Prop) : Prop :=
  (∀ x y : SKTerm, LPO P (f x y z) x) ∧
  (∀ x y n : SKTerm, LPO P (f x y (s n)) (g y (f x y n)))

/-- The demarcation theorem for the precedence route: the lexicographic path
    order orients both rules if and only if the precedence puts `F` above `G`.
    Nothing else about the precedence is determined by the rules. -/
theorem orientsBothRules_iff (P : Sym → Sym → Prop) :
    OrientsBothRules P ↔ P .f .g := by
  constructor
  · intro h
    exact F_gt_G_of_lpo_orients_succ P (h.2 _ _ _)
  · intro hFG
    exact ⟨lpo_orients_base P, lpo_orients_succ_of_F_gt_G P hFG⟩

/-- The minimal precedence, one comparison only, already orients both rules. -/
theorem minimal_precedence_orients :
    OrientsBothRules (fun a b => a = Sym.f ∧ b = Sym.g) :=
  (orientsBothRules_iff _).2 ⟨rfl, rfl⟩

/-- The empty precedence orients the base rule and not the recursive rule. -/
theorem empty_precedence_fails :
    ¬ OrientsBothRules (fun _ _ => False) := by
  intro h
  exact (orientsBothRules_iff _).1 h

/-! ## 3. Counting total orders -/

/-- The four symbols as a list. -/
def symList : List Sym := [.z, .s, .g, .f]

/-- Every list of four symbols, in a fixed enumeration order. -/
def allQuadruples : List (List Sym) :=
  symList.flatMap fun a =>
    symList.flatMap fun b =>
      symList.flatMap fun c =>
        symList.map fun d => [a, b, c, d]

/-- Distinctness test for a four-element list. -/
def distinct4 : List Sym → Bool
  | [a, b, c, d] => a != b && a != c && a != d && b != c && b != d && c != d
  | _ => false

/-- The 24 total orders, each written with its top symbol first. -/
def totalOrders : List (List Sym) := allQuadruples.filter distinct4

/-- Position of a symbol in an order list; the head has position 0. -/
def pos : List Sym → Sym → Nat
  | [], _ => 0
  | a :: l, b => if a = b then 0 else pos l b + 1

/-- The strict precedence induced by an order list: earlier means higher. -/
def precOf (l : List Sym) (a b : Sym) : Prop := pos l a < pos l b

instance (l : List Sym) (a b : Sym) : Decidable (precOf l a b) := by
  unfold precOf
  infer_instance

theorem totalOrders_length : totalOrders.length = 24 := by decide

/-- 12 of the 24 total orders put `F` above `G`. -/
theorem count_F_above_G :
    (totalOrders.filter fun l => decide (precOf l .f .g)).length = 12 := by decide

/-- Under a total order, the lexicographic path order orients both rules
    exactly when the order lists `F` before `G`. -/
theorem orients_iff_F_before_G (l : List Sym) :
    OrientsBothRules (precOf l) ↔ precOf l .f .g :=
  orientsBothRules_iff (precOf l)

open Classical in
/-- The 12 orienting total orders, counted through the demarcation theorem.
    `OrientsBothRules` quantifies over terms, so its decidability is classical;
    the count itself is the computable `count_F_above_G`. -/
theorem count_orienting_total_orders :
    (totalOrders.filter fun l => decide (OrientsBothRules (precOf l))).length = 12 := by
  have hfun : (fun l => decide (OrientsBothRules (precOf l)))
      = (fun l => decide (precOf l .f .g)) := by
    funext l
    exact decide_eq_decide.mpr (orients_iff_F_before_G l)
  rw [hfun]
  exact count_F_above_G

end KO7Benchmark.PaperB.Demarcation
