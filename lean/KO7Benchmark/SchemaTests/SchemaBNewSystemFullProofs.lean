/-
  Full-Step method certificates for Schema Test B New System.

  Each listed option A-E gets a certificate relation that (1) covers every
  full contextual `Step` and (2) is well-founded in reverse. "Full" in
  `FullMethodCertificate` means full contextual `Step` coverage, nothing
  stronger. The per-slot trust boundaries differ and are stated exactly:

  * Slots B and E are COMPLETE method proofs: the certificate relation IS
    the exact interpretation printed in the prompt (`p2` respectively
    `eInterp`), and its strict decrease on every `Step` plus its
    well-foundedness are the whole mathematical content of those methods.
  * Slots A, C, D are OBLIGATIONS-PLUS-MEASURE certificates: the root
    constructors carry the method's concrete per-rule obligations (the
    F > G precedence fact for A/C, the multiset swap fact for C, the
    extracted dependency pair and its third-argument projection decrease
    for D), threaded through the full contextual closure; but the
    well-foundedness of the reverse relation is discharged by the
    benchmark's proven polynomial measure (a subrelation embedding into
    `NonCollapsingPoly.p2` decrease), NOT by a generic path-order or
    DP-framework well-foundedness theorem. No recursive LPO/MPO relation
    and no DP soundness theorem is mechanized here; this follows the
    benchmark-wide obligations-file pattern (`CandidateA_PathOrderSupport`,
    `MPOSuccessWitness`, `CandidateD_SoundnessBridge`).

  Scope:
  * Benchmark-local certificates for the exact two-rule schema kernel and
    its full contextual closure `Step`; not reusable generic order libraries.
  * Relation: `Step` (full contextual closure). Property: SN.
  * Trust: kernel-only, mathlib baseline; no axioms, no sorry.
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateA_PathOrderSupport
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SchemaTests.NonCollapsingPolyWitness
import KO7Benchmark.SchemaTests.ExponentialInterpretationWitness

namespace KO7Benchmark.SchemaTests.SchemaBNewSystemFullProofs

open KO7Benchmark.SchemaTests
open SKTerm

/-- A concrete method certificate for this benchmark: `R t u` means the
method's strict order/certificate orients `t -> u`; the reverse relation is
well-founded, and every full contextual `Step` is covered.

Relation: `Step` (full contextual closure).
Property: SN via a method-specific strict certificate relation.
-/
structure FullMethodCertificate (R : SKTerm → SKTerm → Prop) where
  orients_step : ∀ {t u : SKTerm}, Step t u → R t u
  wf_reverse : WellFounded (fun a b : SKTerm => R b a)

/-- Measure-induced strict orientation, used only for the interpretation
methods B and E where the prompt itself gives a semantic interpretation. -/
def MeasureRel (m : SKTerm → Nat) : SKTerm → SKTerm → Prop :=
  fun t u => m u < m t

theorem measureRel_wf (m : SKTerm → Nat) :
    WellFounded (fun a b : SKTerm => MeasureRel m b a) :=
  InvImage.wf m Nat.lt_wfRel.wf

/-! ## Slot A: LPO certificate for `F > G > S > Z` -/

/-- Benchmark-local LPO-obligations certificate relation for slot A.

Proves: the two root rules each carry their LPO-shaped local obligations
(base = subterm case; recursive = the `F > G` precedence fact plus the two
RHS-argument domination facts, expressed via the proven benchmark measure),
and the certificate is closed under all six `Step` contexts.
Does not prove: a recursive path-order relation or a native LPO
well-foundedness theorem; `lpoCert_wf_reverse` is discharged by the `p2`
measure subrelation. -/
inductive LPOCert : SKTerm → SKTerm → Prop
  | root_base (x y : SKTerm) : LPOCert (f x y z) x
  | root_succ (x y n : SKTerm)
      (hFG :
        CandidateA.precRank (CandidateA.rootSym (g y (f x y n))) <
          CandidateA.precRank (CandidateA.rootSym (f x y (s n))))
      (hy :
        NonCollapsingPoly.p2 y <
          NonCollapsingPoly.p2 (f x y (s n)))
      (hrec :
        NonCollapsingPoly.p2 (f x y n) <
          NonCollapsingPoly.p2 (f x y (s n))) :
      LPOCert (f x y (s n)) (g y (f x y n))
  | s_arg {t u : SKTerm} : LPOCert t u → LPOCert (s t) (s u)
  | g_left {t u b : SKTerm} : LPOCert t u → LPOCert (g t b) (g u b)
  | g_right {a t u : SKTerm} : LPOCert t u → LPOCert (g a t) (g a u)
  | f_arg1 {t u b c : SKTerm} : LPOCert t u → LPOCert (f t b c) (f u b c)
  | f_arg2 {a t u c : SKTerm} : LPOCert t u → LPOCert (f a t c) (f a u c)
  | f_arg3 {a b t u : SKTerm} : LPOCert t u → LPOCert (f a b t) (f a b u)

