/-
Relation: the recursive dependency-pair relations extracted from the duplicating Schema kernel and the copy-removed SANS control.
Closure: one transformed recursive call and its rule-level projections; full contextual Step appears only through already-proved specialized source theorems.
Property: exact family decisions for marked-call argument filtering, same-position size-change descent, immediate-subterm criterion, counter projection, first/second projection failure, payload erasure, and the Schema/SANS control contrast.
Trust: Mathlib and existing project theorems only; no sorry, admit, new axiom, native_decide, unsafe, partial, or opaque declarations.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.SANSTests.DependencyPairsWitness
import KO7Benchmark.SANSTests.LinearWitness
import KO7Benchmark.PaperB.Demarcation
import KO7Benchmark.PaperB.DPSoundness
import KO7Benchmark.ScoringAnchors.ControlContrast

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.ProcessorFamilyDecisions

/-!
This module deliberately stays at the rule-derived projection layer.

The named readings below share one concrete fact: on the extracted recursive call
the first two arguments are preserved and the third argument changes from
`S n` to `n`.  The argument-filtering declarations are therefore collapsing
filters on the marked `F` call, not a generic formalization of an
argument-filtering processor for arbitrary TRSs.  Likewise, the size-change
and subterm declarations certify the single recursive-call edge, not generic
processor soundness.

Full contextual termination of the exact duplicating Schema system is cited
only from `PaperB.DPSoundness.wf_StepRev`, whose proof is specialized to that
system.
-/

namespace Schema

open KO7Benchmark.SchemaTests
open SKTerm
open KO7Benchmark.PaperB

/-- The three argument positions of the marked recursive call. -/
def first : Fin 3 := ⟨0, by decide⟩
def second : Fin 3 := ⟨1, by decide⟩
def third : Fin 3 := ⟨2, by decide⟩

/--
A rule-level collapsing argument filter on the marked `F` call.
It carries exactly one selected position.  This is not a generic recursive
argument-filtering transformation on arbitrary terms or TRSs.
-/
structure MarkedFArgumentFilter where
  slot : Fin 3

namespace MarkedFArgumentFilter

/-- Apply the marked-call filter used by `PaperB.Demarcation`. -/
def apply (A : MarkedFArgumentFilter) : SKTerm → SKTerm :=
  Demarcation.proj A.slot

/-- The selected call argument strictly decreases under the term-size base order. -/
def OrientsExtractedPair (A : MarkedFArgumentFilter) : Prop :=
  ∀ x y n : SKTerm,
    Demarcation.size (A.apply (f x y n))
      < Demarcation.size (A.apply (f x y (s n)))

/-- The selected marked-call coordinate ignores the duplicated payload argument. -/
def PayloadBlind (A : MarkedFArgumentFilter) : Prop :=
  ∀ x y₁ y₂ n : SKTerm,
    A.apply (f x y₁ n) = A.apply (f x y₂ n)

end MarkedFArgumentFilter

def firstFilter : MarkedFArgumentFilter := ⟨first⟩
def secondFilter : MarkedFArgumentFilter := ⟨second⟩
def thirdFilter : MarkedFArgumentFilter := ⟨third⟩

/-- Exact family decision for the rule-level marked-call argument filter. -/
theorem markedF_argument_filter_strict_iff_third (A : MarkedFArgumentFilter) :
    A.OrientsExtractedPair ↔ A.slot.val = 2 := by
  constructor
  · intro h
    exact (Demarcation.projection_strict_iff A.slot z z z).1 (h z z z)
  · intro h x y n
    exact (Demarcation.projection_strict_iff A.slot x y n).2 h

/-- The successful third filter is non-vacuous and erases the copied payload coordinate. -/
theorem third_argument_filter_success :
    thirdFilter.OrientsExtractedPair ∧ thirdFilter.PayloadBlind := by
  constructor
  · exact (markedF_argument_filter_strict_iff_third thirdFilter).2 rfl
  · intro x y₁ y₂ n
    rfl

/-- The first argument filter cannot orient the extracted recursive call. -/
theorem first_argument_filter_fails :
    ¬ firstFilter.OrientsExtractedPair := by
  intro h
  have hslot := (markedF_argument_filter_strict_iff_third firstFilter).1 h
  exact (by decide : firstFilter.slot.val ≠ 2) hslot

/-- The second argument filter cannot orient the extracted recursive call. -/
theorem second_argument_filter_fails :
    ¬ secondFilter.OrientsExtractedPair := by
  intro h
  have hslot := (markedF_argument_filter_strict_iff_third secondFilter).1 h
  exact (by decide : secondFilter.slot.val ≠ 2) hslot

/-- The first projection sends both sides of every extracted pair to the same term. -/
theorem first_projection_equal (x y n : SKTerm) :
    firstFilter.apply (f x y n) = firstFilter.apply (f x y (s n)) := by
  rfl

