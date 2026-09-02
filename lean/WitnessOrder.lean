/-
  Self-contained witness-order layer for the benchmark Lean stack.

  This module is the Paper-B-facing replacement for the cross-paper
  bridge wrapper. It defines the four-level coarse witness-language
  hierarchy used by the benchmark contract, populates the KO7 tower
  using the local benchmark proofs only, and proves the three-kappa
  summary needed for the answer-key calculus.

  The four-level enum and the contract structure are standard; the
  benchmark contract excludes direct whole-term and imported-whole
  routes and admits transformed-call or external-certificate routes.

  KO7-specific population:

  * direct whole-term layer: a self-contained no-go for any additive
    constructor-weighted measure with positive `app` weight, refuted
    on `R_rec_succ` with `s = delta void`.
  * imported-whole layer: the root-step strong-normalization theorem
    `KO7Benchmark.Test03Ordinal.strong_normalization_closed`.
  * transformed-call layer: the dependency-pair well-foundedness
    theorem `KO7Benchmark.KO7DependencyPairs.wf_DPPairRev`.
  * external-certificate layer: `True` (the TTT2/CeTA certificate
    chain is summarized in `KO7Benchmark.CertificateBridge`).
-/
import Mathlib.Order.WellFounded
import Mathlib.Tactic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.KO7DependencyPairs
import KO7Benchmark.Test03_Ordinal_AnswerKey

namespace KO7Benchmark.WitnessOrder

open KO7Benchmark.KO7Kernel
open Trace

/-! ## Coarse witness-language levels -/

/-- Four-level coarse witness hierarchy used by the benchmark contract. -/
inductive WLevel
  | directWhole
  | importedWhole
  | transformedCall
  | externalCert
deriving DecidableEq, Repr

namespace WLevel

def toNat : WLevel → Nat
  | directWhole => 0
  | importedWhole => 1
  | transformedCall => 2
  | externalCert => 3

instance : LE WLevel := ⟨fun a b => a.toNat ≤ b.toNat⟩
instance : LT WLevel := ⟨fun a b => a.toNat < b.toNat⟩

instance (a b : WLevel) : Decidable (a ≤ b) :=
  inferInstanceAs (Decidable (a.toNat ≤ b.toNat))
instance (a b : WLevel) : Decidable (a < b) :=
  inferInstanceAs (Decidable (a.toNat < b.toNat))

@[simp] theorem toNat_directWhole : toNat directWhole = 0 := rfl
@[simp] theorem toNat_importedWhole : toNat importedWhole = 1 := rfl
@[simp] theorem toNat_transformedCall : toNat transformedCall = 2 := rfl
@[simp] theorem toNat_externalCert : toNat externalCert = 3 := rfl

theorem directWhole_lt_importedWhole :
    WLevel.directWhole < WLevel.importedWhole := by decide

theorem importedWhole_lt_transformedCall :
    WLevel.importedWhole < WLevel.transformedCall := by decide

theorem transformedCall_lt_externalCert :
    WLevel.transformedCall < WLevel.externalCert := by decide

end WLevel

/-! ## Witness towers and witness-existence predicates -/

/-- A witness tower assigns to each level the proposition stating that the
    target object has a witness at that level. -/
def WitnessTower := WLevel → Prop

def HasWitness (T : WitnessTower) (ℓ : WLevel) : Prop := T ℓ

def kappaLe (T : WitnessTower) (ℓ : WLevel) : Prop :=
  ∃ j : WLevel, j.toNat ≤ ℓ.toNat ∧ HasWitness T j

def kappaGt (T : WitnessTower) (ℓ : WLevel) : Prop :=
  ∀ j : WLevel, j.toNat ≤ ℓ.toNat → ¬ HasWitness T j

/-! ## Task contract -/

/-- A task contract records which witness-language levels the benchmark
    accepts as admissible. -/
structure TaskContract where
  admissible : WLevel → Prop

def contractTower (T : WitnessTower) (Γ : TaskContract) : WitnessTower :=
  fun ℓ => Γ.admissible ℓ ∧ T ℓ

/-- The benchmark contract: only transformed-call or external-certificate
    routes are admissible. -/
def benchmarkContract : TaskContract where
  admissible
    | .directWhole => False
    | .importedWhole => False
    | .transformedCall => True
    | .externalCert => True

/-! ## Direct whole-term witness predicate and benchmark-local no-go -/

/-- Constructor-weight assignments for the seven KO7 constructors,
    parameterizing additive whole-term measures over `Trace`. -/
