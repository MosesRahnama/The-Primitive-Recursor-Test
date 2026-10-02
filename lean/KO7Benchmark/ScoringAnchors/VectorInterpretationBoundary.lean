/-
  Tracked-coordinate and one-dimensional matrix interpretation boundary.

  Relation: the duplicating SchemaKernel root rules and contextual Step,
    with the copy-removed SANS Step used as the control.
  Closure: the affine one-dimensional barrier is already a root-rule
    impossibility and therefore also blocks full contextual orientation;
    collapsed-coefficient escape examples are root-only and are explicitly
    refuted under context closure; the nonlinear and SANS control witnesses
    orient every contextual step.
  Property: every natural one-dimensional affine matrix interpretation whose
    binary wrapper is strictly sensitive to both arguments fails the recursive
    schema rule. Each wrapper-sensitivity premise is necessary for that root
    barrier: setting the corresponding coefficient to zero admits an explicit
    root-orienting member, but that member then fails context closure in the
    collapsed argument. A nonlinear one-coordinate vector measure works on
    the schema, and a linear one-coordinate vector measure works on SANS.
  Trust: mathlib and existing benchmark modules only. Open remainder:
    arbitrary higher-dimensional matrices with off-diagonal coupling and
    non-componentwise reduction orders are not closed by this module.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SANSTests.SANSKernel
import KO7Benchmark.SANSTests.LinearWitness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.VectorInterpretationBoundary

open KO7Benchmark.SchemaTests
open SKTerm

/-! ## One-dimensional natural affine matrix interpretations -/

/-- A one-dimensional affine matrix interpretation. In dimension one every
matrix is a natural scalar coefficient. Variables are evaluated by an
assignment; constructors use an affine constant plus scalar-matrix products. -/
structure Affine1D where
  z0 : Nat
  s0 : Nat
  s1 : Nat
  g0 : Nat
  gL : Nat
  gR : Nat
  f0 : Nat
  fX : Nat
  fY : Nat
  fN : Nat

namespace Affine1D

def interp (I : Affine1D) (σ : Nat → Nat) : SKTerm → Nat
  | .var i => σ i
  | .z => I.z0
  | .s t => I.s0 + I.s1 * I.interp σ t
  | .g a b => I.g0 + I.gL * I.interp σ a + I.gR * I.interp σ b
  | .f x y n =>
      I.f0 + I.fX * I.interp σ x + I.fY * I.interp σ y +
        I.fN * I.interp σ n

@[simp] theorem interp_var (I : Affine1D) (σ : Nat → Nat) (i : Nat) :
    I.interp σ (.var i) = σ i := rfl

@[simp] theorem interp_z (I : Affine1D) (σ : Nat → Nat) :
    I.interp σ .z = I.z0 := rfl

@[simp] theorem interp_s (I : Affine1D) (σ : Nat → Nat) (t : SKTerm) :
    I.interp σ (.s t) = I.s0 + I.s1 * I.interp σ t := rfl

@[simp] theorem interp_g (I : Affine1D) (σ : Nat → Nat) (a b : SKTerm) :
    I.interp σ (.g a b) =
      I.g0 + I.gL * I.interp σ a + I.gR * I.interp σ b := rfl

@[simp] theorem interp_f (I : Affine1D) (σ : Nat → Nat)
    (x y n : SKTerm) :
    I.interp σ (.f x y n) =
      I.f0 + I.fX * I.interp σ x + I.fY * I.interp σ y +
        I.fN * I.interp σ n := rfl

def OrientsRecursiveRoot (I : Affine1D) : Prop :=
  ∀ (σ : Nat → Nat) (x y n : SKTerm),
    I.interp σ (g y (f x y n)) <
      I.interp σ (f x y (s n))

def OrientsBothRoots (I : Affine1D) : Prop :=
  (∀ (σ : Nat → Nat) (x y : SKTerm),
    I.interp σ x < I.interp σ (f x y z)) ∧
  OrientsRecursiveRoot I

def OrientsStep (I : Affine1D) : Prop :=
  ∀ (σ : Nat → Nat) {t u : SKTerm},
    Step t u → I.interp σ u < I.interp σ t

def pumpValue (I : Affine1D) : Nat :=
  I.f0 + I.fN * I.s0 + 1

def pumpSigma (I : Affine1D) : Nat → Nat :=
  fun i => if i = 1 then I.pumpValue else 0

theorem pump_source_le_target (I : Affine1D)
    (hL : 0 < I.gL) (hR : 0 < I.gR) :
    I.interp I.pumpSigma (f (var 0) (var 1) (s (var 2))) ≤
      I.interp I.pumpSigma (g (var 1) (f (var 0) (var 1) (var 2))) := by
  have hL1 : 1 ≤ I.gL := hL
  have hR1 : 1 ≤ I.gR := hR
  let N := I.f0 + I.fN * I.s0 + 1
  have hLN : N ≤ I.gL * N := by
    simpa using Nat.mul_le_mul_right N hL1
  let A := I.f0 + I.fY * N
  have hRA : A ≤ I.gR * A := by
    simpa using Nat.mul_le_mul_right A hR1
  simp [interp, pumpSigma, pumpValue]
  dsimp [N, A] at hLN hRA
  omega