/-- The second projection sends both sides of every extracted pair to the same term. -/
theorem second_projection_equal (x y n : SKTerm) :
    secondFilter.apply (f x y n) = secondFilter.apply (f x y (s n)) := by
  rfl

/--
The first projection fails against every irreflexive strict relation, not only
against a particular numeric measure.
-/
theorem first_projection_fails_every_irreflexive_relation
    (R : SKTerm → SKTerm → Prop) (hirr : ∀ t : SKTerm, ¬ R t t) :
    ¬ (∀ x y n : SKTerm,
      R (firstFilter.apply (f x y n))
        (firstFilter.apply (f x y (s n)))) := by
  intro h
  have hz := h z z z
  exact hirr z (by simpa [firstFilter, first, MarkedFArgumentFilter.apply, Demarcation.proj] using hz)

/--
The second projection fails against every irreflexive strict relation, not only
against a particular numeric measure.
-/
theorem second_projection_fails_every_irreflexive_relation
    (R : SKTerm → SKTerm → Prop) (hirr : ∀ t : SKTerm, ¬ R t t) :
    ¬ (∀ x y n : SKTerm,
      R (secondFilter.apply (f x y n))
        (secondFilter.apply (f x y (s n)))) := by
  intro h
  have hz := h z z z
  exact hirr z (by simpa [secondFilter, second, MarkedFArgumentFilter.apply, Demarcation.proj] using hz)

/-! ## Rule-level size-change reading -/

/--
A strict same-position size-change edge on the single recursive call.
No generic size-change termination theorem is asserted here.
-/
def SizeChangeStrictAt (i : Fin 3) : Prop :=
  ∀ x y n : SKTerm,
    Demarcation.size (Demarcation.proj i (f x y n))
      < Demarcation.size (Demarcation.proj i (f x y (s n)))

/-- Exactly the third same-position size-change edge is strict. -/
theorem size_change_strict_iff_third (i : Fin 3) :
    SizeChangeStrictAt i ↔ i.val = 2 := by
  constructor
  · intro h
    exact (Demarcation.projection_strict_iff i z z z).1 (h z z z)
  · intro hi x y n
    exact (Demarcation.projection_strict_iff i x y n).2 hi

/-- The first size-change coordinate is preserved. -/
theorem size_change_first_preserved (x y n : SKTerm) :
    Demarcation.proj first (f x y n)
      = Demarcation.proj first (f x y (s n)) := by
  rfl

/-- The second size-change coordinate is preserved. -/
theorem size_change_second_preserved (x y n : SKTerm) :
    Demarcation.proj second (f x y n)
      = Demarcation.proj second (f x y (s n)) := by
  rfl

/-! ## Immediate-subterm criterion on the extracted pair -/

/-- Immediate subterms are strictly smaller under the native term-size function. -/
theorem immSub_size_lt {a t : SKTerm} (h : DPSoundness.ImmSub a t) :
    Demarcation.size a < Demarcation.size t := by
  cases h <;> simp [Demarcation.size] <;> omega

/--
The rule-level immediate-subterm criterion at one selected marked-call position.
This is the concrete pair criterion, not generic dependency-pair processor soundness.
-/
def SubtermCriterionAt (i : Fin 3) : Prop :=
  ∀ x y n : SKTerm,
    DPSoundness.ImmSub
      (Demarcation.proj i (f x y n))
      (Demarcation.proj i (f x y (s n)))

/-- The immediate-subterm criterion succeeds exactly at the third argument. -/
theorem subterm_criterion_iff_third (i : Fin 3) :
    SubtermCriterionAt i ↔ i.val = 2 := by
  constructor
  · intro h
    have hsub := h z z z
    have hlt := immSub_size_lt hsub
    exact (Demarcation.projection_strict_iff i z z z).1 hlt
  · intro hi
    have hiEq : i = third := by
      apply Fin.ext
      simpa [third] using hi
    subst i
    intro x y n
    simpa [third, Demarcation.proj] using DPSoundness.ImmSub.s_arg n

/-! ## Transformed-call counter projection -/

/-- Strictness of a numeric projection on every extracted dependency pair. -/
def TransformedProjectionStrict (μ : SKTerm → Nat) : Prop :=
  ∀ {a b : SKTerm}, CandidateD.DPPair a b → μ b < μ a

/-- The actual rule-derived counter projection strictly decreases on every extracted pair. -/
theorem counter_projection_strict :
    TransformedProjectionStrict CandidateD.sDepth :=
  CandidateD.dp_pair_decreases

/-- The extracted one-pair problem is well-founded. -/
theorem transformed_pair_problem_wf :
    WellFounded CandidateD.DPPairRev :=
  CandidateD.wf_DPPairRev

