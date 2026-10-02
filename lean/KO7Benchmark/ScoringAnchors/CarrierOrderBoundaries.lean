/- 
  Carrier-order interpretation boundaries for the schema scorer.

  Relation: the duplicating SchemaKernel root relation and its actual contextual
    closure Step; SANSKernel is used only for exact copy-removal controls.
  Closure: recursive-root orientation is kept separate from full contextual
    orientation. Tropical and arctic controls name only the one-dimensional
    linear subfamilies formalized here. Finite-carrier results use the exact
    strictly monotone algebra clauses.
  Property: exact min-plus and max-plus one-dimensional linear interpretations
    have recursive-root orienters but no member orients every Schema context.
    Their admissibility laws witness the intended finite-valued method domain,
    while the context barrier itself needs no extra coefficient hypothesis.
    Exact strictly monotone finite-carrier algebras cannot orient the recursive
    rule, with one countermodel for each consumed premise. SANS unary-G controls
    show why the two-sided wrapper contradiction is not transferred to the
    copy-removed signature.
  Trust: Mathlib and the two benchmark kernels only; kernel-checked declarations.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SANSTests.SANSKernel

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.CarrierOrderBoundaries

open KO7Benchmark.SchemaTests
open KO7Benchmark.SchemaTests.SKTerm

namespace Tropical1D

abbrev Val := WithTop Nat

structure Data where
  z0 : Val
  sA : Val
  sC : Val
  gL : Val
  gR : Val
  gC : Val
  fX : Val
  fY : Val
  fN : Val
  fC : Val

def Data.sVal (M : Data) (x : Val) : Val := min (M.sA + x) M.sC

def Data.gVal (M : Data) (x y : Val) : Val :=
  min (min (M.gL + x) (M.gR + y)) M.gC

def Data.fVal (M : Data) (x y n : Val) : Val :=
  min (min (min (M.fX + x) (M.fY + y)) (M.fN + n)) M.fC

def Data.eval (M : Data) (rho : Nat -> Val) : SKTerm -> Val
  | .var i => rho i
  | .z => M.z0
  | .s t => M.sVal (M.eval rho t)
  | .g a b => M.gVal (M.eval rho a) (M.eval rho b)
  | .f x y n => M.fVal (M.eval rho x) (M.eval rho y) (M.eval rho n)

def Finite (x : Val) : Prop := x ≠ (⊤ : Val)

def Lt (x y : Val) : Prop := x < y

structure Laws (M : Data) : Prop where
  z_fin : M.z0 ≠ (⊤ : Val)
  s_sf : M.sC ≠ (⊤ : Val) ∨ M.sA ≠ (⊤ : Val)
  g_sf : M.gC ≠ (⊤ : Val) ∨ M.gL ≠ (⊤ : Val) ∨ M.gR ≠ (⊤ : Val)
  f_sf :
    M.fC ≠ (⊤ : Val) ∨ M.fX ≠ (⊤ : Val) ∨
      M.fY ≠ (⊤ : Val) ∨ M.fN ≠ (⊤ : Val)

def Data.OrientsRecursiveRoot (M : Data) : Prop :=
  ∀ rho : Nat -> Val, (∀ i, Finite (rho i)) ->
    ∀ x y n : SKTerm,
      Lt (M.eval rho (.g y (.f x y n)))
        (M.eval rho (.f x y (.s n)))

def Data.OrientsStep (M : Data) : Prop :=
  ∀ rho : Nat -> Val, (∀ i, Finite (rho i)) ->
    ∀ {t u : SKTerm}, Step t u -> Lt (M.eval rho u) (M.eval rho t)

private theorem add_finite {a b : Val} (ha : a ≠ (⊤ : Val))
    (hb : b ≠ (⊤ : Val)) : a + b ≠ (⊤ : Val) := by
  obtain ⟨m, rfl⟩ := WithTop.ne_top_iff_exists.1 ha
  obtain ⟨n, rfl⟩ := WithTop.ne_top_iff_exists.1 hb
  simp

