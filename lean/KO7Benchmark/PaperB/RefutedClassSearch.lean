/-
  Search inside a refuted class (ICLR Appendix C, Proposition 5).

  Relation: the two-rule schema of `SchemaKernel` for the concrete instance;
    an arbitrary candidate type for the abstract statements.
  Closure: full contextual closure `Step` for the concrete instance.
  Property: if no candidate in a class is a proof, then every finite candidate
    sequence drawn from the class, every budget prefix of it, and every
    finitely supported randomized search over it contains a proof with count
    zero and probability zero. The concrete instance is the additive class on
    the schema, refuted by `no_additive_orients_schema_step`.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Data.Rat.Defs
import KO7Benchmark.PaperB.SchemaAdditiveObstruction

set_option autoImplicit false

namespace KO7Benchmark.PaperB.RefutedClassSearch

open KO7Benchmark.SchemaTests
open KO7Benchmark.PaperB

section Abstract

variable {C : Type} (IsProof : C → Prop)

/-- No element of a sequence drawn from a class without proofs is a proof. -/
theorem no_proof_in_sequence (hEmpty : ∀ c, ¬ IsProof c) (seq : List C) :
    ∀ c ∈ seq, ¬ IsProof c :=
  fun c _ => hEmpty c

/-- The proof count of any such sequence is zero. -/
theorem proof_count_zero [DecidablePred IsProof] (hEmpty : ∀ c, ¬ IsProof c)
    (seq : List C) :
    seq.countP (fun c => decide (IsProof c)) = 0 := by
  rw [List.countP_eq_zero]
  intro c _
  simp [hEmpty c]

/-- Budget invariance: every prefix of the sequence has proof count zero. -/
theorem proof_count_zero_prefix [DecidablePred IsProof] (hEmpty : ∀ c, ¬ IsProof c)
    (seq : List C) (budget : Nat) :
    (seq.take budget).countP (fun c => decide (IsProof c)) = 0 :=
  proof_count_zero IsProof hEmpty (seq.take budget)

/-- A randomized search whose distribution is supported on the class has
    probability zero of drawing a proof: the weighted indicator sum vanishes
    term by term, on any finite support and under any weights. -/
theorem randomized_search_zero [DecidablePred IsProof]
    (hEmpty : ∀ c, ¬ IsProof c) (support : Finset C) (w : C → ℚ) :
    (∑ c ∈ support, (if IsProof c then w c else 0)) = 0 := by
  apply Finset.sum_eq_zero
  intro c _
  simp [hEmpty c]

end Abstract

/-! ## The concrete instance: the additive class on the schema -/

/-- An additive measure is a proof when it strictly decreases on every step. -/
def AdditiveIsProof (M : AdditiveSKMeasure) : Prop :=
  ∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a

/-- The additive class contains no proof (Proposition 2). -/
theorem additive_class_empty : ∀ M : AdditiveSKMeasure, ¬ AdditiveIsProof M :=
  fun M => AdditiveSKMeasure.no_additive_orients_schema_step M

/-- Proposition 5 for the additive class: any finite sequence of additive
    measures contains no proof, whatever its length. -/
theorem additive_sequence_no_proof (seq : List AdditiveSKMeasure) :
    ∀ M ∈ seq, ¬ AdditiveIsProof M :=
  no_proof_in_sequence AdditiveIsProof additive_class_empty seq

open Classical in
/-- The second half of Proposition 5 for the additive class: a randomized
    search over additive measures draws a proof with probability zero, on any
    finite support and under any weights. -/
theorem additive_randomized_search_zero
    (support : Finset AdditiveSKMeasure) (w : AdditiveSKMeasure → ℚ) :
    (∑ M ∈ support, (if AdditiveIsProof M then w M else 0)) = 0 := by
  apply Finset.sum_eq_zero
  intro M _
  simp [additive_class_empty M]

end KO7Benchmark.PaperB.RefutedClassSearch