/-- Family theorem: no natural one-dimensional affine matrix interpretation
with positive wrapper coefficients on both arguments can orient the schema
recursive root rule for all assignments. -/
theorem no_positive_wrapper_affine_orients_recursive_root
    (I : Affine1D) (hL : 0 < I.gL) (hR : 0 < I.gR) :
    ¬ I.OrientsRecursiveRoot := by
  intro h
  have hlt :=
    h I.pumpSigma (var 0) (var 1) (var 2)
  have hle := pump_source_le_target I hL hR
  omega

theorem no_positive_wrapper_affine_orients_step
    (I : Affine1D) (hL : 0 < I.gL) (hR : 0 < I.gR) :
    ¬ I.OrientsStep := by
  intro h
  apply no_positive_wrapper_affine_orients_recursive_root I hL hR
  intro σ x y n
  exact h σ (Step.root (RootStep.succ x y n))

/-! ## Each positivity premise is necessary for the root barrier -/

/-- Collapse the duplicated payload argument of G. This is the familiar
root-orienting but context-invalid interpretation [G(a,b)] = b. -/
def leftCollapsed : Affine1D :=
  { z0 := 0
    s0 := 1, s1 := 1
    g0 := 0, gL := 0, gR := 1
    f0 := 1, fX := 1, fY := 0, fN := 1 }

theorem leftCollapsed_orients_both_roots :
    leftCollapsed.OrientsBothRoots := by
  constructor
  · intro σ x y
    simp [leftCollapsed, interp]
  · intro σ x y n
    simp [leftCollapsed, interp]

theorem leftCollapsed_not_contextual :
    ¬ leftCollapsed.OrientsStep := by
  intro h
  have hs :
      Step (g (f (var 0) (var 0) z) z) (g (var 0) z) :=
    Step.g_left (Step.root (RootStep.base (var 0) (var 0)))
  have hlt := h (fun _ => 0) hs
  simp [leftCollapsed, interp] at hlt

/-- Collapse the recursive-call argument of G. Root orientation becomes easy,
but context closure through G-right is then invisible. -/
def rightCollapsed : Affine1D :=
  { z0 := 0
    s0 := 1, s1 := 1
    g0 := 0, gL := 1, gR := 0
    f0 := 1, fX := 1, fY := 1, fN := 1 }

theorem rightCollapsed_orients_both_roots :
    rightCollapsed.OrientsBothRoots := by
  constructor
  · intro σ x y
    simp [rightCollapsed, interp]
    omega
  · intro σ x y n
    simp [rightCollapsed, interp]
    omega

theorem rightCollapsed_not_contextual :
    ¬ rightCollapsed.OrientsStep := by
  intro h
  have hs :
      Step (g z (f (var 0) (var 0) z)) (g z (var 0)) :=
    Step.g_right (Step.root (RootStep.base (var 0) (var 0)))
  have hlt := h (fun _ => 0) hs
  simp [rightCollapsed, interp] at hlt

end Affine1D

/-! ## Outside the affine-matrix barrier: working one-coordinate vectors -/

def schemaNonlinearVec (t : SKTerm) : Fin 1 → Nat :=
  fun _ => KO7Benchmark.SchemaTests.NonlinearWitness.muW t

theorem schemaNonlinearVec_step_decreases {t u : SKTerm} (h : Step t u) :
    ∀ i : Fin 1, schemaNonlinearVec u i < schemaNonlinearVec t i := by
  intro i
  exact KO7Benchmark.SchemaTests.NonlinearWitness.muW_step_decreases h

theorem schema_nonlinear_vector_family_inhabited :
    ∃ μ : SKTerm → Fin 1 → Nat,
      ∀ {t u : SKTerm}, Step t u → ∀ i, μ u i < μ t i :=
  ⟨schemaNonlinearVec, fun h => schemaNonlinearVec_step_decreases h⟩

def sansLinearVec (t : KO7Benchmark.SANSTests.SANSTerm) : Fin 1 → Nat :=
  fun _ => KO7Benchmark.SANSTests.LinearWitness.mu t

theorem sansLinearVec_step_decreases
    {t u : KO7Benchmark.SANSTests.SANSTerm}
    (h : KO7Benchmark.SANSTests.Step t u) :
    ∀ i : Fin 1, sansLinearVec u i < sansLinearVec t i := by
  intro i
  exact KO7Benchmark.SANSTests.LinearWitness.mu_step_decreases h

theorem sans_linear_vector_family_inhabited :
    ∃ μ : KO7Benchmark.SANSTests.SANSTerm → Fin 1 → Nat,
      ∀ {t u : KO7Benchmark.SANSTests.SANSTerm},
        KO7Benchmark.SANSTests.Step t u → ∀ i, μ u i < μ t i :=
  ⟨sansLinearVec, fun h => sansLinearVec_step_decreases h⟩

end KO7Benchmark.ScoringAnchors.VectorInterpretationBoundary
