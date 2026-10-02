/-
  Residual direct-measure families for scorer decisions.

  Relation: KO7Kernel.Step, SchemaKernel.RootStep/Step, and the SANS control Step, exactly as named by each theorem.
  Closure: KO7Kernel.Step is the eight-rule root relation; schema and SANS multiset obstructions use a root rule embedded in their contextual Step.
  Property: residual depth, flag, constellation, nesting-multiset, and exact ordinal-recoding proposals receive method-identical family obstructions or controls not owned by the other scoring-anchor modules.
  Trust: mathlib and existing benchmark modules only; all proofs are checked by Lean and no extra logical assumptions are introduced here.
-/
import Mathlib.Tactic
import Mathlib.SetTheory.Ordinal.Basic
import KO7Benchmark.KO7Kernel
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.ScoringAnchors.MeasureFailures
import KO7Benchmark.ScoringAnchors.ControlContrast

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.ResidualMeasureFamilies

/-! ## KO7 merge-neutral nesting-depth family -/

namespace KO7Residual

open KO7Benchmark.KO7Kernel
open Trace

/-- Measures whose merge node is depth-neutral: merge takes the maximum of
    the two branch values and adds no level. -/
structure MergeNeutralMeasure where
  eval : Trace → Nat
  eval_merge : ∀ a b : Trace, eval (merge a b) = max (eval a) (eval b)

/-- Every merge-neutral maximum measure fails strict orientation of KO7's
    idempotent merge rule, independently of the recursive rule. -/
theorem no_mergeNeutral_orients_step (M : MergeNeutralMeasure) :
    ¬ (∀ {a b : Trace}, Step a b → M.eval b < M.eval a) := by
  intro h
  have hlt : M.eval void < M.eval (merge void void) :=
    h (Step.R_merge_cancel void)
  rw [M.eval_merge void void] at hlt
  simp at hlt

/-- Exact merge-neutral nesting depth used by the Orientation Boundary
    concrete family. -/
@[simp] def nestingDepth : Trace → Nat
  | .void => 0
  | .delta t => nestingDepth t + 1
  | .integrate t => nestingDepth t + 1
  | .merge a b => max (nestingDepth a) (nestingDepth b)
  | .app a b => max (nestingDepth a) (nestingDepth b) + 1
  | .recDelta b s n => max (max (nestingDepth b) (nestingDepth s)) (nestingDepth n) + 1
  | .eqW a b => max (nestingDepth a) (nestingDepth b) + 1

def nestingDepthMeasure : MergeNeutralMeasure where
  eval := nestingDepth
  eval_merge := by
    intro a b
    rfl

/-- Non-vacuity: the exact nesting-depth member is not constant. -/
theorem nestingDepth_nonconstant :
    nestingDepth void = 0 ∧ nestingDepth (delta void) = 1 := by
  constructor <;> rfl

theorem nestingDepth_not_step_orienting :
    ¬ (∀ {a b : Trace}, Step a b → nestingDepth b < nestingDepth a) :=
  no_mergeNeutral_orients_step nestingDepthMeasure

/-- A one-level merge bump drops strictly on every merge-cancellation rule. -/
@[simp] def mergeBumpDepth : Trace → Nat
  | .void => 0
  | .delta t => mergeBumpDepth t + 1
  | .integrate t => mergeBumpDepth t + 1
  | .merge a b => max (mergeBumpDepth a) (mergeBumpDepth b) + 1
  | .app a b => max (mergeBumpDepth a) (mergeBumpDepth b) + 1
  | .recDelta b s n => max (max (mergeBumpDepth b) (mergeBumpDepth s)) (mergeBumpDepth n) + 1
  | .eqW a b => max (mergeBumpDepth a) (mergeBumpDepth b) + 1

/-- Necessity control for the local blocker: removing merge-neutrality permits
    a depth measure that strictly orients every merge-cancellation instance. -/
theorem mergeNeutrality_is_load_bearing :
    (∀ t : Trace, mergeBumpDepth t < mergeBumpDepth (merge t t)) ∧
      ¬ (∀ a b : Trace,
        mergeBumpDepth (merge a b) = max (mergeBumpDepth a) (mergeBumpDepth b)) := by
  constructor
  · intro t
    simp [mergeBumpDepth]
  · intro h
    have hv := h void void
    simp [mergeBumpDepth] at hv

/-! ## Recursor-depth plus a constant -/

/-- Exact direct recursor-depth proposal: only the third recursor argument
    contributes below a recursor node; wrappers aggregate by maximum. -/
