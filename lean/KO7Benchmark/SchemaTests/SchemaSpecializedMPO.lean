/-
  Schema-specialized MPO with NATIVE well-foundedness (slot C, Schema Test B
  New System).

  This is the schema-signature port of the Orientation Boundary artifact's
  KO7-specialized MPO (`OperatorKO7/Meta/MPO_FullStep.lean`, manuscript
  Proposition "KO7-specialized MPO full-step termination"): a fixed-signature
  multiset-style path order with

  * a subterm clause (direct and transitive);
  * a precedence clause for the fixed precedence F > G > S > Z > var;
  * a same-head clause for `f` restricted to the third (counter) argument,
    with the first two arguments required to agree syntactically. This is
    the multiset-status comparison specialized to this TRS: the recursive
    rule changes ONLY the third argument, so the multiset comparison
    {x, y, S(n)} >mul {x, y, n} degenerates to the single swapped element.

  Well-foundedness is NATIVE: a Veblen-hierarchy ordinal ranking `mpoOrd`
  strictly decreases along every MPO comparison, with no appeal to any
  polynomial or other Nat-valued system witness. This matches the proof-
  theoretic shape of the artifact's MPO (a direct fixed-signature ordinal
  ranking), specialized to the five-symbol schema signature.

  Relation: `RootStep` (the two root rules). Property: root termination by
  the specialized MPO, `wf_RootStepRev_mpo`.
  Proves: both root rules are MPO-oriented and the reverse MPO relation is
  well-founded by the native ordinal ranking.
  Does not prove: a generic MPO metatheorem over arbitrary signatures, and
  not context-closed termination BY THIS ORDER (the specialized relation
  carries no general congruence clauses; full contextual SN of this TRS is
  independently Lean-proven by the exact slot-B and slot-E interpretations
  and externally CeTA-certified). This mirrors the Orientation Boundary
  paper, whose KO7 MPO is likewise a root-relation result while context
  closure is carried by the polynomial witness.
  Trust: kernel-only; mathlib baseline axioms.
-/
import Mathlib.Order.WellFounded
import Mathlib.SetTheory.Ordinal.Arithmetic
import Mathlib.SetTheory.Ordinal.Exponential
import Mathlib.SetTheory.Ordinal.Principal
import Mathlib.SetTheory.Ordinal.Veblen
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.SchemaMPO

open KO7Benchmark.SchemaTests
open SKTerm
open scoped Ordinal

/-! ## Symbols, heads, arguments -/

inductive Sym : Type
  | var
  | z
  | s
  | g
  | f
deriving DecidableEq, Repr

@[simp] def sym : SKTerm → Sym
  | SKTerm.var _ => .var
  | SKTerm.z => .z
  | SKTerm.s _ => .s
  | SKTerm.g _ _ => .g
  | SKTerm.f _ _ _ => .f

@[simp] def args : SKTerm → List SKTerm
  | SKTerm.var _ => []
  | SKTerm.z => []
  | SKTerm.s t => [t]
  | SKTerm.g a b => [a, b]
  | SKTerm.f x y n => [x, y, n]

/-! ## Fixed precedence F > G > S > Z > var -/

@[simp] def rank : Sym → Nat
  | .var => 0
  | .z => 1
  | .s => 2
  | .g => 3
  | .f => 4

def symPrec (a b : Sym) : Prop := rank a < rank b

/-! ## Schema-specialized MPO relation -/

/-- `MPO s t` means `s` strictly dominates `t` in the specialized order.

Constructors:
- `subEq`: direct subterm.
- `subGt`: transitive subterm descent through an argument.
- `byPrec`: precedence domination with recursive domination of RHS arguments.
- `fArg`: same-head multiset-style clause on `f` (decrease in the third
  argument, first two arguments syntactically equal). -/