/-- The recursive root rule and its transformed pair are coupled to the same inputs. -/
theorem recursive_rule_extracts_same_input_pair (x y n : SKTerm) :
    RootStep (f x y (s n)) (g y (f x y n)) ∧
      CandidateD.DPPair (f x y (s n)) (f x y n) :=
  CandidateD.rec_rule_extracts_pair x y n

/--
The four manuscript readings coincide on one rule-level fact: the third marked
argument is selected, strictly decreases, is an immediate subterm, and the
counter projection decreases on the extracted dependency pair.
-/
theorem four_projection_readings_hold :
    thirdFilter.OrientsExtractedPair ∧
    SizeChangeStrictAt third ∧
    SubtermCriterionAt third ∧
    TransformedProjectionStrict CandidateD.sDepth := by
  refine ⟨(third_argument_filter_success).1, ?_, ?_, counter_projection_strict⟩
  · exact (size_change_strict_iff_third third).2 rfl
  · exact (subterm_criterion_iff_third third).2 rfl

/--
Full contextual strong normalization is available for this exact Schema system
from the specialized source proof in `PaperB.DPSoundness`.
It is not inferred here from pair well-foundedness alone.
-/
theorem full_context_step_wf_specialized :
    WellFounded DPSoundness.StepRev :=
  DPSoundness.wf_StepRev

end Schema

namespace SANS

open KO7Benchmark.SANSTests
open SANSTerm

def first : Fin 3 := ⟨0, by decide⟩
def second : Fin 3 := ⟨1, by decide⟩
def third : Fin 3 := ⟨2, by decide⟩

/-- SANS analogue of the rule-level marked-call projection. -/
def proj (i : Fin 3) : SANSTerm → SANSTerm
  | f x y n =>
      match i.val with
      | 0 => x
      | 1 => y
      | _ => n
  | t => t

/-- One unit per SANS syntax node. -/
def size : SANSTerm → Nat
  | var _ => 1
  | z => 1
  | s t => size t + 1
  | g t => size t + 1
  | f x y n => size x + size y + size n + 1

@[simp] theorem proj_first (x y n : SANSTerm) :
    proj first (f x y n) = x := rfl
@[simp] theorem proj_second (x y n : SANSTerm) :
    proj second (f x y n) = y := rfl
@[simp] theorem proj_third (x y n : SANSTerm) :
    proj third (f x y n) = n := rfl

/-- Pointwise SANS projection decision on the extracted recursive call. -/
theorem projection_strict_iff (i : Fin 3) (x y n : SANSTerm) :
    size (proj i (f x y n)) < size (proj i (f x y (s n))) ↔ i.val = 2 := by
  rcases i with ⟨i, hi⟩
  interval_cases i <;> simp [proj, size]

/-- Rule-level same-position size-change predicate for the SANS control. -/
def SizeChangeStrictAt (i : Fin 3) : Prop :=
  ∀ x y n : SANSTerm,
    size (proj i (f x y n)) < size (proj i (f x y (s n)))

/-- The SANS extracted call has the same strict-position decision as Schema. -/
theorem size_change_strict_iff_third (i : Fin 3) :
    SizeChangeStrictAt i ↔ i.val = 2 := by
  constructor
  · intro h
    exact (projection_strict_iff i z z z).1 (h z z z)
  · intro hi x y n
    exact (projection_strict_iff i x y n).2 hi

/-- The first SANS projection is preserved across the extracted call. -/
theorem first_projection_equal (x y n : SANSTerm) :
    proj first (f x y n) = proj first (f x y (s n)) := rfl

/-- The second SANS projection is preserved across the extracted call. -/
theorem second_projection_equal (x y n : SANSTerm) :
    proj second (f x y n) = proj second (f x y (s n)) := rfl

/-- SANS first projection fails for every irreflexive strict relation. -/
theorem first_projection_fails_every_irreflexive_relation
    (R : SANSTerm → SANSTerm → Prop) (hirr : ∀ t : SANSTerm, ¬ R t t) :
    ¬ (∀ x y n : SANSTerm,
      R (proj first (f x y n)) (proj first (f x y (s n)))) := by
  intro h
  exact hirr z (by simpa [first, proj] using h z z z)

/-- SANS second projection fails for every irreflexive strict relation. -/
theorem second_projection_fails_every_irreflexive_relation
    (R : SANSTerm → SANSTerm → Prop) (hirr : ∀ t : SANSTerm, ¬ R t t) :
    ¬ (∀ x y n : SANSTerm,
      R (proj second (f x y n)) (proj second (f x y (s n)))) := by
  intro h
  exact hirr z (by simpa [second, proj] using h z z z)

