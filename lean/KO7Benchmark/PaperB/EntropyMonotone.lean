/-
  Entropy monotonicity under pushforward and the verdict-first
  signature bound.

  Mechanizes the formal core behind Rahnama_PRT_Benchmark.tex §7
  ("stability of the verdict layer vs. instability of the method
  layer"): for a finite nonnegative mass assignment, the Shannon
  entropy of any pushforward is at most the Shannon entropy of the
  source. Specialized to the benchmark's method families: whenever the
  emitted verdict is a function of the method class, the verdict-layer
  entropy is bounded by the method-layer entropy.

  Scope note (statement-adequacy guard): the theorem is a one-way
  bound for the method-determined-verdict regime. It licenses the
  reading that the observed pair (verdict entropy 0.293 bits, method
  entropy 1.133 bits) lies inside the predicted cone of that regime;
  the converse interpretive claim in the manuscript prose (that
  witness-driven reasoning would show a different asymmetry) is not a
  theorem here and is not stated as one.

  The proof is elementary: grouping a fiber's mass can only lower the
  `x log x` sum, because each member's mass is bounded by the fiber
  total and `log` is monotone on positives. Entropies are in
  natural-log units; normalization to a probability vector is not
  required for the inequality.

  Relation: none (finite information bookkeeping).
  Property: metadata / distributional theorem layer.
  Trust: kernel-only; baseline axioms (classical real analysis).
-/
import KO7Benchmark.BenchmarkContract
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.EntropyMonotone

open Finset

variable {ι κ : Type} [Fintype ι] [Fintype κ] [DecidableEq κ]

/-- Finite Shannon entropy (natural-log units) of a nonnegative mass
    assignment. -/
noncomputable def shannonEntropy (p : ι → ℝ) : ℝ :=
  -∑ i : ι, p i * Real.log (p i)

/-- Pushforward mass along a map. -/
def pushforward (f : ι → κ) (p : ι → ℝ) : κ → ℝ :=
  fun y => ∑ i ∈ univ.filter (fun i => f i = y), p i

omit [Fintype κ] in
theorem pushforward_nonneg (f : ι → κ) (p : ι → ℝ)
    (hp : ∀ i, 0 ≤ p i) (y : κ) : 0 ≤ pushforward f p y :=
  Finset.sum_nonneg fun i _ => hp i

omit [Fintype κ] in
/-- Each mass is bounded by its fiber total. -/
theorem le_pushforward (f : ι → κ) (p : ι → ℝ)
    (hp : ∀ i, 0 ≤ p i) (i : ι) : p i ≤ pushforward f p (f i) := by
  refine Finset.single_le_sum (fun j _ => hp j) ?_
  simp

private theorem log_mono_of_pos_le {x y : ℝ} (hx : 0 < x) (hxy : x ≤ y) :
    Real.log x ≤ Real.log y := by
  rcases eq_or_lt_of_le hxy with rfl | h
  · exact le_rfl
  · exact (Real.log_lt_log hx h).le

omit [Fintype κ] in
private theorem term_le (f : ι → κ) (p : ι → ℝ)
    (hp : ∀ i, 0 ≤ p i) (i : ι) :
    p i * Real.log (p i) ≤ p i * Real.log (pushforward f p (f i)) := by
  rcases (hp i).eq_or_lt with h0 | hpos
  · simp [← h0]
  · exact mul_le_mul_of_nonneg_left
      (log_mono_of_pos_le hpos (le_pushforward f p hp i)) (hp i)

private theorem sum_fiberwise_eq (f : ι → κ) (g : ι → ℝ) :
    ∑ y : κ, ∑ i ∈ univ.filter (fun i => f i = y), g i = ∑ i : ι, g i :=
  Finset.sum_fiberwise_of_maps_to (fun i _ => mem_univ (f i)) g

/-- **Entropy is monotone under pushforward.** For any finite
    nonnegative mass assignment `p` and any map `f`, the Shannon
    entropy of the pushforward of `p` along `f` is at most the Shannon
    entropy of `p`. -/
theorem shannonEntropy_pushforward_le (f : ι → κ) (p : ι → ℝ)
    (hp : ∀ i, 0 ≤ p i) :
    shannonEntropy (pushforward f p) ≤ shannonEntropy p := by
  unfold shannonEntropy
  rw [neg_le_neg_iff]
  calc ∑ i : ι, p i * Real.log (p i)
      = ∑ y : κ, ∑ i ∈ univ.filter (fun i => f i = y),
          p i * Real.log (p i) :=
        (sum_fiberwise_eq f (fun i => p i * Real.log (p i))).symm
    _ ≤ ∑ y : κ, pushforward f p y * Real.log (pushforward f p y) := by
        refine Finset.sum_le_sum fun y _ => ?_
        calc ∑ i ∈ univ.filter (fun i => f i = y), p i * Real.log (p i)
            ≤ ∑ i ∈ univ.filter (fun i => f i = y),
                p i * Real.log (pushforward f p y) := by
              refine Finset.sum_le_sum fun i hi => ?_
              have hfi : f i = y := (Finset.mem_filter.mp hi).2
              simpa [hfi] using term_le f p hp i
          _ = pushforward f p y * Real.log (pushforward f p y) := by
              rw [← Finset.sum_mul]
              rfl

/-! ## Benchmark specialization: method families and verdict maps -/

open KO7Benchmark.Benchmark

instance : Fintype MethodFamily where
  elems := ⟨[MethodFamily.directMeasure, .affine, .quadratic, .polynomial,
    .pathOrder, .kboStyle, .dependencyPairs, .rootOnly, .semanticObjection,
    .nonlinearPoly, .mpoSpecialized, .exponentialInterp], by decide⟩
  complete := fun x => by cases x <;> decide

/-- The method-determined verdict regime: the objection family maps to a
    negative verdict, every other method family maps to a positive
    verdict. This models the regime in which the emitted verdict is a
    function of the method class; the empirical corpus is compared
    against this regime in the manuscript. -/
def methodDeterminedVerdict : MethodFamily → Bool
  | .semanticObjection => false
  | _ => true

/-- **Verdict-first signature bound.** For any session mass over the
    method families and any method-determined verdict map, the
    verdict-layer entropy is at most the method-layer entropy. -/
theorem verdict_entropy_le_method_entropy
    (g : MethodFamily → Bool) (p : MethodFamily → ℝ)
    (hp : ∀ m, 0 ≤ p m) :
    shannonEntropy (pushforward g p) ≤ shannonEntropy p :=
  shannonEntropy_pushforward_le g p hp

/-- The bound instantiated at the canonical objection-vs-positive
    verdict map. -/
theorem methodDeterminedVerdict_entropy_le
    (p : MethodFamily → ℝ) (hp : ∀ m, 0 ≤ p m) :
    shannonEntropy (pushforward methodDeterminedVerdict p) ≤
      shannonEntropy p :=
  verdict_entropy_le_method_entropy methodDeterminedVerdict p hp

end KO7Benchmark.PaperB.EntropyMonotone