inductive MPO : SKTerm → SKTerm → Prop
  | subEq : ∀ {s u : SKTerm}, u ∈ args s → MPO s u
  | subGt : ∀ {s u t : SKTerm}, u ∈ args s → MPO u t → MPO s t
  | byPrec : ∀ {s t : SKTerm},
      symPrec (sym t) (sym s) →
      (∀ u, u ∈ args t → MPO s u) →
      MPO s t
  | fArg : ∀ {x y n n' : SKTerm},
      MPO n' n →
      MPO (f x y n') (f x y n)

/-! ## Root-rule orientation -/

theorem mpo_s_arg (n : SKTerm) : MPO (s n) n :=
  MPO.subEq (by simp [args])

/-- Base rule `F(x,y,Z) -> x`: subterm case. -/
theorem mpo_root_base (x y : SKTerm) : MPO (f x y z) x :=
  MPO.subEq (by simp [args])

/-- Same-head comparison for the recursive call: `S(n)` strictly dominates
`n`, so `F(x,y,S(n))` dominates `F(x,y,n)` by the specialized `f` clause. -/
theorem mpo_f_counter (x y n : SKTerm) :
    MPO (f x y (s n)) (f x y n) :=
  MPO.fArg (mpo_s_arg n)

/-- Recursive rule `F(x,y,S(n)) -> G(y, F(x,y,n))`: precedence case `F > G`
with both RHS arguments dominated (`y` by subterm; the recursive call by the
same-head counter clause). -/
theorem mpo_root_succ (x y n : SKTerm) :
    MPO (f x y (s n)) (g y (f x y n)) :=
  MPO.byPrec
    (s := f x y (s n)) (t := g y (f x y n))
    (by simp [symPrec, rank, sym])
    (by
      intro u hu
      have hu' : u = y ∨ u = f x y n := by
        simpa [args] using hu
      rcases hu' with rfl | rfl
      · exact MPO.subEq (by simp [args])
      · exact mpo_f_counter x y n)

/-- Both root rules of the schema kernel are MPO-oriented. -/
theorem mpo_orients_rootStep : ∀ {a b : SKTerm}, RootStep a b → MPO a b
  | _, _, RootStep.base x y => mpo_root_base x y
  | _, _, RootStep.succ x y n => mpo_root_succ x y n

/-! ## Ordinal ranking and native well-foundedness

The ranking maps each symbol to a Veblen value of its rank, over a payload
built from the argument ranks. Ported from the Orientation Boundary
artifact's `mpoOrd` (KO7 signature) to the five-symbol schema signature. -/

/-- Payload used for the binary constructor `g`. The outer successor keeps
the payload non-limit, so positive-rank Veblen values strictly dominate it. -/
@[simp] noncomputable def pairPayload (a b : Ordinal.{0}) : Ordinal.{0} :=
  Order.succ ((ω : Ordinal) ^ (Order.succ a) + b)

/-- Payload used for the ternary constructor `f`. -/
@[simp] noncomputable def triplePayload (a b c : Ordinal.{0}) : Ordinal.{0} :=
  Order.succ ((ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c)

/-- Ordinal ranking for the schema-specialized MPO. -/
@[simp] noncomputable def mpoOrd : SKTerm → Ordinal.{0}
  | SKTerm.var _ => Ordinal.veblen 0 0
  | SKTerm.z => Ordinal.veblen 1 0
  | SKTerm.s t => Ordinal.veblen 2 (Order.succ (mpoOrd t))
  | SKTerm.g a b => Ordinal.veblen 3 (pairPayload (mpoOrd a) (mpoOrd b))
  | SKTerm.f x y n => Ordinal.veblen 4 (triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n))

/-- The raw payload sitting under the Veblen head. -/
@[simp] noncomputable def payloadOrd : SKTerm → Ordinal.{0}
  | SKTerm.var _ => 0
  | SKTerm.z => 0
  | SKTerm.s t => Order.succ (mpoOrd t)
  | SKTerm.g a b => pairPayload (mpoOrd a) (mpoOrd b)
  | SKTerm.f x y n => triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n)

lemma mpoOrd_eq_veblen_payload (t : SKTerm) :
    mpoOrd t = Ordinal.veblen (rank (sym t)) (payloadOrd t) := by
  cases t <;> simp [mpoOrd, payloadOrd, sym, rank]

lemma ordNat_pos {n : Nat} (h : 0 < n) : (0 : Ordinal.{0}) < (n : Ordinal.{0}) := by
  exact_mod_cast h

lemma veblen_fixed_of_pos {k x : Ordinal.{0}} (hk : 0 < k) :
    (ω : Ordinal.{0}) ^ (Ordinal.veblen k x) = Ordinal.veblen k x := by
  simpa [Ordinal.veblen_zero_apply] using (Ordinal.veblen_veblen_of_lt hk x)

lemma veblen_gt_one_of_pos {k x : Ordinal.{0}} (hk : 0 < k) :
    (1 : Ordinal.{0}) < Ordinal.veblen k x := by
  have hk1 : (1 : Ordinal.{0}) ≤ k := by
    simpa using (Order.succ_le_of_lt hk : Order.succ (0 : Ordinal.{0}) ≤ k)
  have hε : Ordinal.veblen 1 0 ≤ Ordinal.veblen k 0 :=
    (Ordinal.veblen_zero_le_veblen_zero).2 hk1
  have hx : Ordinal.veblen k 0 ≤ Ordinal.veblen k x :=
    (Ordinal.veblen_right_strictMono k).monotone (Ordinal.zero_le x)
  have h1ε : (1 : Ordinal.{0}) < Ordinal.veblen 1 0 := by
    exact Ordinal.one_lt_omega0.trans <|
      (by simpa [Ordinal.epsilon] using (Ordinal.omega0_lt_epsilon 0))
  exact h1ε.trans_le (hε.trans hx)

lemma veblen_isSuccLimit_of_pos {k x : Ordinal.{0}} (hk : 0 < k) :
    Order.IsSuccLimit (Ordinal.veblen k x) := by
  have hprin : Ordinal.Principal (· + ·) (Ordinal.veblen k x) := by
    simpa [veblen_fixed_of_pos hk] using
      (Ordinal.principal_add_omega0_opow (Ordinal.veblen k x))
  exact Ordinal.isSuccLimit_of_principal_add (veblen_gt_one_of_pos hk) hprin

lemma lt_veblen_of_nonlimit {k p : Ordinal.{0}} (hk : 0 < k) (hp : ¬ Order.IsSuccLimit p) :
    p < Ordinal.veblen k p := by
  have hle : p ≤ Ordinal.veblen k p := Ordinal.right_le_veblen k p
  exact lt_of_le_of_ne hle (fun hEq => hp (hEq ▸ veblen_isSuccLimit_of_pos hk))

lemma mpoOrd_gt_one_of_rank_pos {t : SKTerm} (h : 0 < rank (sym t)) :
    (1 : Ordinal.{0}) < mpoOrd t := by
  rw [mpoOrd_eq_veblen_payload]
  exact veblen_gt_one_of_pos (ordNat_pos h)

lemma mpoOrd_fixed_of_rank_pos {t : SKTerm} (h : 0 < rank (sym t)) :
    (ω : Ordinal.{0}) ^ mpoOrd t = mpoOrd t := by
  rw [mpoOrd_eq_veblen_payload]
  exact veblen_fixed_of_pos (ordNat_pos h)

lemma mpoOrd_isSuccLimit_of_rank_pos {t : SKTerm} (h : 0 < rank (sym t)) :
    Order.IsSuccLimit (mpoOrd t) := by
  rw [mpoOrd_eq_veblen_payload]
  exact veblen_isSuccLimit_of_pos (ordNat_pos h)

lemma left_lt_pairPayload (a b : Ordinal.{0}) : a < pairPayload a b := by
  have hcore : a < (ω : Ordinal) ^ (Order.succ a) + b := by
    have hpow : Order.succ a ≤ (ω : Ordinal) ^ (Order.succ a) :=
      Ordinal.right_le_opow (Order.succ a) Ordinal.one_lt_omega0
    exact lt_of_lt_of_le (Order.lt_succ a) (hpow.trans (Ordinal.le_add_right _ _))
  exact hcore.trans (Order.lt_succ _)

lemma right_lt_pairPayload (a b : Ordinal.{0}) : b < pairPayload a b := by
  exact lt_of_le_of_lt (Ordinal.le_add_left b ((ω : Ordinal) ^ (Order.succ a))) (Order.lt_succ _)

lemma pairPayload_lt_of_lt {a b α : Ordinal.{0}}
    (ha : a < α) (hb : b < α)
    (hlim : Order.IsSuccLimit α) (hfix : (ω : Ordinal) ^ α = α) :
    pairPayload a b < α := by
  have hsucc : Order.succ a < α := hlim.succ_lt ha
  have hpow : (ω : Ordinal) ^ (Order.succ a) < α := by
    rw [← hfix]
    exact (Ordinal.opow_lt_opow_iff_right Ordinal.one_lt_omega0).2 hsucc
  have hprin : Ordinal.Principal (· + ·) α := by
    simpa [hfix] using (Ordinal.principal_add_omega0_opow α)
  have hcore : (ω : Ordinal) ^ (Order.succ a) + b < α := hprin hpow hb
  exact hlim.succ_lt hcore

lemma first_lt_triplePayload (a b c : Ordinal.{0}) : a < triplePayload a b c := by
  have hexp : Order.succ a ≤ (ω : Ordinal) ^ (Order.succ a) + Order.succ b := by
    exact (Ordinal.right_le_opow (Order.succ a) Ordinal.one_lt_omega0).trans
      (Ordinal.le_add_right _ _)
  have hpow : a < (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) := by
    have hexp' : (ω : Ordinal) ^ (Order.succ a) + Order.succ b ≤
        (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) :=
      Ordinal.right_le_opow ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) Ordinal.one_lt_omega0
    exact lt_of_lt_of_le (Order.lt_succ a) (hexp.trans hexp')
  have hcore :
      a < (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c := by
    exact lt_of_lt_of_le hpow (Ordinal.le_add_right _ _)
  exact hcore.trans (Order.lt_succ _)

lemma second_lt_triplePayload (a b c : Ordinal.{0}) : b < triplePayload a b c := by
  have hexp : Order.succ b ≤ (ω : Ordinal) ^ (Order.succ a) + Order.succ b := by
    exact Ordinal.le_add_left (Order.succ b) ((ω : Ordinal) ^ (Order.succ a))
  have hpow : b < (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) := by
    have hexp' : (ω : Ordinal) ^ (Order.succ a) + Order.succ b ≤
        (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) :=
      Ordinal.right_le_opow ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) Ordinal.one_lt_omega0
    exact lt_of_lt_of_le (Order.lt_succ b) (hexp.trans hexp')
  have hcore :
      b < (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c := by
    exact lt_of_lt_of_le hpow (Ordinal.le_add_right _ _)
  exact hcore.trans (Order.lt_succ _)

lemma third_lt_triplePayload (a b c : Ordinal.{0}) : c < triplePayload a b c := by
  exact lt_of_le_of_lt
    (Ordinal.le_add_left c ((ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b)))
    (Order.lt_succ _)

lemma triplePayload_lt_of_lt {a b c α : Ordinal.{0}}
    (ha : a < α) (hb : b < α) (hc : c < α)
    (hlim : Order.IsSuccLimit α) (hfix : (ω : Ordinal) ^ α = α) :
    triplePayload a b c < α := by
  have hsuccA : Order.succ a < α := hlim.succ_lt ha
  have hsuccB : Order.succ b < α := hlim.succ_lt hb
  have hpowA : (ω : Ordinal) ^ (Order.succ a) < α := by
    rw [← hfix]
    exact (Ordinal.opow_lt_opow_iff_right Ordinal.one_lt_omega0).2 hsuccA
  have hprin : Ordinal.Principal (· + ·) α := by
    simpa [hfix] using (Ordinal.principal_add_omega0_opow α)
  have hexp : (ω : Ordinal) ^ (Order.succ a) + Order.succ b < α := hprin hpowA hsuccB
  have hpow : (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) < α := by
    rw [← hfix]
    exact (Ordinal.opow_lt_opow_iff_right Ordinal.one_lt_omega0).2 hexp
  have hcore :
      (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c < α := hprin hpow hc
  exact hlim.succ_lt hcore

lemma triplePayload_strictMono_right (a b : Ordinal.{0}) {c c' : Ordinal.{0}} (hc : c < c') :
    triplePayload a b c < triplePayload a b c' := by
  dsimp [triplePayload]
  have hcore :
      (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c <
      (ω : Ordinal) ^ ((ω : Ordinal) ^ (Order.succ a) + Order.succ b) + c' := by
    exact add_lt_add_left hc _
  exact (Order.succ_lt_succ_iff).2 hcore

lemma mpoOrd_lt_s_arg (t : SKTerm) : mpoOrd t < mpoOrd (s t) := by
  have hpayload : Order.succ (mpoOrd t) < mpoOrd (s t) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 2) (p := Order.succ (mpoOrd t))
        (by exact_mod_cast (show 0 < (2 : Nat) by decide))
        (Order.not_isSuccLimit_succ (mpoOrd t)))
  exact (Order.lt_succ _).trans hpayload

lemma mpoOrd_lt_g_left (a b : SKTerm) : mpoOrd a < mpoOrd (g a b) := by
  have hpayload : pairPayload (mpoOrd a) (mpoOrd b) < mpoOrd (g a b) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 3) (p := pairPayload (mpoOrd a) (mpoOrd b))
        (by exact_mod_cast (show 0 < (3 : Nat) by decide))
        (Order.not_isSuccLimit_succ _))
  exact (left_lt_pairPayload _ _).trans hpayload

lemma mpoOrd_lt_g_right (a b : SKTerm) : mpoOrd b < mpoOrd (g a b) := by
  have hpayload : pairPayload (mpoOrd a) (mpoOrd b) < mpoOrd (g a b) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 3) (p := pairPayload (mpoOrd a) (mpoOrd b))
        (by exact_mod_cast (show 0 < (3 : Nat) by decide))
        (Order.not_isSuccLimit_succ _))
  exact (right_lt_pairPayload _ _).trans hpayload