/-- Immediate-subterm relation used only for the SANS rule-level control. -/
inductive ImmSub : SANSTerm → SANSTerm → Prop
  | s_arg (t : SANSTerm) : ImmSub t (s t)
  | g_arg (t : SANSTerm) : ImmSub t (g t)
  | f_arg1 (x y n : SANSTerm) : ImmSub x (f x y n)
  | f_arg2 (x y n : SANSTerm) : ImmSub y (f x y n)
  | f_arg3 (x y n : SANSTerm) : ImmSub n (f x y n)

theorem immSub_size_lt {a t : SANSTerm} (h : ImmSub a t) :
    size a < size t := by
  cases h <;> simp [size] <;> omega

def SubtermCriterionAt (i : Fin 3) : Prop :=
  ∀ x y n : SANSTerm,
    ImmSub (proj i (f x y n)) (proj i (f x y (s n)))

/-- The SANS control also satisfies the immediate-subterm criterion exactly at argument three. -/
theorem subterm_criterion_iff_third (i : Fin 3) :
    SubtermCriterionAt i ↔ i.val = 2 := by
  constructor
  · intro h
    have hlt := immSub_size_lt (h z z z)
    exact (projection_strict_iff i z z z).1 hlt
  · intro hi
    have hiEq : i = third := by
      apply Fin.ext
      simpa [third] using hi
    subst i
    intro x y n
    simpa [third, proj] using ImmSub.s_arg n

/-- Numeric projection strictness on every SANS extracted dependency pair. -/
def TransformedProjectionStrict (μ : SANSTerm → Nat) : Prop :=
  ∀ {a b : SANSTerm},
    DependencyPairsWitness.DPPair a b → μ b < μ a

theorem counter_projection_strict :
    TransformedProjectionStrict DependencyPairsWitness.sDepth :=
  DependencyPairsWitness.dp_pair_decreases

theorem transformed_pair_problem_wf :
    WellFounded DependencyPairsWitness.DPPairRev :=
  DependencyPairsWitness.wf_DPPairRev

theorem recursive_rule_extracts_same_input_pair (x y n : SANSTerm) :
    RootStep (f x y (s n)) (g (f x y n)) ∧
      DependencyPairsWitness.DPPair (f x y (s n)) (f x y n) :=
  DependencyPairsWitness.rec_rule_extracts_pair x y n

/--
Unlike the duplicating Schema system, SANS also has a direct additive
full-context measure.  This is independent of the shared transformed-call
projection decision.
-/
theorem full_context_step_wf_by_direct_linear_measure :
    WellFounded LinearWitness.StepRev :=
  LinearWitness.wf_StepRev

end SANS

/-! ## Copy-removal control: same pair decision, different direct-measure boundary -/

/--
The transformed recursive-call decision is unchanged by copy removal: argument
three is strict in both systems.  What copy removal changes is the availability
of an additive whole-term full-context measure.
-/
theorem copy_removal_preserves_pair_projection_but_changes_direct_measure :
    Schema.SizeChangeStrictAt Schema.third ∧
    SANS.SizeChangeStrictAt SANS.third ∧
    (∃ M : ControlContrast.SANSAdditive,
      ∀ {a b : KO7Benchmark.SANSTests.SANSTerm},
        KO7Benchmark.SANSTests.Step a b → M.eval b < M.eval a) ∧
    ¬ (∃ M : MeasureFailures.GenAdditive,
      ∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
        KO7Benchmark.SchemaTests.Step a b → M.eval b < M.eval a) := by
  refine ⟨(Schema.size_change_strict_iff_third Schema.third).2 rfl,
    (SANS.size_change_strict_iff_third SANS.third).2 rfl, ?_, ?_⟩
  · exact ControlContrast.SANSAdditive.additive_family_inhabited_on_control
  · exact ControlContrast.additive_family_empty_on_schema

/-! ## Necessity control for any claimed pair-to-source lift -/

namespace PairOnlyCountermodel

/-- A trivially well-founded transformed relation. -/
def pairRel : Unit → Unit → Prop := fun _ _ => False

/-- A source relation with a self-loop at its only point. -/
def sourceRel : Unit → Unit → Prop := fun _ _ => True

theorem pairRel_wf : WellFounded pairRel := by
  refine ⟨?_⟩
  intro a
  constructor
  intro b h
  exact False.elim h

theorem sourceRel_not_wf : ¬ WellFounded sourceRel := by
  intro hwf
  apply hwf.induction (C := fun _ => False) ()
  intro a ih
  exact ih a True.intro

/--
Pair well-foundedness by itself cannot be a generic source-termination
processor theorem.  Any valid lift must consume structural bridge hypotheses.
-/
theorem pair_wf_alone_has_no_generic_source_lift :
    ¬ (∀ (P S : Unit → Unit → Prop), WellFounded P → WellFounded S) := by
  intro h
  exact sourceRel_not_wf (h pairRel sourceRel pairRel_wf)

end PairOnlyCountermodel

end KO7Benchmark.ScoringAnchors.ProcessorFamilyDecisions