private theorem eval_finite (M : Data) (hM : Laws M) (rho : Nat -> Val)
    (hrho : ∀ i, Finite (rho i)) (t : SKTerm) : Finite (M.eval rho t) := by
  induction t with
  | var i => exact hrho i
  | z => exact hM.z_fin
  | s t ih =>
      simp only [Data.eval, Data.sVal]
      rcases hM.s_sf with hc | ha
      · exact ne_top_of_le_ne_top hc (min_le_right _ _)
      · exact ne_top_of_le_ne_top (add_finite ha ih) (min_le_left _ _)
  | g a b iha ihb =>
      simp only [Data.eval, Data.gVal]
      rcases hM.g_sf with hc | ha | hb
      · exact ne_top_of_le_ne_top hc (min_le_right _ _)
      · exact ne_top_of_le_ne_top (add_finite ha iha)
          (le_trans (min_le_left _ _) (min_le_left _ _))
      · exact ne_top_of_le_ne_top (add_finite hb ihb)
          (le_trans (min_le_left _ _) (min_le_right _ _))
  | f x y n ihx ihy ihn =>
      simp only [Data.eval, Data.fVal]
      rcases hM.f_sf with hc | hx | hy | hn
      · exact ne_top_of_le_ne_top hc (min_le_right _ _)
      · exact ne_top_of_le_ne_top (add_finite hx ihx)
          (le_trans (min_le_left _ _) (le_trans (min_le_left _ _) (min_le_left _ _)))
      · exact ne_top_of_le_ne_top (add_finite hy ihy)
          (le_trans (min_le_left _ _) (le_trans (min_le_left _ _) (min_le_right _ _)))
      · exact ne_top_of_le_ne_top (add_finite hn ihn)
          (le_trans (min_le_left _ _) (min_le_right _ _))