theorem lpo_payload_dominated (x y n : SKTerm) :
    NonCollapsingPoly.p2 y < NonCollapsingPoly.p2 (f x y (s n)) := by
  simp only [NonCollapsingPoly.p2_f, NonCollapsingPoly.p2_s]
  nlinarith [NonCollapsingPoly.p2 x, NonCollapsingPoly.p2 y, NonCollapsingPoly.p2 n]

theorem lpoCert_orients_step : ∀ {t u : SKTerm}, Step t u → LPOCert t u
  | _, _, Step.root (RootStep.base x y) => LPOCert.root_base x y
  | _, _, Step.root (RootStep.succ x y n) =>
      LPOCert.root_succ x y n
        (CandidateA.candidateA_declares_F_over_G x y n)
        (lpo_payload_dominated x y n)
        (by
          simp only [NonCollapsingPoly.p2_f, NonCollapsingPoly.p2_s]
          nlinarith [NonCollapsingPoly.p2 y])
  | _, _, Step.s_arg h => LPOCert.s_arg (lpoCert_orients_step h)
  | _, _, Step.g_left h => LPOCert.g_left (lpoCert_orients_step h)
  | _, _, Step.g_right h => LPOCert.g_right (lpoCert_orients_step h)
  | _, _, Step.f_arg1 h => LPOCert.f_arg1 (lpoCert_orients_step h)
  | _, _, Step.f_arg2 h => LPOCert.f_arg2 (lpoCert_orients_step h)
  | _, _, Step.f_arg3 h => LPOCert.f_arg3 (lpoCert_orients_step h)

theorem lpoCert_decreases_p2 : ∀ {t u : SKTerm},
    LPOCert t u → NonCollapsingPoly.p2 u < NonCollapsingPoly.p2 t
  | _, _, LPOCert.root_base x y => NonCollapsingPoly.p2_root_base x y
  | _, _, LPOCert.root_succ x y n _ _ _ => NonCollapsingPoly.p2_root_succ x y n
  | _, _, LPOCert.s_arg h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_s]
      omega
  | _, _, LPOCert.g_left h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, LPOCert.g_right h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, LPOCert.f_arg1 h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      omega
  | _, _, LPOCert.f_arg2 (a := a) (t := t) (u := u) (c := c) h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]
  | _, _, LPOCert.f_arg3 (a := a) (b := b) (t := t) (u := u) h => by
      have hlt := lpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]

theorem lpoCert_wf_reverse :
    WellFounded (fun a b : SKTerm => LPOCert b a) := by
  have hsub :
      Subrelation (fun a b : SKTerm => LPOCert b a)
        (InvImage (· < ·) NonCollapsingPoly.p2) := by
    intro a b h
    exact lpoCert_decreases_p2 h
  exact Subrelation.wf hsub
    (InvImage.wf NonCollapsingPoly.p2 Nat.lt_wfRel.wf)

theorem slotA_LPO_full_certificate :
    FullMethodCertificate LPOCert :=
  ⟨lpoCert_orients_step, lpoCert_wf_reverse⟩

/-! ## Slot B: exact nonlinear polynomial interpretation -/

def NonlinearPolyRel : SKTerm → SKTerm → Prop :=
  MeasureRel NonCollapsingPoly.p2

theorem nonlinearPoly_orients_step :
    ∀ {t u : SKTerm}, Step t u → NonlinearPolyRel t u :=
  fun h => NonCollapsingPoly.p2_step_decreases h

theorem slotB_nonlinearPoly_full_certificate :
    FullMethodCertificate NonlinearPolyRel :=
  ⟨nonlinearPoly_orients_step, measureRel_wf NonCollapsingPoly.p2⟩

/-! ## Slot C: MPO certificate for multiset status and `F > G > S > Z` -/

/-- Benchmark-local MPO-obligations certificate relation for slot C.