@[simp] def recursorDepth : Trace → Nat
  | .void => 0
  | .delta t => recursorDepth t
  | .integrate t => recursorDepth t
  | .merge a b => max (recursorDepth a) (recursorDepth b)
  | .app a b => max (recursorDepth a) (recursorDepth b)
  | .recDelta _ _ n => recursorDepth n + 1
  | .eqW a b => max (recursorDepth a) (recursorDepth b)

def recursorDepthPlus (k : Nat) (t : Trace) : Nat :=
  recursorDepth t + k

/-- The recursive source and target tie for an entire input family, not only
    for one ground example. -/
theorem recursorDepthPlus_recursive_tie (k : Nat) (b n : Trace) :
    recursorDepthPlus k (app void (recDelta b void n)) =
      recursorDepthPlus k (recDelta b void (delta n)) := by
  simp [recursorDepthPlus, recursorDepth]

theorem no_recursorDepthPlus_orients_step (k : Nat) :
    ¬ (∀ {a b : Trace}, Step a b →
      recursorDepthPlus k b < recursorDepthPlus k a) := by
  intro h
  have hlt := h (Step.R_rec_succ void void void)
  have heq := recursorDepthPlus_recursive_tie k void void
  rw [heq] at hlt
  exact (Nat.lt_irrefl _ hlt)

/-! ## Exact ordinal recodings of that same direct depth -/

/-- Any ordinal-valued post-recoding of the exact recursor depth. -/
def ordinalRecoding (rho : Nat → Ordinal.{0}) (t : Trace) : Ordinal.{0} :=
  rho (recursorDepth t)

theorem ordinalRecoding_recursive_tie
    (rho : Nat → Ordinal.{0}) (b n : Trace) :
    ordinalRecoding rho (app void (recDelta b void n)) =
      ordinalRecoding rho (recDelta b void (delta n)) := by
  simp [ordinalRecoding, recursorDepth]

/-- This is only a theorem about ordinal recodings of this exact depth
    proposal. It does not classify arbitrary ordinal interpretations. -/
theorem no_ordinalRecoding_of_recursorDepth_orients_step
    (rho : Nat → Ordinal.{0}) :
    ¬ (∀ {a b : Trace}, Step a b →
      ordinalRecoding rho b < ordinalRecoding rho a) := by
  intro h
  have hlt := h (Step.R_rec_succ void void void)
  have heq := ordinalRecoding_recursive_tie rho void void
  rw [heq] at hlt
  exact (lt_irrefl _ hlt)

/-! ## Top-delta flag family -/

@[simp] def deltaFlagTop : Trace → Nat
  | .delta _ => 1
  | _ => 0

def deltaFlagAffine (scale bias : Nat) (t : Trace) : Nat :=
  scale * deltaFlagTop t + bias

theorem deltaFlagTop_nonconstant :
    deltaFlagTop void = 0 ∧ deltaFlagTop (delta void) = 1 := by
  constructor <;> rfl

/-- Every affine recoding of the single top-delta flag fails the merge-void
    rule: for positive scale it rises, and for zero scale it ties. -/
theorem no_deltaFlagAffine_orients_step (scale bias : Nat) :
    ¬ (∀ {a b : Trace}, Step a b →
      deltaFlagAffine scale bias b < deltaFlagAffine scale bias a) := by
  intro h
  have hlt := h (Step.R_merge_void_left (delta void))
  simp [deltaFlagAffine, deltaFlagTop] at hlt

end KO7Residual

/-! ## SANS control for recursor depth and its ordinal recodings -/

namespace SANSControl

open KO7Benchmark.SANSTests
open SANSTerm

/-- Copy-removed analogue of the KO7 recursor-depth proposal. The successor
    and unary wrapper are transparent to this rank. -/
@[simp] def recursorDepth : SANSTerm → Nat
  | .var _ => 0
  | .z => 0
  | .s t => recursorDepth t
  | .g t => recursorDepth t
  | .f _ _ n => recursorDepth n + 1

def recursorDepthPlus (k : Nat) (t : SANSTerm) : Nat :=
  recursorDepth t + k

theorem recursorDepth_nonconstant :
    recursorDepth z = 0 ∧ recursorDepth (f z z z) = 1 := by
  constructor <;> rfl

/-- Removing the copied payload does not rescue this particular rank family:
    the source and target still tie for every recursive instance. -/
