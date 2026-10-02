/-
  The task-relativized exhaustion gap and the typed-abstention counting
  theorem.

  Mechanizes Rahnama_PRT_Benchmark.tex §3 (task-relativized exhaustion
  gap; "T4 requires exhaustion work of at least E(x)"; the recursor
  corollary "E(recursor) ≥ 12 + |W1-catalog|"). Before this module the
  definitions were manuscript-level.

  Model: a supervisory catalog assigns a per-layer budget of distinct
  catalog-listed witness attempts. A typed-abstention record carries a
  list of failure certificates, one per attempt, and a coverage proof
  that every catalog item strictly below the required witness order is
  certified. The counting theorem lower-bounds the record length by the
  exhaustion gap.

  Catalog scope note (statement-adequacy guard): the twelve-member
  `DirectMeasureClass` enum is a catalog bookkeeping object mirroring
  the direct-measure barrier package enumeration of the companion
  orientation-boundary artifact. It does not restate the twelve
  impossibility proofs; benchmark-locally, only the additive member is
  refuted in Lean (`WitnessOrder.ko7_no_directWhole_witness`), and the
  remaining classes are cited.

  Relation: none (finite catalog bookkeeping over `WLevel`).
  Property: metadata / counting theorem layer.
  Trust: kernel-only; baseline axioms.
-/
import KO7Benchmark.WitnessOrder
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.ExhaustionGap

open KO7Benchmark.WitnessOrder

/-! ## Catalogs, gaps, and typed-abstention records -/

/-- A supervisory catalog: the number of distinct catalog-listed witness
    attempts at each witness-language layer. -/
structure SupervisoryCatalog where
  budget : WLevel → Nat

/-- The witness-language levels strictly below a level, in the canonical
    order. -/
def levelsBelow : WLevel → List WLevel
  | .directWhole => []
  | .importedWhole => [.directWhole]
  | .transformedCall => [.directWhole, .importedWhole]
  | .externalCert => [.directWhole, .importedWhole, .transformedCall]

/-- The task-relativized exhaustion gap at a required witness order:
    the sum of the per-layer budgets strictly below it. -/
def exhaustionGap (C : SupervisoryCatalog) : WLevel → Nat
  | .directWhole => 0
  | .importedWhole => C.budget .directWhole
  | .transformedCall => C.budget .directWhole + C.budget .importedWhole
  | .externalCert =>
      C.budget .directWhole + C.budget .importedWhole +
        C.budget .transformedCall

/-- A typed-abstention record at required order `κ`: a list of failure
    certificates, each naming a layer and an attempt index, together
    with the coverage proof that every catalog item strictly below `κ`
    is certified. (The list may contain additional certificates.) -/
structure TypedAbstentionRecord (C : SupervisoryCatalog) (κ : WLevel) where
  certificates : List (WLevel × Nat)
  covers : ∀ ℓ ∈ levelsBelow κ, ∀ i < C.budget ℓ, (ℓ, i) ∈ certificates

/-- The certificates a layer contributes: one per budgeted attempt. -/
def tagged (ℓ : WLevel) (n : Nat) : List (WLevel × Nat) :=
  (List.range n).map fun i => (ℓ, i)

theorem tagged_length (ℓ : WLevel) (n : Nat) : (tagged ℓ n).length = n := by
  simp [tagged]

theorem mem_tagged {a : WLevel × Nat} {ℓ : WLevel} {n : Nat} :
    a ∈ tagged ℓ n ↔ ∃ i < n, a = (ℓ, i) := by
  simp only [tagged, List.mem_map, List.mem_range]
  constructor
  · rintro ⟨i, hi, rfl⟩; exact ⟨i, hi, rfl⟩
  · rintro ⟨i, hi, rfl⟩; exact ⟨i, hi, rfl⟩

theorem tagged_nodup (ℓ : WLevel) (n : Nat) : (tagged ℓ n).Nodup :=
  (List.nodup_range).map fun _ _ h => congrArg Prod.snd h

theorem tagged_disjoint {ℓ₁ ℓ₂ : WLevel} (h : ℓ₁ ≠ ℓ₂) (m n : Nat) :
    List.Disjoint (tagged ℓ₁ m) (tagged ℓ₂ n) := by
  intro a h₁ h₂
  obtain ⟨i, _, rfl⟩ := mem_tagged.mp h₁
  obtain ⟨j, _, hj⟩ := mem_tagged.mp h₂
  exact h (congrArg Prod.fst hj)