Proves: the recursive root constructor records the MPO precedence case and
the multiset-status obligations (duplicated `y` dominated by the LHS; the
swapped element `S(n) -> n` strictly decreasing; the recursive F-call
dominated), expressed via the proven benchmark measure, closed under all
six `Step` contexts.
Does not prove: a recursive multiset path order or its native
well-foundedness; `mpoCert_wf_reverse` is discharged by the `p2` measure
subrelation. The NATIVE specialized MPO (recursive comparator + Veblen
ordinal well-foundedness, no measure appeal) lives separately in
`SchemaSpecializedMPO.lean` at root-relation scope. -/
inductive MPOCert : SKTerm → SKTerm → Prop
  | root_base (x y : SKTerm) : MPOCert (f x y z) x
  | root_succ (x y n : SKTerm)
      (hFG :
        CandidateA.precRank (CandidateA.rootSym (g y (f x y n))) <
          CandidateA.precRank (CandidateA.rootSym (f x y (s n))))
      (hy :
        NonCollapsingPoly.p2 y <
          NonCollapsingPoly.p2 (f x y (s n)))
      (hswap :
        NonCollapsingPoly.p2 n < NonCollapsingPoly.p2 (s n))
      (hrec :
        NonCollapsingPoly.p2 (f x y n) <
          NonCollapsingPoly.p2 (f x y (s n))) :
      MPOCert (f x y (s n)) (g y (f x y n))
  | s_arg {t u : SKTerm} : MPOCert t u → MPOCert (s t) (s u)
  | g_left {t u b : SKTerm} : MPOCert t u → MPOCert (g t b) (g u b)
  | g_right {a t u : SKTerm} : MPOCert t u → MPOCert (g a t) (g a u)
  | f_arg1 {t u b c : SKTerm} : MPOCert t u → MPOCert (f t b c) (f u b c)
  | f_arg2 {a t u c : SKTerm} : MPOCert t u → MPOCert (f a t c) (f a u c)
  | f_arg3 {a b t u : SKTerm} : MPOCert t u → MPOCert (f a b t) (f a b u)

theorem mpoCert_orients_step : ∀ {t u : SKTerm}, Step t u → MPOCert t u
  | _, _, Step.root (RootStep.base x y) => MPOCert.root_base x y
  | _, _, Step.root (RootStep.succ x y n) =>
      MPOCert.root_succ x y n
        (CandidateA.candidateA_declares_F_over_G x y n)
        (lpo_payload_dominated x y n)
        (by simp only [NonCollapsingPoly.p2_s]; omega)
        (by
          simp only [NonCollapsingPoly.p2_f, NonCollapsingPoly.p2_s]
          nlinarith [NonCollapsingPoly.p2 y])
  | _, _, Step.s_arg h => MPOCert.s_arg (mpoCert_orients_step h)
  | _, _, Step.g_left h => MPOCert.g_left (mpoCert_orients_step h)
  | _, _, Step.g_right h => MPOCert.g_right (mpoCert_orients_step h)
  | _, _, Step.f_arg1 h => MPOCert.f_arg1 (mpoCert_orients_step h)
  | _, _, Step.f_arg2 h => MPOCert.f_arg2 (mpoCert_orients_step h)
  | _, _, Step.f_arg3 h => MPOCert.f_arg3 (mpoCert_orients_step h)

theorem mpoCert_decreases_p2 : ∀ {t u : SKTerm},
    MPOCert t u → NonCollapsingPoly.p2 u < NonCollapsingPoly.p2 t
  | _, _, MPOCert.root_base x y => NonCollapsingPoly.p2_root_base x y
  | _, _, MPOCert.root_succ x y n _ _ _ _ => NonCollapsingPoly.p2_root_succ x y n
  | _, _, MPOCert.s_arg h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_s]
      omega
  | _, _, MPOCert.g_left h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, MPOCert.g_right h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, MPOCert.f_arg1 h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      omega
  | _, _, MPOCert.f_arg2 (a := a) (t := t) (u := u) (c := c) h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]
  | _, _, MPOCert.f_arg3 (a := a) (b := b) (t := t) (u := u) h => by
      have hlt := mpoCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]

theorem mpoCert_wf_reverse :
    WellFounded (fun a b : SKTerm => MPOCert b a) := by
  have hsub :
      Subrelation (fun a b : SKTerm => MPOCert b a)
        (InvImage (· < ·) NonCollapsingPoly.p2) := by
    intro a b h
    exact mpoCert_decreases_p2 h
  exact Subrelation.wf hsub
    (InvImage.wf NonCollapsingPoly.p2 Nat.lt_wfRel.wf)

theorem slotC_MPO_full_certificate :
    FullMethodCertificate MPOCert :=
  ⟨mpoCert_orients_step, mpoCert_wf_reverse⟩

/-! ## Slot D: dependency-pair/subterm certificate -/

/-- Benchmark-local DP-obligations certificate relation for slot D.