theorem recursorDepthPlus_recursive_tie
    (k : Nat) (x y n : SANSTerm) :
    recursorDepthPlus k (g (f x y n)) =
      recursorDepthPlus k (f x y (s n)) := by
  simp [recursorDepthPlus, recursorDepth]

theorem no_recursorDepthPlus_orients_step (k : Nat) :
    ¬ (∀ {a b : SANSTerm}, Step a b →
      recursorDepthPlus k b < recursorDepthPlus k a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z z z))
  have heq := recursorDepthPlus_recursive_tie k z z z
  rw [heq] at hlt
  exact (Nat.lt_irrefl _ hlt)

def ordinalRecoding
    (rho : Nat → Ordinal.{0}) (t : SANSTerm) : Ordinal.{0} :=
  rho (recursorDepth t)

theorem ordinalRecoding_recursive_tie
    (rho : Nat → Ordinal.{0}) (x y n : SANSTerm) :
    ordinalRecoding rho (g (f x y n)) =
      ordinalRecoding rho (f x y (s n)) := by
  simp [ordinalRecoding, recursorDepth]

theorem no_ordinalRecoding_of_recursorDepth_orients_step
    (rho : Nat → Ordinal.{0}) :
    ¬ (∀ {a b : SANSTerm}, Step a b →
      ordinalRecoding rho b < ordinalRecoding rho a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z z z))
  have heq := ordinalRecoding_recursive_tie rho z z z
  rw [heq] at hlt
  exact (lt_irrefl _ hlt)

end SANSControl

/-! ## Strictly monotone post-processing of additive measures -/

namespace StrictPostprocessing

open KO7Benchmark.SchemaTests
open SKTerm
open KO7Benchmark.ScoringAnchors.MeasureFailures

def postprocess
    (rho : Nat → Nat) (M : GenAdditive) (t : SKTerm) : Nat :=
  rho (M.eval t)

/-- The same fixed recursive-rule instance used by the additive family has
    source value at most target value for every constructor-weight assignment. -/
theorem genAdditive_recursive_counterexample_le (M : GenAdditive) :
    M.eval (f z (s z) (s z)) ≤
      M.eval (g (s z) (f z (s z) z)) := by
  simp only [
    GenAdditive.eval_g,
    GenAdditive.eval_f,
    GenAdditive.eval_s,
    GenAdditive.eval_z
  ]
  omega

/-- Strictly increasing post-processing cannot repair any member of the exact
    additive constructor-weight family on the duplicating schema. -/
theorem no_strictMono_postprocess_genAdditive_orients_step
    (M : GenAdditive) (rho : Nat → Nat) (hrho : StrictMono rho) :
    ¬ (∀ {a b : SKTerm}, Step a b →
      postprocess rho M b < postprocess rho M a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z (s z) z))
  have hle := genAdditive_recursive_counterexample_le M
  have hmono :
      rho (M.eval (f z (s z) (s z))) ≤
        rho (M.eval (g (s z) (f z (s z) z))) :=
    hrho.monotone hle
  exact (not_lt_of_ge hmono) hlt

/-- Copy removal is the exact control: every strictly increasing recoding of
    the certified SANS additive witness still orients every contextual step. -/
theorem sans_strictMono_postprocess_control_orients_step
    (rho : Nat → Nat) (hrho : StrictMono rho) :
    ∀ {a b : KO7Benchmark.SANSTests.SANSTerm},
      KO7Benchmark.SANSTests.Step a b →
      rho (KO7Benchmark.ScoringAnchors.ControlContrast.SANSAdditive.control.eval b) <
        rho (KO7Benchmark.ScoringAnchors.ControlContrast.SANSAdditive.control.eval a) := by
  intro a b h
  exact hrho
    (KO7Benchmark.ScoringAnchors.ControlContrast.SANSAdditive.control_orients_step h)

end StrictPostprocessing

/-! ## Exact constellation-size proposal on KO7 -/

namespace KO7Constellation

open KO7Benchmark.KO7Kernel
open Trace

inductive Constellation where
  | atom : Constellation
  | deltaNode : Constellation → Constellation
  | integrateNode : Constellation → Constellation
  | mergeNode : Constellation → Constellation → Constellation
  | appNode : Constellation → Constellation → Constellation
  | recNode : Constellation → Constellation → Constellation → Constellation
  | eqNode : Constellation → Constellation → Constellation
deriving DecidableEq, Repr

