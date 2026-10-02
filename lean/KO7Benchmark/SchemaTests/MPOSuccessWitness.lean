/-
  Candidate (C) for Schema Test B New System: multiset path order (MPO)
  with precedence F > G > S > Z, all arguments compared as multisets.

  Status: SUCCEEDS as an imported precedence-plus-multiset-status method.
  MPO tolerates the duplication of `y` in the recursive rule because path
  orders compare term structure recursively; the multiset variable
  condition that blocks KBO (`CandidateC_KBOFailure`) does not apply to
  path orders.

  Like `CandidateA_PathOrderSupport` (LPO) and the SANS support files,
  this benchmark file does not mechanize a generic MPO library. It
  records the exact local rule-shape obligations behind the MPO argument:

  * base rule `F(x,y,Z) -> x`: the RHS is a direct subterm of the LHS
    (MPO subterm case);
  * recursive rule `F(x,y,S(n)) -> G(y, F(x,y,n))`: head precedence
    F > G fires the precedence case, under which each RHS argument must
    sit strictly below the LHS: the duplicated payload `y` is a direct
    LHS subterm, and the recursive call `F(x,y,n)` is dominated by the
    same-head multiset comparison {x, y, S(n)} >mul {x, y, n}, whose
    only swapped element is S(n) -> n, a strict subterm step.

  The overall success status is closed with the benchmark-local
  strong-normalization witness `NonCollapsingPoly.wf_StepRev_p2` (the
  same TRS is SN, proved independently), following the same pattern as
  candidate (A), which closes with `NonlinearWitness.wf_StepRev`.

  Relation: the closing status is about `Step` (full contextual
  closure); the obligations themselves are root-rule shape facts.
  Boundary status: mathematically adequate but boundary-EXTERNAL
  (imported precedence and status), i.e. adequate-not-admissible.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.SchemaKernel
import KO7Benchmark.SchemaTests.CandidateA_PathOrderSupport
import KO7Benchmark.SchemaTests.NonCollapsingPolyWitness

namespace KO7Benchmark.SchemaTests.MPOSuccess

open KO7Benchmark.SchemaTests
open SKTerm

/-- Head precedence F > G on the recursive rule, the MPO precedence-case
trigger. Reuses candidate A's precedence encoding F > G > S > Z. -/
theorem mpo_head_precedence (x y n : SKTerm) :
    CandidateA.precRank (CandidateA.rootSym (g y (f x y n))) <
      CandidateA.precRank (CandidateA.rootSym (f x y (s n))) :=
  CandidateA.candidateA_declares_F_over_G x y n

/-- Benchmark-local measure used to express the local MPO obligations. -/
abbrev mpoWitness : SKTerm → Nat := NonCollapsingPoly.p2

/-- Base rule, MPO subterm case: the RHS `x` sits strictly below the LHS. -/
theorem mpo_root_base_subterm_supported (x y : SKTerm) :
    mpoWitness x < mpoWitness (f x y z) :=
  NonCollapsingPoly.p2_root_base x y

/-- Recursive rule, payload domination: the duplicated `y` sits strictly
below the LHS. MPO does not count occurrences, so duplication of `y` is
harmless here, unlike for KBO's variable condition. -/
theorem mpo_lhs_dominates_duplicated_y (x y n : SKTerm) :
    mpoWitness y < mpoWitness (f x y (s n)) := by
  simp only [mpoWitness, NonCollapsingPoly.p2_f, NonCollapsingPoly.p2_s]
  nlinarith [NonCollapsingPoly.p2 x, NonCollapsingPoly.p2 y, NonCollapsingPoly.p2 n]

/-- Recursive rule, same-head multiset comparison: the only swapped
element of {x, y, S(n)} >mul {x, y, n} is the third argument, and it
strictly decreases (S(n) -> n is a strict subterm step). -/
theorem mpo_multiset_swap_element_decreases (n : SKTerm) :
    mpoWitness n < mpoWitness (s n) := by
  have h : mpoWitness (s n) = mpoWitness n + 1 := rfl
  omega

/-- Recursive rule, recursive-call domination: F(x,y,n) sits strictly
below the LHS F(x,y,S(n)). -/
theorem mpo_recursive_call_smaller (x y n : SKTerm) :
    mpoWitness (f x y n) < mpoWitness (f x y (s n)) := by
  simp only [mpoWitness, NonCollapsingPoly.p2_f, NonCollapsingPoly.p2_s]
  nlinarith [NonCollapsingPoly.p2 y]

/-- Recursive rule, full root comparison under the witness measure. -/
theorem mpo_root_succ_supported (x y n : SKTerm) :
    mpoWitness (g y (f x y n)) < mpoWitness (f x y (s n)) :=
  NonCollapsingPoly.p2_root_succ x y n

abbrev StepRev : SKTerm → SKTerm → Prop := fun a b => Step b a

/-- Success status for candidate (C): the TRS the MPO obligations orient
is strongly normalizing. Closed by the benchmark-local independent
witness `NonCollapsingPoly.wf_StepRev_p2`, following the candidate-A
pattern.

Relation: `Step` (full contextual closure). Property: SN.
Does not prove: a generic MPO library; the obligations above are the
concrete rule-shape facts behind the MPO argument on this TRS. -/
theorem mpo_success_status : WellFounded StepRev :=
  NonCollapsingPoly.wf_StepRev_p2

end KO7Benchmark.SchemaTests.MPOSuccess