Proves: the recursive root case carries the extracted dependency pair
(`CandidateD.DPPair`) and its third-argument subterm-projection decrease
(`sDepth`), closed under all six `Step` contexts.
Does not prove: DP-framework soundness (projection termination does not by
itself give full-TRS termination); `dpCert_wf_reverse` is discharged by the
`p2` measure subrelation, exactly as the honest bridge pattern in
`CandidateD_SoundnessBridge` closes the Schema B row. -/
inductive DPCert : SKTerm → SKTerm → Prop
  | root_base (x y : SKTerm) : DPCert (f x y z) x
  | root_succ (x y n : SKTerm)
      (pair : CandidateD.DPPair (f x y (s n)) (f x y n))
      (proj :
        CandidateD.sDepth (f x y n) <
          CandidateD.sDepth (f x y (s n))) :
      DPCert (f x y (s n)) (g y (f x y n))
  | s_arg {t u : SKTerm} : DPCert t u → DPCert (s t) (s u)
  | g_left {t u b : SKTerm} : DPCert t u → DPCert (g t b) (g u b)
  | g_right {a t u : SKTerm} : DPCert t u → DPCert (g a t) (g a u)
  | f_arg1 {t u b c : SKTerm} : DPCert t u → DPCert (f t b c) (f u b c)
  | f_arg2 {a t u c : SKTerm} : DPCert t u → DPCert (f a t c) (f a u c)
  | f_arg3 {a b t u : SKTerm} : DPCert t u → DPCert (f a b t) (f a b u)

theorem dpCert_orients_step : ∀ {t u : SKTerm}, Step t u → DPCert t u
  | _, _, Step.root (RootStep.base x y) => DPCert.root_base x y
  | _, _, Step.root (RootStep.succ x y n) =>
      DPCert.root_succ x y n
        (CandidateD.DPPair.succ x y n)
        (CandidateD.dp_pair_decreases (CandidateD.DPPair.succ x y n))
  | _, _, Step.s_arg h => DPCert.s_arg (dpCert_orients_step h)
  | _, _, Step.g_left h => DPCert.g_left (dpCert_orients_step h)
  | _, _, Step.g_right h => DPCert.g_right (dpCert_orients_step h)
  | _, _, Step.f_arg1 h => DPCert.f_arg1 (dpCert_orients_step h)
  | _, _, Step.f_arg2 h => DPCert.f_arg2 (dpCert_orients_step h)
  | _, _, Step.f_arg3 h => DPCert.f_arg3 (dpCert_orients_step h)

theorem dpCert_decreases_p2 : ∀ {t u : SKTerm},
    DPCert t u → NonCollapsingPoly.p2 u < NonCollapsingPoly.p2 t
  | _, _, DPCert.root_base x y => NonCollapsingPoly.p2_root_base x y
  | _, _, DPCert.root_succ x y n _ _ => NonCollapsingPoly.p2_root_succ x y n
  | _, _, DPCert.s_arg h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_s]
      omega
  | _, _, DPCert.g_left h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, DPCert.g_right h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_g]
      omega
  | _, _, DPCert.f_arg1 h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      omega
  | _, _, DPCert.f_arg2 (a := a) (t := t) (u := u) (c := c) h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]
  | _, _, DPCert.f_arg3 (a := a) (b := b) (t := t) (u := u) h => by
      have hlt := dpCert_decreases_p2 h
      simp only [NonCollapsingPoly.p2_f]
      nlinarith [NonCollapsingPoly.p2 u, NonCollapsingPoly.p2 t]

theorem dpCert_wf_reverse :
    WellFounded (fun a b : SKTerm => DPCert b a) := by
  have hsub :
      Subrelation (fun a b : SKTerm => DPCert b a)
        (InvImage (· < ·) NonCollapsingPoly.p2) := by
    intro a b h
    exact dpCert_decreases_p2 h
  exact Subrelation.wf hsub
    (InvImage.wf NonCollapsingPoly.p2 Nat.lt_wfRel.wf)

theorem slotD_DP_full_certificate :
    FullMethodCertificate DPCert :=
  ⟨dpCert_orients_step, dpCert_wf_reverse⟩

/-! ## Slot E: exact exponential interpretation -/

def ExpRel : SKTerm → SKTerm → Prop :=
  MeasureRel ExponentialInterp.eInterp

theorem exp_orients_step :
    ∀ {t u : SKTerm}, Step t u → ExpRel t u :=
  fun h => ExponentialInterp.eInterp_step_decreases h

theorem slotE_exponential_full_certificate :
    FullMethodCertificate ExpRel :=
  ⟨exp_orients_step, measureRel_wf ExponentialInterp.eInterp⟩

/-! ## Combined control theorem -/

theorem schemaBNewSystem_all_slots_have_full_certificates :
    FullMethodCertificate LPOCert ∧
      FullMethodCertificate NonlinearPolyRel ∧
      FullMethodCertificate MPOCert ∧
      FullMethodCertificate DPCert ∧
      FullMethodCertificate ExpRel := by
  exact ⟨slotA_LPO_full_certificate,
    slotB_nonlinearPoly_full_certificate,
    slotC_MPO_full_certificate,
    slotD_DP_full_certificate,
    slotE_exponential_full_certificate⟩

end KO7Benchmark.SchemaTests.SchemaBNewSystemFullProofs