@[simp] def toConstellation : Trace → Constellation
  | .void => .atom
  | .delta t => .deltaNode (toConstellation t)
  | .integrate t => .integrateNode (toConstellation t)
  | .merge a b => .mergeNode (toConstellation a) (toConstellation b)
  | .app a b => .appNode (toConstellation a) (toConstellation b)
  | .recDelta b s n =>
      .recNode (toConstellation b) (toConstellation s) (toConstellation n)
  | .eqW a b => .eqNode (toConstellation a) (toConstellation b)

@[simp] def constellationSize : Constellation → Nat
  | .atom => 1
  | .deltaNode c => constellationSize c + 1
  | .integrateNode c => constellationSize c + 1
  | .mergeNode a b => constellationSize a + constellationSize b + 1
  | .appNode a b => constellationSize a + constellationSize b + 1
  | .recNode b s n =>
      constellationSize b + constellationSize s + constellationSize n + 1
  | .eqNode a b => constellationSize a + constellationSize b + 1

theorem constellationSize_pos (c : Constellation) :
    1 ≤ constellationSize c := by
  induction c <;> simp [constellationSize, *]

/-- The copied step argument contributes one extra constellation copy on the
    target side. Since every constellation has positive size, the target can
    never be strictly smaller under this measure. -/
theorem constellation_recursive_not_decreasing (b s n : Trace) :
    constellationSize (toConstellation (recDelta b s (delta n))) ≤
      constellationSize (toConstellation (app s (recDelta b s n))) := by
  simp only [toConstellation, constellationSize]
  have hs := constellationSize_pos (toConstellation s)
  omega

theorem no_constellationSize_orients_step :
    ¬ (∀ {a b : Trace}, Step a b →
      constellationSize (toConstellation b) <
        constellationSize (toConstellation a)) := by
  intro h
  have hlt := h (Step.R_rec_succ void void void)
  have hle := constellation_recursive_not_decreasing void void void
  omega

end KO7Constellation

/-! ## Copy-removed node-count control for constellation size -/

namespace SANSNodeCount

open KO7Benchmark.SANSTests
open SANSTerm

@[simp] def nodeCount : SANSTerm → Nat
  | .var _ => 1
  | .z => 1
  | .s t => nodeCount t + 1
  | .g t => nodeCount t + 1
  | .f x y n => nodeCount x + nodeCount y + nodeCount n + 1

theorem nodeCount_nonconstant :
    nodeCount z = 1 ∧ nodeCount (s z) = 2 := by
  constructor <;> rfl

/-- Copy removal changes the schema increase into an exact tie for every
    recursive instance, so unit node count still is not a strict measure. -/
theorem recursive_rule_ties (x y n : SANSTerm) :
    nodeCount (g (f x y n)) = nodeCount (f x y (s n)) := by
  simp [nodeCount]
  omega

theorem no_nodeCount_orients_step :
    ¬ (∀ {a b : SANSTerm}, Step a b → nodeCount b < nodeCount a) := by
  intro h
  have hlt := h (Step.root (RootStep.succ z z z))
  rw [recursive_rule_ties z z z] at hlt
  exact (Nat.lt_irrefl _ hlt)

end SANSNodeCount

/-! ## Single-pass multisets over immediate-subterm nesting ranks -/

namespace NestingMultiset

/-- Standard Dershowitz-Manna multiset extension of the strict natural order:
    a nonempty part Z of N is replaced by elements each strictly below some
    element of Z. -/
def DMLT (M N : Multiset Nat) : Prop :=
  ∃ X Y Z : Multiset Nat,
    Z ≠ 0 ∧
    M = X + Y ∧
    N = X + Z ∧
    ∀ y ∈ Y, ∃ z ∈ Z, y < z

/-- Any element on the smaller side is bounded by an element retained or
    removed from the larger side. -/
theorem dm_element_bounded {M N : Multiset Nat}
    (h : DMLT M N) {m : Nat} (hm : m ∈ M) :
    ∃ n ∈ N, m ≤ n := by
  rcases h with ⟨X, Y, Z, hZ, rfl, rfl, hYZ⟩
  simp only [Multiset.mem_add] at hm
  rcases hm with hm | hm
  · exact ⟨m, by simp [hm], Nat.le_refl m⟩
  · rcases hYZ m hm with ⟨n, hn, hmn⟩
    exact ⟨n, by simp [hn], Nat.le_of_lt hmn⟩

