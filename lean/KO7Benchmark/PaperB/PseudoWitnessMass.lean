/-
  Pseudo-witness mass, free energies, and the bottleneck signature.

  Mechanizes the distributional layer of Rahnama_PRT_Benchmark.tex §3
  (verifier mass and pseudo-witness mass, free energies, bottleneck
  signature, and the theorem that the bottleneck signature is
  equivalent to pseudo-mass domination). Before this module the
  definitions were manuscript-level.

  Model: a finite candidate family carries a nonnegative real mass, a
  witness-language level, and a recorded verifier verdict. The verdict
  is recorded as data (`Bool`); the propositional bridge from a real
  verifier is the instantiating caller's obligation, exactly as the
  manuscript discharges it by the external Lean/TTT2 artifacts rather
  than by model self-report.

  Relation: none (finite measure bookkeeping over `WLevel`).
  Property: metadata / distributional theorem layer.
  Trust: kernel-only; baseline axioms (classical real analysis).
-/
import KO7Benchmark.WitnessOrder
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.PseudoWitnessMass

open KO7Benchmark.WitnessOrder
open Finset

/-- A finite generation model: candidate proof objects with nonnegative
    mass, a witness-language level, and a recorded verifier verdict. -/
structure GenerationModel (ι : Type) [Fintype ι] where
  mass : ι → ℝ
  mass_nonneg : ∀ i, 0 ≤ mass i
  level : ι → WLevel
  valid : ι → Bool

variable {ι : Type} [Fintype ι]

/-- Verifier mass at a level: total mass of verifier-accepted candidates
    at that witness-language level. -/
def checkMass (G : GenerationModel ι) (ℓ : WLevel) : ℝ :=
  ∑ i ∈ univ.filter (fun i => G.level i = ℓ ∧ G.valid i = true), G.mass i

/-- Pseudo-witness mass at a level: total mass of verifier-rejected
    candidates at that witness-language level. -/
def pseudoMass (G : GenerationModel ι) (ℓ : WLevel) : ℝ :=
  ∑ i ∈ univ.filter (fun i => G.level i = ℓ ∧ G.valid i = false), G.mass i

theorem checkMass_nonneg (G : GenerationModel ι) (ℓ : WLevel) :
    0 ≤ checkMass G ℓ :=
  Finset.sum_nonneg fun i _ => G.mass_nonneg i

theorem pseudoMass_nonneg (G : GenerationModel ι) (ℓ : WLevel) :
    0 ≤ pseudoMass G ℓ :=
  Finset.sum_nonneg fun i _ => G.mass_nonneg i

/-- A rejected candidate with positive mass makes the pseudo mass
    positive: the non-vacuity bridge from pseudo-witness objects to
    pseudo-witness mass. -/
theorem pseudoMass_pos_of_witness (G : GenerationModel ι) {ℓ : WLevel}
    {i : ι} (hlev : G.level i = ℓ) (hval : G.valid i = false)
    (hmass : 0 < G.mass i) : 0 < pseudoMass G ℓ := by
  refine Finset.sum_pos' (fun j _ => G.mass_nonneg j) ?_
  exact ⟨i, by simp [hlev, hval], hmass⟩

/-- An accepted candidate with positive mass makes the verifier mass
    positive. -/
theorem checkMass_pos_of_witness (G : GenerationModel ι) {ℓ : WLevel}
    {i : ι} (hlev : G.level i = ℓ) (hval : G.valid i = true)
    (hmass : 0 < G.mass i) : 0 < checkMass G ℓ := by
  refine Finset.sum_pos' (fun j _ => G.mass_nonneg j) ?_
  exact ⟨i, by simp [hlev, hval], hmass⟩

/-- Free energy of the verifier mass at a level. -/
noncomputable def checkFreeEnergy (G : GenerationModel ι) (ℓ : WLevel) : ℝ :=
  - Real.log (checkMass G ℓ)