private theorem min3_lt_right {A : Type} [LinearOrder A] {p q q' c : A}
    (h : min (min p q') c < min (min p q) c) : q' < p := by
  by_contra hp
  push_neg at hp
  have hle : min (min p q) c ≤ min (min p q') c :=
    min_le_min (by rw [min_eq_left hp]; exact min_le_left p q) le_rfl
  exact (not_lt_of_ge hle) h

private theorem min3_lt_left {A : Type} [LinearOrder A] {p p' q c : A}
    (h : min (min p' q) c < min (min p q) c) : p' < q := by
  by_contra hq
  push_neg at hq
  have hle : min (min p q) c ≤ min (min p' q) c :=
    min_le_min (by rw [min_eq_right hq]; exact min_le_right p q) le_rfl
  exact (not_lt_of_ge hle) h

theorem contextual_barrier (M : Data) : ¬ M.OrientsStep := by
  intro h
  let rho : Nat -> Val := fun _ => (0 : Nat)
  have hrho : ∀ i, Finite (rho i) := by
    intro i
    exact WithTop.coe_ne_top
  let src : SKTerm := .f .z .z (.s .z)
  let tgt : SKTerm := .g .z (.f .z .z .z)
  have hs : Step src tgt := Step.root (RootStep.succ .z .z .z)
  have hright := h rho hrho (Step.g_right (a := tgt) hs)
  have hleft := h rho hrho (Step.g_left (b := tgt) hs)
  change
    min (min (M.gL + M.eval rho tgt) (M.gR + M.eval rho tgt)) M.gC <
      min (min (M.gL + M.eval rho tgt) (M.gR + M.eval rho src)) M.gC at hright
  change
    min (min (M.gL + M.eval rho tgt) (M.gR + M.eval rho tgt)) M.gC <
      min (min (M.gL + M.eval rho src) (M.gR + M.eval rho tgt)) M.gC at hleft
  have hR : M.gR + M.eval rho tgt < M.gL + M.eval rho tgt :=
    min3_lt_right hright
  have hL : M.gL + M.eval rho tgt < M.gR + M.eval rho tgt :=
    min3_lt_left hleft
  exact lt_asymm hR hL

def rootWitness : Data where
  z0 := 0
  sA := 1
  sC := ⊤
  gL := ⊤
  gR := 0
  gC := ⊤
  fX := ⊤
  fY := ⊤
  fN := 0
  fC := ⊤

theorem rootWitness_laws : Laws rootWitness := by
  constructor
  · exact WithTop.coe_ne_top
  · exact Or.inr WithTop.coe_ne_top
  · exact Or.inr (Or.inr WithTop.coe_ne_top)
  · exact Or.inr (Or.inr (Or.inr WithTop.coe_ne_top))

theorem finite_lt_one_add {x : Val} (hx : x ≠ (⊤ : Val)) :
    x < 1 + x := by
  obtain ⟨k, rfl⟩ := WithTop.ne_top_iff_exists.1 hx
  simpa using (WithTop.coe_lt_coe.2 (show k < 1 + k by omega))

theorem rootWitness_orients_recursive :
    rootWitness.OrientsRecursiveRoot := by
  intro rho hrho x y n
  have hn : Finite (rootWitness.eval rho n) :=
    eval_finite rootWitness rootWitness_laws rho hrho n
  simpa [Lt, Data.eval, Data.gVal, Data.fVal, Data.sVal, rootWitness] using
    finite_lt_one_add hn

def topDegenerate : Data where
  z0 := ⊤
  sA := ⊤
  sC := ⊤
  gL := ⊤
  gR := ⊤
  gC := ⊤
  fX := ⊤
  fY := ⊤
  fN := ⊤
  fC := ⊤

theorem topDegenerate_not_laws : ¬ Laws topDegenerate := by
  intro h
  exact h.z_fin rfl


end Tropical1D

namespace Arctic1D

abbrev Val := WithBot Nat

structure Data where
  z0 : Val
  sA : Val
  sC : Val
  gL : Val
  gR : Val
  gC : Val
  fX : Val
  fY : Val
  fN : Val
  fC : Val

def Data.sVal (M : Data) (x : Val) : Val := max (M.sA + x) M.sC

def Data.gVal (M : Data) (x y : Val) : Val :=
  max (max (M.gL + x) (M.gR + y)) M.gC

def Data.fVal (M : Data) (x y n : Val) : Val :=
  max (max (max (M.fX + x) (M.fY + y)) (M.fN + n)) M.fC

def Data.eval (M : Data) (rho : Nat -> Val) : SKTerm -> Val
  | .var i => rho i
  | .z => M.z0
  | .s t => M.sVal (M.eval rho t)
  | .g a b => M.gVal (M.eval rho a) (M.eval rho b)
  | .f x y n => M.fVal (M.eval rho x) (M.eval rho y) (M.eval rho n)

def Finite (x : Val) : Prop := x ≠ (⊥ : Val)

def Lt (x y : Val) : Prop := x < y

structure Laws (M : Data) : Prop where
  z_fin : M.z0 ≠ (⊥ : Val)
  s_sf : M.sC ≠ (⊥ : Val) ∨ M.sA ≠ (⊥ : Val)
  g_sf : M.gC ≠ (⊥ : Val) ∨ M.gL ≠ (⊥ : Val) ∨ M.gR ≠ (⊥ : Val)
  f_sf :
    M.fC ≠ (⊥ : Val) ∨ M.fX ≠ (⊥ : Val) ∨
      M.fY ≠ (⊥ : Val) ∨ M.fN ≠ (⊥ : Val)

def Data.OrientsRecursiveRoot (M : Data) : Prop :=
  ∀ rho : Nat -> Val, (∀ i, Finite (rho i)) ->
    ∀ x y n : SKTerm,
      Lt (M.eval rho (.g y (.f x y n)))
        (M.eval rho (.f x y (.s n)))

def Data.OrientsStep (M : Data) : Prop :=
  ∀ rho : Nat -> Val, (∀ i, Finite (rho i)) ->
    ∀ {t u : SKTerm}, Step t u -> Lt (M.eval rho u) (M.eval rho t)

private theorem add_finite {a b : Val} (ha : a ≠ (⊥ : Val))
    (hb : b ≠ (⊥ : Val)) : a + b ≠ (⊥ : Val) := by
  obtain ⟨m, rfl⟩ := WithBot.ne_bot_iff_exists.1 ha
  obtain ⟨n, rfl⟩ := WithBot.ne_bot_iff_exists.1 hb
  simp

private theorem eval_finite (M : Data) (hM : Laws M) (rho : Nat -> Val)
    (hrho : ∀ i, Finite (rho i)) (t : SKTerm) : Finite (M.eval rho t) := by
  induction t with
  | var i => exact hrho i
  | z => exact hM.z_fin
  | s t ih =>
      simp only [Data.eval, Data.sVal]
      rcases hM.s_sf with hc | ha
      · exact ne_bot_of_le_ne_bot hc (le_max_right _ _)
      · exact ne_bot_of_le_ne_bot (add_finite ha ih) (le_max_left _ _)
  | g a b iha ihb =>
      simp only [Data.eval, Data.gVal]
      rcases hM.g_sf with hc | ha | hb
      · exact ne_bot_of_le_ne_bot hc (le_max_right _ _)
      · exact ne_bot_of_le_ne_bot (add_finite ha iha)
          (le_trans (le_max_left _ _) (le_max_left _ _))
      · exact ne_bot_of_le_ne_bot (add_finite hb ihb)
          (le_trans (le_max_right _ _) (le_max_left _ _))
  | f x y n ihx ihy ihn =>
      simp only [Data.eval, Data.fVal]
      rcases hM.f_sf with hc | hx | hy | hn
      · exact ne_bot_of_le_ne_bot hc (le_max_right _ _)
      · exact ne_bot_of_le_ne_bot (add_finite hx ihx)
          (le_trans (le_max_left _ _) (le_trans (le_max_left _ _) (le_max_left _ _)))
      · exact ne_bot_of_le_ne_bot (add_finite hy ihy)
          (le_trans (le_max_right _ _) (le_trans (le_max_left _ _) (le_max_left _ _)))
      · exact ne_bot_of_le_ne_bot (add_finite hn ihn)
          (le_trans (le_max_right _ _) (le_max_left _ _))

private theorem exists_nat_ge (x : Val) : ∃ B : Nat, x ≤ (B : Val) := by
  by_cases hx : x = (⊥ : Val)
  · subst x
    exact ⟨0, bot_le⟩
  · obtain ⟨n, rfl⟩ := WithBot.ne_bot_iff_exists.1 hx
    exact ⟨n, le_rfl⟩

private theorem coe_le_add (q : Nat) (y : Val) : y ≤ (q : Val) + y := by
  by_cases hy : y = (⊥ : Val)
  · subst y
    exact bot_le
  · obtain ⟨n, rfl⟩ := WithBot.ne_bot_iff_exists.1 hy
    simpa using (WithBot.coe_le_coe.2 (Nat.le_add_left n q))

theorem contextual_barrier (M : Data) : ¬ M.OrientsStep := by
  intro h
  let src : SKTerm := .f .z .z (.s .z)
  let tgt : SKTerm := .g .z (.f .z .z .z)
  have hs : Step src tgt := Step.root (RootStep.succ .z .z .z)
  by_cases hL : M.gL = (⊥ : Val)
  · let rho : Nat -> Val := fun _ => (0 : Nat)
    have hrho : ∀ i, Finite (rho i) := by
      intro i
      exact WithBot.coe_ne_bot
    have hctx := h rho hrho (Step.g_left (b := .z) hs)
    have heq : M.eval rho (.g tgt .z) = M.eval rho (.g src .z) := by
      simp [Data.eval, Data.gVal, hL]
    rw [heq] at hctx
    exact (lt_irrefl _) hctx
  · obtain ⟨p, hp⟩ := WithBot.ne_bot_iff_exists.1 hL
    let rho0 : Nat -> Val := fun _ => (0 : Nat)
    have hrho0 : ∀ i, Finite (rho0 i) := by
      intro i
      exact WithBot.coe_ne_bot
    let aSrc : Val := M.eval rho0 src
    let aTgt : Val := M.eval rho0 tgt
    obtain ⟨B1, hB1⟩ := exists_nat_ge (M.gR + aSrc)
    obtain ⟨B2, hB2⟩ := exists_nat_ge (M.gR + aTgt)
    obtain ⟨B3, hB3⟩ := exists_nat_ge M.gC
    let K : Nat := B1 + B2 + B3
    let rhoK : Nat -> Val := fun _ => (K : Nat)
    have hrhoK : ∀ i, Finite (rhoK i) := by
      intro i
      exact WithBot.coe_ne_bot
    have src_closed : M.eval rhoK src = aSrc := by
      simp [src, aSrc, rho0, Data.eval]
    have tgt_closed : M.eval rhoK tgt = aTgt := by
      simp [tgt, aTgt, rho0, Data.eval]
    have hK : (K : Val) ≤ M.gL + (K : Val) := by
      rw [← hp]
      exact coe_le_add p (K : Val)
    have hB1K : B1 ≤ K := by
      dsimp [K]
      omega
    have hB2K : B2 ≤ K := by
      dsimp [K]
      omega
    have hB3K : B3 ≤ K := by
      dsimp [K]
      omega
    have hsrc : M.gR + M.eval rhoK src ≤ M.gL + (K : Val) := by
      rw [src_closed]
      exact le_trans hB1 (le_trans (WithBot.coe_le_coe.2 hB1K) hK)
    have htgt : M.gR + M.eval rhoK tgt ≤ M.gL + (K : Val) := by
      rw [tgt_closed]
      exact le_trans hB2 (le_trans (WithBot.coe_le_coe.2 hB2K) hK)
    have hc : M.gC ≤ M.gL + (K : Val) :=
      le_trans hB3 (le_trans (WithBot.coe_le_coe.2 hB3K) hK)
    have eSrc : M.eval rhoK (.g (.var 3) src) = M.gL + (K : Val) := by
      simp only [Data.eval, Data.gVal]
      change max (max (M.gL + (K : Val)) (M.gR + M.eval rhoK src)) M.gC =
        M.gL + (K : Val)
      rw [max_eq_left hsrc, max_eq_left hc]
    have eTgt : M.eval rhoK (.g (.var 3) tgt) = M.gL + (K : Val) := by
      simp only [Data.eval, Data.gVal]
      change max (max (M.gL + (K : Val)) (M.gR + M.eval rhoK tgt)) M.gC =
        M.gL + (K : Val)
      rw [max_eq_left htgt, max_eq_left hc]
    have hctx := h rhoK hrhoK (Step.g_right (a := .var 3) hs)
    rw [eTgt, eSrc] at hctx
    exact (lt_irrefl _) hctx

def rootWitness : Data where
  z0 := 0
  sA := 0
  sC := ⊥
  gL := 0
  gR := ⊥
  gC := ⊥
  fX := ⊥
  fY := 1
  fN := ⊥
  fC := ⊥

theorem rootWitness_laws : Laws rootWitness := by
  constructor
  · exact WithBot.coe_ne_bot
  · exact Or.inr WithBot.coe_ne_bot
  · exact Or.inr (Or.inl WithBot.coe_ne_bot)
  · exact Or.inr (Or.inr (Or.inl WithBot.coe_ne_bot))

theorem finite_lt_one_add {x : Val} (hx : x ≠ (⊥ : Val)) :
    x < 1 + x := by
  obtain ⟨k, rfl⟩ := WithBot.ne_bot_iff_exists.1 hx
  simpa using (WithBot.coe_lt_coe.2 (show k < 1 + k by omega))

theorem rootWitness_orients_recursive :
    rootWitness.OrientsRecursiveRoot := by
  intro rho hrho x y n
  have hy : Finite (rootWitness.eval rho y) :=
    eval_finite rootWitness rootWitness_laws rho hrho y
  simpa [Lt, Data.eval, Data.gVal, Data.fVal, Data.sVal, rootWitness] using
    finite_lt_one_add hy

def botDegenerate : Data where
  z0 := ⊥
  sA := ⊥
  sC := ⊥
  gL := ⊥
  gR := ⊥
  gC := ⊥
  fX := ⊥
  fY := ⊥
  fN := ⊥
  fC := ⊥

theorem botDegenerate_not_laws : ¬ Laws botDegenerate := by
  intro h
  exact h.z_fin rfl


end Arctic1D

namespace FiniteCarrier

structure Interpretation (A : Type) where
  z : A
  s : A -> A
  g : A -> A -> A
  f : A -> A -> A -> A

structure StrictContextLaws {A : Type} (I : Interpretation A)
    (lt : A -> A -> Prop) : Prop where
  s : ∀ {x y}, lt x y -> lt (I.s x) (I.s y)
  gLeft : ∀ {x y} z, lt x y -> lt (I.g x z) (I.g y z)
  gRight : ∀ z {x y}, lt x y -> lt (I.g z x) (I.g z y)
  fX : ∀ {x y} s n, lt x y -> lt (I.f x s n) (I.f y s n)
  fY : ∀ b {x y} n, lt x y -> lt (I.f b x n) (I.f b y n)
  fN : ∀ b s {x y}, lt x y -> lt (I.f b s x) (I.f b s y)

def RecursiveRootOrients {A : Type} (I : Interpretation A)
    (lt : A -> A -> Prop) : Prop :=
  ∀ b s n, lt (I.g s (I.f b s n)) (I.f b s (I.s n))

open Classical in
noncomputable def belowCount {A : Type} [Fintype A]
    (lt : A -> A -> Prop) (x : A) : Nat :=
  (Finset.univ.filter (fun y => lt y x)).card

private theorem belowCount_lt {A : Type} [Fintype A] (lt : A -> A -> Prop)
    (hirr : ∀ x, ¬ lt x x)
    (htrans : ∀ x y z, lt x y -> lt y z -> lt x z)
    {x y : A} (h : lt x y) :
    belowCount lt x < belowCount lt y := by
  classical
  unfold belowCount
  apply Finset.card_lt_card
  rw [Finset.ssubset_iff_of_subset]
  · exact ⟨x, by simp [h], by simp [hirr x]⟩
  · intro z hz
    simp only [Finset.mem_filter, Finset.mem_univ, true_and] at hz ⊢
    exact htrans z x y hz h

private theorem belowCount_le {A : Type} [Fintype A]
    (lt : A -> A -> Prop) (x : A) :
    belowCount lt x ≤ Fintype.card A := by
  classical
  unfold belowCount
  exact le_trans (Finset.card_filter_le _ _) (le_of_eq Finset.card_univ)

theorem finite_strict_recursive_barrier {A : Type} [Fintype A]
    (I : Interpretation A) (lt : A -> A -> Prop)
    (hirr : ∀ x, ¬ lt x x)
    (htrans : ∀ x y z, lt x y -> lt y z -> lt x z)
    (hgRight : ∀ z {x y}, lt x y -> lt (I.g z x) (I.g z y)) :
    ¬ RecursiveRootOrients I lt := by
  intro hor
  have hit : ∀ (i : Nat) {x y : A}, lt x y ->
      lt ((I.g I.z)^[i] x) ((I.g I.z)^[i] y) := by
    intro i
    induction i with
    | zero =>
        intro x y hxy
        exact hxy
    | succ i ih =>
        intro x y hxy
        rw [Function.iterate_succ_apply', Function.iterate_succ_apply']
        exact hgRight I.z (ih hxy)
  have key : ∀ k i : Nat,
      k ≤ belowCount lt ((I.g I.z)^[i] (I.f I.z I.z ((I.s)^[k] I.z))) := by
    intro k
    induction k with
    | zero =>
        intro i
        exact Nat.zero_le _
    | succ k ih =>
        intro i
        have h1 := belowCount_lt lt hirr htrans
          (hit i (hor I.z I.z ((I.s)^[k] I.z)))
        have h2 := ih (i + 1)
        rw [Function.iterate_succ_apply] at h2
        rw [Function.iterate_succ_apply']
        omega
  have h3 := key (Fintype.card A + 1) 0
  have h4 := belowCount_le lt
    ((I.g I.z)^[0] (I.f I.z I.z ((I.s)^[Fintype.card A + 1] I.z)))
  omega

structure Data where
  k : Nat
  interp : Interpretation (Fin (k + 1))
  lt : Fin (k + 1) -> Fin (k + 1) -> Prop

structure Laws (M : Data) : Prop where
  irrefl : ∀ x, ¬ M.lt x x
  trans : ∀ x y z, M.lt x y -> M.lt y z -> M.lt x z
  strict_mono : StrictContextLaws M.interp M.lt

def Data.Accepts (M : Data) : Prop :=
  RecursiveRootOrients M.interp M.lt

def Data.Result (M : Data) : Prop := ¬ M.Accepts

theorem universal_barrier (M : Data) (hM : Laws M) : M.Result :=
  finite_strict_recursive_barrier M.interp M.lt hM.irrefl hM.trans
    hM.strict_mono.gRight

def witness : Data where
  k := 0
  interp := { z := 0, s := fun _ => 0, g := fun _ _ => 0, f := fun _ _ _ => 0 }
  lt := fun _ _ => False

theorem witness_laws : Laws witness := by
  refine ⟨?_, ?_, ?_⟩
  · intro x h
    exact h
  · intro x y z hxy hyz
    exact False.elim hxy
  · exact {
      s := by intro x y h; exact False.elim h
      gLeft := by intro x y z h; exact False.elim h
      gRight := by intro z x y h; exact False.elim h
      fX := by intro x y s n h; exact False.elim h
      fY := by intro b x y n h; exact False.elim h
      fN := by intro b s x y h; exact False.elim h }

theorem witness_result : witness.Result :=
  universal_barrier witness witness_laws

def mutation : Data :=
  { witness with lt := fun _ _ => True }

theorem mutation_accepts : mutation.Accepts := by
  intro b s n
  trivial

theorem mutation_trans :
    ∀ x y z, mutation.lt x y -> mutation.lt y z -> mutation.lt x z := by
  intro x y z hxy hyz
  trivial

theorem mutation_gRight :
    ∀ z {x y}, mutation.lt x y ->
      mutation.lt (mutation.interp.g z x) (mutation.interp.g z y) := by
  intro z x y hxy
  trivial

theorem mutation_not_irrefl : ¬ (∀ x, ¬ mutation.lt x x) := by
  intro h
  exact h 0 trivial

theorem irrefl_is_load_bearing :
    mutation.Accepts ∧
      (∀ x y z, mutation.lt x y -> mutation.lt y z -> mutation.lt x z) ∧
      (∀ z {x y}, mutation.lt x y ->
        mutation.lt (mutation.interp.g z x) (mutation.interp.g z y)) ∧
      ¬ (∀ x, ¬ mutation.lt x x) :=
  ⟨mutation_accepts, mutation_trans, mutation_gRight, mutation_not_irrefl⟩

def cycleSucc (x : Fin 3) : Fin 3 :=
  ⟨(x.val + 1) % 3, Nat.mod_lt _ (by decide)⟩

def cycleLt (x y : Fin 3) : Prop := y = cycleSucc x

def nontransitiveInterp : Interpretation (Fin 3) where
  z := 0
  s := cycleSucc
  g := fun _ y => y
  f := fun _ _ n => n

theorem cycleLt_irrefl : ∀ x, ¬ cycleLt x x := by
  intro x
  fin_cases x <;> simp [cycleLt, cycleSucc]

theorem cycleLt_not_transitive :
    ¬ (∀ x y z, cycleLt x y -> cycleLt y z -> cycleLt x z) := by
  intro h
  have h01 : cycleLt 0 1 := by simp [cycleLt, cycleSucc]
  have h12 : cycleLt 1 2 := by simp [cycleLt, cycleSucc]
  have h02 := h 0 1 2 h01 h12
  have hn02 : ¬ cycleLt 0 2 := by simp [cycleLt, cycleSucc]
  exact hn02 h02

theorem nontransitive_gRight :
    ∀ z {x y}, cycleLt x y ->
      cycleLt (nontransitiveInterp.g z x) (nontransitiveInterp.g z y) := by
  intro z x y hxy
  simpa [nontransitiveInterp] using hxy

theorem nontransitive_orients :
    RecursiveRootOrients nontransitiveInterp cycleLt := by
  intro b s n
  change cycleLt n (cycleSucc n)
  rfl

theorem transitivity_is_load_bearing :
    RecursiveRootOrients nontransitiveInterp cycleLt ∧
      (∀ x, ¬ cycleLt x x) ∧
      (∀ z {x y}, cycleLt x y ->
        cycleLt (nontransitiveInterp.g z x) (nontransitiveInterp.g z y)) ∧
      ¬ (∀ x y z, cycleLt x y -> cycleLt y z -> cycleLt x z) :=
  ⟨nontransitive_orients, cycleLt_irrefl, nontransitive_gRight,
    cycleLt_not_transitive⟩

def fin2Lt (x y : Fin 2) : Prop := x.val < y.val

def nonmonotoneGInterp : Interpretation (Fin 2) where
  z := 0
  s := fun _ => 0
  g := fun _ _ => 0
  f := fun _ _ _ => 1

theorem fin2Lt_irrefl : ∀ x, ¬ fin2Lt x x := by
  intro x
  exact Nat.lt_irrefl x.val

theorem fin2Lt_trans :
    ∀ x y z, fin2Lt x y -> fin2Lt y z -> fin2Lt x z := by
  intro x y z hxy hyz
  exact Nat.lt_trans hxy hyz

theorem nonmonotoneG_orients :
    RecursiveRootOrients nonmonotoneGInterp fin2Lt := by
  intro b s n
  change (0 : Nat) < 1
  omega

theorem nonmonotoneG_not_gRight :
    ¬ (∀ z {x y}, fin2Lt x y ->
      fin2Lt (nonmonotoneGInterp.g z x) (nonmonotoneGInterp.g z y)) := by
  intro h
  have h01 : fin2Lt (0 : Fin 2) (1 : Fin 2) := by simp [fin2Lt]
  have hbad := h (0 : Fin 2) (x := (0 : Fin 2)) (y := (1 : Fin 2)) h01
  change (0 : Nat) < 0 at hbad
  exact (Nat.lt_irrefl 0) hbad

theorem gRight_is_load_bearing :
    RecursiveRootOrients nonmonotoneGInterp fin2Lt ∧
      (∀ x, ¬ fin2Lt x x) ∧
      (∀ x y z, fin2Lt x y -> fin2Lt y z -> fin2Lt x z) ∧
      ¬ (∀ z {x y}, fin2Lt x y ->
        fin2Lt (nonmonotoneGInterp.g z x) (nonmonotoneGInterp.g z y)) :=
  ⟨nonmonotoneG_orients, fin2Lt_irrefl, fin2Lt_trans,
    nonmonotoneG_not_gRight⟩

end FiniteCarrier

namespace SANSControl

open KO7Benchmark.SANSTests
open KO7Benchmark.SANSTests.SANSTerm

def tropicalEval (rho : Nat -> WithTop Nat) : SANSTerm -> WithTop Nat
  | .var i => rho i
  | .z => 0
  | .s t => 1 + tropicalEval rho t
  | .g t => tropicalEval rho t
  | .f _ _ n => tropicalEval rho n

def arcticEval (rho : Nat -> WithBot Nat) : SANSTerm -> WithBot Nat
  | .var i => rho i
  | .z => 0
  | .s t => 1 + arcticEval rho t
  | .g t => arcticEval rho t
  | .f _ _ n => arcticEval rho n

theorem tropicalEval_finite (rho : Nat -> WithTop Nat)
    (hrho : ∀ i, rho i ≠ (⊤ : WithTop Nat)) :
    ∀ t : SANSTerm, tropicalEval rho t ≠ (⊤ : WithTop Nat)
  | .var i => hrho i
  | .z => WithTop.coe_ne_top
  | .s t => by
      have ht := tropicalEval_finite rho hrho t
      obtain ⟨k, hk⟩ := WithTop.ne_top_iff_exists.1 ht
      simp only [tropicalEval]
      rw [← hk]
      simp
  | .g t => tropicalEval_finite rho hrho t
  | .f _ _ n => tropicalEval_finite rho hrho n

theorem arcticEval_finite (rho : Nat -> WithBot Nat)
    (hrho : ∀ i, rho i ≠ (⊥ : WithBot Nat)) :
    ∀ t : SANSTerm, arcticEval rho t ≠ (⊥ : WithBot Nat)
  | .var i => hrho i
  | .z => WithBot.coe_ne_bot
  | .s t => by
      have ht := arcticEval_finite rho hrho t
      obtain ⟨k, hk⟩ := WithBot.ne_bot_iff_exists.1 ht
      simp only [arcticEval]
      rw [← hk]
      simp
  | .g t => arcticEval_finite rho hrho t
  | .f _ _ n => arcticEval_finite rho hrho n

theorem tropical_recursive_root (rho : Nat -> WithTop Nat)
    (hrho : ∀ i, rho i ≠ (⊤ : WithTop Nat)) (x y n : SANSTerm) :
    Tropical1D.Lt (tropicalEval rho (.g (.f x y n)))
      (tropicalEval rho (.f x y (.s n))) := by
  simp only [tropicalEval]
  simpa [Tropical1D.Lt] using
    Tropical1D.finite_lt_one_add (tropicalEval_finite rho hrho n)

theorem tropical_unary_g_control (rho : Nat -> WithTop Nat)
    (hrho : ∀ i, rho i ≠ (⊤ : WithTop Nat)) (x y n : SANSTerm) :
    Tropical1D.Lt (tropicalEval rho (.g (.g (.f x y n))))
      (tropicalEval rho (.g (.f x y (.s n)))) := by
  simpa only [tropicalEval] using tropical_recursive_root rho hrho x y n

theorem arctic_recursive_root (rho : Nat -> WithBot Nat)
    (hrho : ∀ i, rho i ≠ (⊥ : WithBot Nat)) (x y n : SANSTerm) :
    Arctic1D.Lt (arcticEval rho (.g (.f x y n)))
      (arcticEval rho (.f x y (.s n))) := by
  simp only [arcticEval]
  simpa [Arctic1D.Lt] using
    Arctic1D.finite_lt_one_add (arcticEval_finite rho hrho n)

theorem arctic_unary_g_control (rho : Nat -> WithBot Nat)
    (hrho : ∀ i, rho i ≠ (⊥ : WithBot Nat)) (x y n : SANSTerm) :
    Arctic1D.Lt (arcticEval rho (.g (.g (.f x y n))))
      (arcticEval rho (.g (.f x y (.s n)))) := by
  simpa only [arcticEval] using arctic_recursive_root rho hrho x y n

end SANSControl

#print axioms Tropical1D.contextual_barrier
#print axioms Tropical1D.rootWitness_laws
#print axioms Tropical1D.finite_lt_one_add
#print axioms Tropical1D.rootWitness_orients_recursive
#print axioms Tropical1D.topDegenerate_not_laws
#print axioms Arctic1D.contextual_barrier
#print axioms Arctic1D.rootWitness_laws
#print axioms Arctic1D.finite_lt_one_add
#print axioms Arctic1D.rootWitness_orients_recursive
#print axioms Arctic1D.botDegenerate_not_laws
#print axioms FiniteCarrier.finite_strict_recursive_barrier
#print axioms FiniteCarrier.universal_barrier
#print axioms FiniteCarrier.witness_laws
#print axioms FiniteCarrier.witness_result
#print axioms FiniteCarrier.irrefl_is_load_bearing
#print axioms FiniteCarrier.transitivity_is_load_bearing
#print axioms FiniteCarrier.gRight_is_load_bearing
#print axioms SANSControl.tropicalEval_finite
#print axioms SANSControl.tropical_recursive_root
#print axioms SANSControl.tropical_unary_g_control
#print axioms SANSControl.arcticEval_finite
#print axioms SANSControl.arctic_recursive_root
#print axioms SANSControl.arctic_unary_g_control

end KO7Benchmark.ScoringAnchors.CarrierOrderBoundaries