/-- The required certificate list at order `κ`: the tagged attempt lists
    of every layer strictly below `κ`, concatenated. -/
def requiredCertificates (C : SupervisoryCatalog) : WLevel → List (WLevel × Nat)
  | .directWhole => []
  | .importedWhole => tagged .directWhole (C.budget .directWhole)
  | .transformedCall =>
      tagged .directWhole (C.budget .directWhole) ++
        tagged .importedWhole (C.budget .importedWhole)
  | .externalCert =>
      tagged .directWhole (C.budget .directWhole) ++
        (tagged .importedWhole (C.budget .importedWhole) ++
          tagged .transformedCall (C.budget .transformedCall))

theorem requiredCertificates_length (C : SupervisoryCatalog) (κ : WLevel) :
    (requiredCertificates C κ).length = exhaustionGap C κ := by
  cases κ <;>
    simp [requiredCertificates, exhaustionGap, tagged_length, Nat.add_assoc]

theorem requiredCertificates_nodup (C : SupervisoryCatalog) (κ : WLevel) :
    (requiredCertificates C κ).Nodup := by
  cases κ with
  | directWhole => simp [requiredCertificates]
  | importedWhole => exact tagged_nodup _ _
  | transformedCall =>
      exact (tagged_nodup _ _).append (tagged_nodup _ _)
        (tagged_disjoint (by decide) _ _)
  | externalCert =>
      refine (tagged_nodup _ _).append ?_ ?_
      · exact (tagged_nodup _ _).append (tagged_nodup _ _)
          (tagged_disjoint (by decide) _ _)
      · intro a h₁ h₂
        obtain ⟨i, _, rfl⟩ := mem_tagged.mp h₁
        rcases List.mem_append.mp h₂ with h₂ | h₂
        · obtain ⟨j, _, hj⟩ := mem_tagged.mp h₂
          exact (by decide : WLevel.directWhole ≠ .importedWhole)
            (congrArg Prod.fst hj)
        · obtain ⟨j, _, hj⟩ := mem_tagged.mp h₂
          exact (by decide : WLevel.directWhole ≠ .transformedCall)
            (congrArg Prod.fst hj)

theorem requiredCertificates_subset {C : SupervisoryCatalog} {κ : WLevel}
    (R : TypedAbstentionRecord C κ) :
    requiredCertificates C κ ⊆ R.certificates := by
  intro a ha
  cases κ with
  | directWhole => simp [requiredCertificates] at ha
  | importedWhole =>
      obtain ⟨i, hi, rfl⟩ := mem_tagged.mp ha
      exact R.covers _ (by simp [levelsBelow]) i hi
  | transformedCall =>
      rcases List.mem_append.mp ha with ha | ha <;>
        · obtain ⟨i, hi, rfl⟩ := mem_tagged.mp ha
          exact R.covers _ (by simp [levelsBelow]) i hi
  | externalCert =>
      rcases List.mem_append.mp ha with ha | ha
      · obtain ⟨i, hi, rfl⟩ := mem_tagged.mp ha
        exact R.covers _ (by simp [levelsBelow]) i hi
      · rcases List.mem_append.mp ha with ha | ha <;>
          · obtain ⟨i, hi, rfl⟩ := mem_tagged.mp ha
            exact R.covers _ (by simp [levelsBelow]) i hi