lemma mpoOrd_lt_f_first (x y n : SKTerm) : mpoOrd x < mpoOrd (f x y n) := by
  have hpayload : triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n) < mpoOrd (f x y n) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 4) (p := triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n))
        (by exact_mod_cast (show 0 < (4 : Nat) by decide))
        (Order.not_isSuccLimit_succ _))
  exact (first_lt_triplePayload _ _ _).trans hpayload

lemma mpoOrd_lt_f_second (x y n : SKTerm) : mpoOrd y < mpoOrd (f x y n) := by
  have hpayload : triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n) < mpoOrd (f x y n) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 4) (p := triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n))
        (by exact_mod_cast (show 0 < (4 : Nat) by decide))
        (Order.not_isSuccLimit_succ _))
  exact (second_lt_triplePayload _ _ _).trans hpayload

lemma mpoOrd_lt_f_third (x y n : SKTerm) : mpoOrd n < mpoOrd (f x y n) := by
  have hpayload : triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n) < mpoOrd (f x y n) := by
    simpa using
      (lt_veblen_of_nonlimit (k := 4) (p := triplePayload (mpoOrd x) (mpoOrd y) (mpoOrd n))
        (by exact_mod_cast (show 0 < (4 : Nat) by decide))
        (Order.not_isSuccLimit_succ _))
  exact (third_lt_triplePayload _ _ _).trans hpayload