/-- Non-vacuity of the exact multiset relation. -/
theorem dm_nonempty : DMLT {0} {1} := by
  refine ⟨0, {0}, {1}, by simp, by simp, by simp, ?_⟩
  intro y hy
  have hy0 : y = 0 := by simpa using hy
  subst y
  exact ⟨1, by simp, by decide⟩

namespace Schema

open KO7Benchmark.SchemaTests
open SKTerm

/-- Nesting rank used by the single-pass multiset proposal. -/
@[simp] def nestingRank : SKTerm → Nat
  | .var _ => 0
  | .z => 0
  | .s t => nestingRank t + 1
  | .g a b => max (nestingRank a) (nestingRank b) + 1
  | .f x y n => max (nestingRank x) (max (nestingRank y) (nestingRank n)) + 1

/-- The proposal records nesting ranks of immediate subterms once. -/
def singlePassNestingBag : SKTerm → Multiset Nat
  | .var _ => 0
  | .z => 0
  | .s t => {nestingRank t}
  | .g a b => {nestingRank a, nestingRank b}
  | .f x y n => {nestingRank x, nestingRank y, nestingRank n}

theorem nestingRank_nonconstant :
    nestingRank z = 0 ∧ nestingRank (s z) = 1 := by
  constructor <;> rfl

private theorem source_members_eq_one {m : Nat}
    (hm : m ∈ singlePassNestingBag (f (s z) (s z) (s z))) :
    m = 1 := by
  simpa [singlePassNestingBag, nestingRank] using hm

private theorem target_has_two :
    2 ∈ singlePassNestingBag (g (s z) (f (s z) (s z) z)) := by
  decide

/-- Exact failure of the manuscript's single-pass multiset over nesting ranks. -/
theorem singlePass_nesting_multiset_fails_recursive_root :
    ¬ DMLT
      (singlePassNestingBag (g (s z) (f (s z) (s z) z)))
      (singlePassNestingBag (f (s z) (s z) (s z))) := by
  intro h
  rcases dm_element_bounded h target_has_two with ⟨m, hm, htwo⟩
  have hm1 := source_members_eq_one hm
  omega

theorem no_singlePass_nesting_multiset_orients_step :
    ¬ (∀ {a b : SKTerm}, Step a b →
      DMLT (singlePassNestingBag b) (singlePassNestingBag a)) := by
  intro h
  exact singlePass_nesting_multiset_fails_recursive_root
    (h (Step.root (RootStep.succ (s z) (s z) z)))

end Schema

namespace SANS

open KO7Benchmark.SANSTests
open SANSTerm

@[simp] def nestingRank : SANSTerm → Nat
  | .var _ => 0
  | .z => 0
  | .s t => nestingRank t + 1
  | .g t => nestingRank t + 1
  | .f x y n => max (nestingRank x) (max (nestingRank y) (nestingRank n)) + 1

def singlePassNestingBag : SANSTerm → Multiset Nat
  | .var _ => 0
  | .z => 0
  | .s t => {nestingRank t}
  | .g t => {nestingRank t}
  | .f x y n => {nestingRank x, nestingRank y, nestingRank n}

theorem nestingRank_nonconstant :
    nestingRank z = 0 ∧ nestingRank (s z) = 1 := by
  constructor <;> rfl

private theorem source_members_eq_one {m : Nat}
    (hm : m ∈ singlePassNestingBag (f (s z) (s z) (s z))) :
    m = 1 := by
  simpa [singlePassNestingBag, nestingRank] using hm

private theorem target_has_two :
    2 ∈ singlePassNestingBag (g (f (s z) (s z) z)) := by
  decide

/-- The exact copy-removed analogue also fails. This prevents attributing this
    particular multiset obstruction to duplication itself. -/
theorem singlePass_nesting_multiset_fails_recursive_root :
    ¬ DMLT
      (singlePassNestingBag (g (f (s z) (s z) z)))
      (singlePassNestingBag (f (s z) (s z) (s z))) := by
  intro h
  rcases dm_element_bounded h target_has_two with ⟨m, hm, htwo⟩
  have hm1 := source_members_eq_one hm
  omega

theorem no_singlePass_nesting_multiset_orients_step :
    ¬ (∀ {a b : SANSTerm}, Step a b →
      DMLT (singlePassNestingBag b) (singlePassNestingBag a)) := by
  intro h
  exact singlePass_nesting_multiset_fails_recursive_root
    (h (Step.root (RootStep.succ (s z) (s z) z)))

end SANS
end NestingMultiset

end KO7Benchmark.ScoringAnchors.ResidualMeasureFamilies