/-- **Typed abstention requires exhaustion work of at least the gap.**
    (PRT manuscript, Prop. "T4 requires exhaustion work of at least
    E(x)".) Any typed-abstention record at required order `κ` carries at
    least `exhaustionGap C κ` failure certificates. -/
theorem typedAbstention_length_ge_exhaustionGap
    {C : SupervisoryCatalog} {κ : WLevel}
    (R : TypedAbstentionRecord C κ) :
    exhaustionGap C κ ≤ R.certificates.length := by
  have h := ((requiredCertificates_nodup C κ).subperm
    (requiredCertificates_subset R)).length_le
  simpa [requiredCertificates_length] using h

/-! ## The direct-measure catalog and the recursor corollary -/

/-- The twelve direct-measure classes of the companion barrier package,
    as a catalog bookkeeping enum. See the module docstring for the
    statement-adequacy scope note. -/
inductive DirectMeasureClass
  | additive
  | transparentCompositional
  | affine
  | restrictedQuadratic
  | boundedCrossTermQuadratic
  | boundedMultilinear
  | generalizedBoundedPolynomial
  | maxPlus
  | trackedComponentwise
  | trackedPrimaryLex
  | balancedMixedCoordinate
  | weightedScalarProjection
deriving DecidableEq, Repr

/-- The catalog list of the twelve direct-measure classes. -/
def directMeasureClasses : List DirectMeasureClass :=
  [.additive, .transparentCompositional, .affine, .restrictedQuadratic,
   .boundedCrossTermQuadratic, .boundedMultilinear,
   .generalizedBoundedPolynomial, .maxPlus, .trackedComponentwise,
   .trackedPrimaryLex, .balancedMixedCoordinate, .weightedScalarProjection]

theorem directMeasureClasses_length : directMeasureClasses.length = 12 := rfl

theorem directMeasureClasses_nodup : directMeasureClasses.Nodup := by decide

theorem directMeasureClasses_complete :
    ∀ c : DirectMeasureClass, c ∈ directMeasureClasses := by
  intro c; cases c <;> decide

/-- A catalog covers the direct-measure catalog when its direct-whole
    budget lists at least the twelve named classes. -/
def CoversDirectCatalog (C : SupervisoryCatalog) : Prop :=
  12 ≤ C.budget .directWhole

/-- **Exhaustion gap on the primitive recursor** (PRT manuscript,
    Cor. "exhaustion gap on the recursor"): for the duplicating kernel,
    the required witness order under the benchmark contract is the
    transformed-call level (`ko7_kappaContract_le_transformedCall` and
    `ko7_kappaContract_gt_importedWhole`), so a catalog covering the
    direct-measure catalog has exhaustion gap at least
    `12 + budget(importedWhole)` there. -/
theorem recursor_exhaustionGap_lower_bound (C : SupervisoryCatalog)
    (h : CoversDirectCatalog C) :
    12 + C.budget .importedWhole ≤ exhaustionGap C .transformedCall := by
  unfold CoversDirectCatalog at h
  simp only [exhaustionGap]
  omega

/-- A typed abstention on the duplicating kernel, at the benchmark
    contract's required order, carries at least `12 + |W1-catalog|`
    failure certificates. Countable audit criterion for the supervisory
    axis. -/
theorem ko7_typedAbstention_certificate_bound (C : SupervisoryCatalog)
    (h : CoversDirectCatalog C)
    (R : TypedAbstentionRecord C .transformedCall) :
    12 + C.budget .importedWhole ≤ R.certificates.length :=
  le_trans (recursor_exhaustionGap_lower_bound C h)
    (typedAbstention_length_ge_exhaustionGap R)

/-! ## Non-vacuity witness (release-gate R5) -/

/-- A minimal catalog covering the direct-measure catalog with one
    imported-whole attempt. -/
def minimalCatalog : SupervisoryCatalog where
  budget
    | .directWhole => 12
    | .importedWhole => 1
    | .transformedCall => 0
    | .externalCert => 0

/-- The exhaustive typed-abstention record over the minimal catalog:
    exactly the required certificates. `TypedAbstentionRecord` is
    inhabited, so the counting theorem is not vacuous. -/
def minimalRecord : TypedAbstentionRecord minimalCatalog .transformedCall where
  certificates := requiredCertificates minimalCatalog .transformedCall
  covers := by
    intro ℓ hℓ i hi
    simp only [levelsBelow, List.mem_cons, List.not_mem_nil, or_false] at hℓ
    rcases hℓ with rfl | rfl <;>
      · simp only [requiredCertificates, List.mem_append]
        first
          | exact Or.inl (mem_tagged.mpr ⟨i, hi, rfl⟩)
          | exact Or.inr (mem_tagged.mpr ⟨i, hi, rfl⟩)

theorem minimalRecord_length :
    minimalRecord.certificates.length = 13 := by
  simp [minimalRecord, requiredCertificates_length, exhaustionGap,
    minimalCatalog]

end KO7Benchmark.PaperB.ExhaustionGap