/-- Free energy of the pseudo-witness mass at a level. -/
noncomputable def pseudoFreeEnergy (G : GenerationModel ι) (ℓ : WLevel) : ℝ :=
  - Real.log (pseudoMass G ℓ)

/-- The bottleneck signature between a lower level `ℓ` and a higher
    level `ℓ'`: the pseudo free energy at `ℓ` lies strictly below the
    verifier free energy at `ℓ'`. (PRT manuscript,
    Def. "bottleneck signature".) -/
def BottleneckSignature (G : GenerationModel ι) (ℓ ℓ' : WLevel) : Prop :=
  pseudoFreeEnergy G ℓ < checkFreeEnergy G ℓ'

/-- The bottleneck signature is equivalent to pseudo-mass domination
    when both masses are positive. (PRT manuscript, Thm. "bottleneck
    signature implies pseudo-domination", both directions.) -/
theorem bottleneckSignature_iff_pseudoDomination (G : GenerationModel ι)
    (ℓ ℓ' : WLevel)
    (hp : 0 < pseudoMass G ℓ) (hc : 0 < checkMass G ℓ') :
    BottleneckSignature G ℓ ℓ' ↔ checkMass G ℓ' < pseudoMass G ℓ := by
  unfold BottleneckSignature pseudoFreeEnergy checkFreeEnergy
  rw [neg_lt_neg_iff]
  exact Real.strictMonoOn_log.lt_iff_lt
    (Set.mem_Ioi.mpr hc) (Set.mem_Ioi.mpr hp)

/-- Forward direction packaged separately for citation. -/
theorem pseudoDomination_of_bottleneckSignature (G : GenerationModel ι)
    {ℓ ℓ' : WLevel}
    (hp : 0 < pseudoMass G ℓ) (hc : 0 < checkMass G ℓ')
    (h : BottleneckSignature G ℓ ℓ') :
    checkMass G ℓ' < pseudoMass G ℓ :=
  (bottleneckSignature_iff_pseudoDomination G ℓ ℓ' hp hc).mp h

/-! ## Non-vacuity witness (release-gate R5)

A two-candidate model: three quarters of the mass on a rejected
direct-whole candidate, one quarter on an accepted transformed-call
candidate. The bottleneck signature holds between the direct-whole and
transformed-call levels. -/

/-- Toy generation model over `Bool`: `true` is the rejected
    direct-whole candidate with mass `3/4`; `false` is the accepted
    transformed-call candidate with mass `1/4`. -/
noncomputable def toyModel : GenerationModel Bool where
  mass := fun i => if i then 3/4 else 1/4
  mass_nonneg := by intro i; cases i <;> norm_num
  level := fun i => if i then .directWhole else .transformedCall
  valid := fun i => !i

theorem toyModel_pseudoMass :
    pseudoMass toyModel WLevel.directWhole = 3/4 := by
  simp [pseudoMass, toyModel, Finset.sum_filter]

theorem toyModel_checkMass :
    checkMass toyModel WLevel.transformedCall = 1/4 := by
  simp [checkMass, toyModel, Finset.sum_filter]

/-- The bottleneck signature is satisfiable: the toy model exhibits it
    between the direct-whole and transformed-call levels. -/
theorem bottleneckSignature_satisfiable :
    BottleneckSignature toyModel WLevel.directWhole WLevel.transformedCall := by
  have hp : (0:ℝ) < pseudoMass toyModel WLevel.directWhole := by
    rw [toyModel_pseudoMass]; norm_num
  have hc : (0:ℝ) < checkMass toyModel WLevel.transformedCall := by
    rw [toyModel_checkMass]; norm_num
  rw [bottleneckSignature_iff_pseudoDomination _ _ _ hp hc,
    toyModel_pseudoMass, toyModel_checkMass]
  norm_num

end KO7Benchmark.PaperB.PseudoWitnessMass