structure AdditiveTraceMeasure where
  wVoid       : Nat
  wDelta      : Nat
  wIntegrate  : Nat
  wMerge      : Nat
  wApp        : Nat
  wRec        : Nat
  wEq         : Nat
  wApp_pos    : 0 < wApp

namespace AdditiveTraceMeasure

/-- The additive evaluation defined by a constructor-weight assignment. -/
def eval (M : AdditiveTraceMeasure) : Trace → Nat
  | void => M.wVoid
  | delta t => M.wDelta + M.eval t
  | integrate t => M.wIntegrate + M.eval t
  | merge a b => M.wMerge + M.eval a + M.eval b
  | app a b => M.wApp + M.eval a + M.eval b
  | recDelta b s n => M.wRec + M.eval b + M.eval s + M.eval n
  | eqW a b => M.wEq + M.eval a + M.eval b

@[simp] theorem eval_void (M : AdditiveTraceMeasure) :
    M.eval void = M.wVoid := rfl
@[simp] theorem eval_delta (M : AdditiveTraceMeasure) (t : Trace) :
    M.eval (delta t) = M.wDelta + M.eval t := rfl
@[simp] theorem eval_app (M : AdditiveTraceMeasure) (a b : Trace) :
    M.eval (app a b) = M.wApp + M.eval a + M.eval b := rfl
@[simp] theorem eval_recDelta (M : AdditiveTraceMeasure) (b s n : Trace) :
    M.eval (recDelta b s n) = M.wRec + M.eval b + M.eval s + M.eval n := rfl

end AdditiveTraceMeasure

/-- A direct whole-term witness for KO7 termination would be an additive
    constructor-weighted measure with positive `app` weight that strictly
    decreases on every step. The benchmark Lean proves this is empty.

    This is the benchmark-local refutation of the additive direct route;
    it is honest and self-contained. The full twelve-class direct-measure
    barrier theorem in the companion artifact strengthens this to every
    direct-measure family enumerated there. The benchmark stack mechanizes
    only the additive case so the negative-control story closes locally. -/
def DirectWholeWitness : Prop :=
  ∃ M : AdditiveTraceMeasure,
    ∀ {a b : Trace}, Step a b → M.eval b < M.eval a

/-! ## KO7 witness tower -/

/-- KO7 witness tower populated by benchmark-local proofs only. -/
def ko7Tower : WitnessTower
  | .directWhole     => DirectWholeWitness
  | .importedWhole   => WellFounded (fun a b : Trace => Step b a)
  | .transformedCall => WellFounded KO7Benchmark.KO7DependencyPairs.DPPairRev
  | .externalCert    => True

/-! ## Direct whole-term refutation -/

/-- No additive whole-term measure with positive `app` weight orients
    `R_rec_succ` uniformly. The witness substitution is `b = void`,
    `s = delta void`, `n = void`. -/
theorem ko7_no_directWhole_witness :
    ¬ HasWitness ko7Tower WLevel.directWhole := by
  rintro ⟨M, h⟩
  -- Apply the duplicating step with b := void, s := delta void, n := void.
  have hstep :
      Step (recDelta void (delta void) (delta void))
           (app (delta void) (recDelta void (delta void) void)) := by
    exact Step.R_rec_succ void (delta void) void
  have hlt := h hstep
  -- Compute both sides.
  simp only [AdditiveTraceMeasure.eval] at hlt
  have hpos := M.wApp_pos
  omega

/-! ## Imported-whole and transformed-call witnesses -/

/-- KO7 has a benchmark-local truth-level imported-whole witness through
    the root-step strong-normalization theorem of `Test03_Ordinal_AnswerKey`. -/
theorem ko7_has_importedWhole_witness :
    HasWitness ko7Tower WLevel.importedWhole := by
  show WellFounded (fun a b : Trace => Step b a)
  exact KO7Benchmark.Test03Ordinal.strong_normalization_closed

/-- KO7 has a benchmark-local transformed-call witness through the
    dependency-pair well-foundedness theorem. -/
theorem ko7_has_transformedCall_witness :
    HasWitness ko7Tower WLevel.transformedCall := by
  show WellFounded KO7Benchmark.KO7DependencyPairs.DPPairRev
  exact KO7Benchmark.KO7DependencyPairs.wf_DPPairRev

/-- KO7's transformed-call witness still admits a simple linear base order
    on the extracted dependency-pair problem. -/