lemma mpoOrd_arg_lt_of_mem {t u : SKTerm} (h : u ∈ args t) : mpoOrd u < mpoOrd t := by
  cases t with
  | var k => cases h
  | z => cases h
  | s a =>
      have hu : u = a := by simpa [args] using h
      simpa [hu] using mpoOrd_lt_s_arg a
  | g a b =>
      have hu : u = a ∨ u = b := by simpa [args] using h
      rcases hu with hu | hu
      · simpa [hu] using mpoOrd_lt_g_left a b
      · simpa [hu] using mpoOrd_lt_g_right a b
  | f x y n =>
      have hu : u = x ∨ u = y ∨ u = n := by simpa [args] using h
      rcases hu with hu | hrest
      · simpa [hu] using mpoOrd_lt_f_first x y n
      · rcases hrest with hu | hu
        · simpa [hu] using mpoOrd_lt_f_second x y n
        · simpa [hu] using mpoOrd_lt_f_third x y n

lemma payloadOrd_lt_of_args_lt {t u : SKTerm}
    (ht : 0 < rank (sym t))
    (hargs : ∀ v, v ∈ args u → mpoOrd v < mpoOrd t) :
    payloadOrd u < mpoOrd t := by
  have hlim : Order.IsSuccLimit (mpoOrd t) := mpoOrd_isSuccLimit_of_rank_pos ht
  have hfix : (ω : Ordinal) ^ mpoOrd t = mpoOrd t := mpoOrd_fixed_of_rank_pos ht
  cases u with
  | var k =>
      exact zero_lt_one.trans (mpoOrd_gt_one_of_rank_pos ht)
  | z =>
      exact zero_lt_one.trans (mpoOrd_gt_one_of_rank_pos ht)
  | s a =>
      have hsmall : mpoOrd a < mpoOrd t := hargs a (by simp [args])
      exact Order.IsSuccLimit.succ_lt (α := Ordinal) hlim hsmall
  | g a b =>
      have hleft : mpoOrd a < mpoOrd t := hargs a (by simp [args])
      have hright : mpoOrd b < mpoOrd t := hargs b (by simp [args])
      exact pairPayload_lt_of_lt (a := mpoOrd a) (b := mpoOrd b) (α := mpoOrd t)
        hleft hright hlim hfix
  | f x y n =>
      have hx : mpoOrd x < mpoOrd t := hargs x (by simp [args])
      have hy : mpoOrd y < mpoOrd t := hargs y (by simp [args])
      have hn : mpoOrd n < mpoOrd t := hargs n (by simp [args])
      exact triplePayload_lt_of_lt (a := mpoOrd x) (b := mpoOrd y) (c := mpoOrd n)
        (α := mpoOrd t) hx hy hn hlim hfix