theorem ko7_transformedCall_has_linear_base_order :
    ∃ μ : Trace → Nat,
      ∀ {a b : Trace}, KO7Benchmark.KO7DependencyPairs.DPPair a b → μ b < μ a :=
  KO7Benchmark.KO7DependencyPairs.extracted_dp_problem_has_linear_base_order

/-- The external-certificate layer is populated by the TTT2/CeTA replay
    summary in `CertificateBridge`. The benchmark stack only records its
    presence; the substantive fact is that the chain exists. -/
theorem ko7_has_externalCert_witness :
    HasWitness ko7Tower WLevel.externalCert := by
  show True
  trivial

/-! ## Three-kappa summary -/

theorem ko7_kappaDirect_gt_directWhole :
    kappaGt ko7Tower WLevel.directWhole := by
  intro j hj
  cases j with
  | directWhole =>
      simpa [HasWitness] using ko7_no_directWhole_witness
  | importedWhole => simp [WLevel.toNat] at hj
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert => simp [WLevel.toNat] at hj

theorem ko7_kappaTruth_le_importedWhole :
    kappaLe ko7Tower WLevel.importedWhole :=
  ⟨WLevel.importedWhole, by decide, ko7_has_importedWhole_witness⟩

theorem benchmarkContract_disallows_importedWhole :
    ¬ benchmarkContract.admissible WLevel.importedWhole := by
  show ¬ False
  exact id

theorem ko7_kappaContract_gt_importedWhole :
    kappaGt (contractTower ko7Tower benchmarkContract) WLevel.importedWhole := by
  intro j hj
  cases j with
  | directWhole =>
      intro h
      exact h.1
  | importedWhole =>
      intro h
      exact h.1
  | transformedCall => simp [WLevel.toNat] at hj
  | externalCert => simp [WLevel.toNat] at hj

theorem ko7_kappaContract_le_transformedCall :
    kappaLe (contractTower ko7Tower benchmarkContract) WLevel.transformedCall := by
  refine ⟨WLevel.transformedCall, by decide, ?_⟩
  refine ⟨?_, ko7_has_transformedCall_witness⟩
  show benchmarkContract.admissible WLevel.transformedCall
  trivial

/-- The cross-paper three-kappa split, locally certified. -/
theorem ko7_three_kappa_summary :
    kappaGt ko7Tower WLevel.directWhole ∧
      kappaLe ko7Tower WLevel.importedWhole ∧
      kappaGt (contractTower ko7Tower benchmarkContract) WLevel.importedWhole ∧
      kappaLe (contractTower ko7Tower benchmarkContract) WLevel.transformedCall :=
  ⟨ko7_kappaDirect_gt_directWhole,
   ko7_kappaTruth_le_importedWhole,
   ko7_kappaContract_gt_importedWhole,
   ko7_kappaContract_le_transformedCall⟩

/-! ## Contract bookkeeping -/

@[simp] theorem benchmarkContract_admissible_directWhole :
    benchmarkContract.admissible WLevel.directWhole = False := rfl

@[simp] theorem benchmarkContract_admissible_importedWhole :
    benchmarkContract.admissible WLevel.importedWhole = False := rfl

@[simp] theorem benchmarkContract_admissible_transformedCall :
    benchmarkContract.admissible WLevel.transformedCall = True := rfl

@[simp] theorem benchmarkContract_admissible_externalCert :
    benchmarkContract.admissible WLevel.externalCert = True := rfl

/-- A contract witness for KO7 first appears at the transformed-call layer. -/
def HasContractWitness (T : WitnessTower) (Γ : TaskContract) : Prop :=
  ∃ ℓ : WLevel, Γ.admissible ℓ ∧ HasWitness T ℓ

theorem ko7_kappaContract_has_transformedCall :
    HasContractWitness ko7Tower benchmarkContract := by
  refine ⟨WLevel.transformedCall, ?_, ko7_has_transformedCall_witness⟩
  show benchmarkContract.admissible WLevel.transformedCall
  trivial

theorem benchmark_importedWhole_out_of_contract :
    HasWitness ko7Tower WLevel.importedWhole ∧
      ¬ benchmarkContract.admissible WLevel.importedWhole :=
  ⟨ko7_has_importedWhole_witness, benchmarkContract_disallows_importedWhole⟩

theorem benchmark_directWhole_out_of_contract :
    ¬ benchmarkContract.admissible WLevel.directWhole := by
  show ¬ False
  exact id

end KO7Benchmark.WitnessOrder