lemma mpoOrd_lt_of_byPrec {t u : SKTerm}
    (hprec : symPrec (sym u) (sym t))
    (hargs : ∀ v, v ∈ args u → mpoOrd v < mpoOrd t) :
    mpoOrd u < mpoOrd t := by
  have ht : 0 < rank (sym t) := Nat.zero_lt_of_lt hprec
  have hpayload : payloadOrd u < mpoOrd t := payloadOrd_lt_of_args_lt ht hargs
  have hprecOrd : ((rank (sym u)) : Ordinal) < ((rank (sym t)) : Ordinal) := by
    exact_mod_cast hprec
  rw [mpoOrd_eq_veblen_payload u, mpoOrd_eq_veblen_payload t]
  have hpayload' : payloadOrd u < Ordinal.veblen (rank (sym t)) (payloadOrd t) := by
    simpa [mpoOrd_eq_veblen_payload t] using hpayload
  exact (Ordinal.veblen_lt_veblen_iff).2 (Or.inr (Or.inl ⟨hprecOrd, hpayload'⟩))

/-- Every MPO comparison strictly decreases the native ordinal rank. -/
theorem mpoOrd_strict_of_mpo {a b : SKTerm} (h : MPO a b) : mpoOrd b < mpoOrd a := by
  induction h with
  | subEq hmem =>
      exact mpoOrd_arg_lt_of_mem hmem
  | subGt hmem hgt ih =>
      exact ih.trans (mpoOrd_arg_lt_of_mem hmem)
  | byPrec hprec hargs ih =>
      exact mpoOrd_lt_of_byPrec hprec (fun v hv => ih v hv)
  | fArg hgt ih =>
      rw [mpoOrd_eq_veblen_payload (f _ _ _), mpoOrd_eq_veblen_payload (f _ _ _)]
      exact (Ordinal.veblen_lt_veblen_iff_right).2
        (triplePayload_strictMono_right _ _ ih)

/-- Reverse MPO relation. -/
def MPORev : SKTerm → SKTerm → Prop := fun a b => MPO b a

/-- The schema-specialized MPO is well-founded in reverse, NATIVELY, by the
Veblen ordinal ranking. No polynomial or other system witness is used. -/
theorem wf_MPORev : WellFounded MPORev := by
  have wf_measure : WellFounded (fun a b : SKTerm => (mpoOrd a : Ordinal) < mpoOrd b) :=
    InvImage.wf mpoOrd Ordinal.lt_wf
  have hsub : Subrelation MPORev (fun a b : SKTerm => (mpoOrd a : Ordinal) < mpoOrd b) := by
    intro a b hab
    exact mpoOrd_strict_of_mpo hab
  exact Subrelation.wf hsub wf_measure

/-- Root-step termination of the schema kernel derived from the specialized
MPO alone: the reverse root relation is well-founded because every root step
is MPO-oriented and reverse MPO is natively well-founded. -/
theorem wf_RootStepRev_mpo : WellFounded (fun a b : SKTerm => RootStep b a) := by
  have hsub : Subrelation (fun a b : SKTerm => RootStep b a) MPORev := by
    intro a b hstep
    exact mpo_orients_rootStep hstep
  exact Subrelation.wf hsub wf_MPORev

end KO7Benchmark.SchemaTests.SchemaMPO
