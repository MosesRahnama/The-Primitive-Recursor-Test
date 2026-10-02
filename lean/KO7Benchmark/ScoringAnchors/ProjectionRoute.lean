/- 
  Exact rule-derived projection / dependency-pair route for the schema benchmark.

  Relation: KO7Benchmark.SchemaTests.Step on the source system and
    KO7Benchmark.SchemaTests.CandidateD.DPPair on the transformed problem;
    the SANS control uses KO7Benchmark.SANSTests.Step and
    KO7Benchmark.SANSTests.DependencyPairsWitness.DPPair.
  Closure: full contextual closure for both source Step relations; root only
    for identifying the recursive source rule; transformed-call relation for
    the dependency-pair problems.
  Property: exact pair extraction, strict third-counter projection, pair-problem
    well-foundedness, the fixed-schema full contextual strong-normalization
    conclusion, and countermodels showing why extraction identity, strict
    projection, and full-context source-to-pair soundness cannot be omitted.
  Trust: Mathlib and existing KO7Benchmark modules only; no sorry, admit, new
    axiom, native_decide, unsafe, partial, or opaque declaration.
  Open remainder: the generic Arts-Giesl dependency-pair soundness metatheorem
    for arbitrary finite TRSs is not mechanized here. This file closes the
    fixed schema and SANS control surfaces and states the exact transport
    premise a generic response would still have to justify.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.CandidateD_DependencyPairsWitness
import KO7Benchmark.PaperB.DPSoundness
import KO7Benchmark.SANSTests.DependencyPairsWitness
import KO7Benchmark.SANSTests.LinearWitness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.ProjectionRoute

/-- A natural-valued projection strictly orients every edge of a relation. -/
def StrictNatProjection {α : Type} (R : α → α → Prop) (rank : α → Nat) : Prop :=
  ∀ {a b : α}, R a b → rank b < rank a

/--
Proves: strict orientation by a natural rank makes the reversed pair relation
well founded.
Relation: arbitrary transformed relation R.
Closure: transformed edges only.
Property: SN / well-foundedness of the reversed transformed relation.
Trust: kernel-checked Mathlib well-foundedness.
-/
theorem wf_reverse_of_strictNatProjection {α : Type} {R : α → α → Prop}
    {rank : α → Nat} (h : StrictNatProjection R rank) :
    WellFounded (fun a b : α => R b a) := by
  let Q : α → α → Prop := InvImage (· < ·) rank
  have hsub : Subrelation (fun a b : α => R b a) Q := by
    intro a b hab
    exact h hab
  exact Subrelation.wf hsub (InvImage.wf rank Nat.lt_wfRel.wf)

/--
Proves: once method identity is fixed, two load-bearing premises suffice for
the logical projection route: strict transformed-pair descent and a soundness
transport from transformed-pair well-foundedness to the full source relation.
Does not prove: the transport premise itself for arbitrary TRSs.
Relation: Pair and Source supplied by the caller.
Closure: whatever closure Source denotes; callers claiming contextual
termination must instantiate Source with the full contextual relation.
Property: SN / well-foundedness.
Trust: kernel-only.
-/
theorem contextual_wf_of_projection_and_transport {α : Type}
    {Pair Source : α → α → Prop} {rank : α → Nat}
    (hproj : StrictNatProjection Pair rank)
    (htransport :
      WellFounded (fun a b : α => Pair b a) →
        WellFounded (fun a b : α => Source b a)) :
    WellFounded (fun a b : α => Source b a) :=
  htransport (wf_reverse_of_strictNatProjection hproj)

namespace Schema

open KO7Benchmark.SchemaTests
open KO7Benchmark.SchemaTests.SKTerm

/-- The transformed call extracted from the actual recursive root rule. -/
def RuleDerivedPair (a b : SKTerm) : Prop :=
  ∃ x y n : SKTerm,
    RootStep (f x y (s n)) (g y (f x y n)) ∧
      a = f x y (s n) ∧ b = f x y n

/--
Proves: Candidate D contains exactly the transformed recursive calls emitted by
the schema successor rule, with no missing and no extra pair.
Relation: RootStep and CandidateD.DPPair.
Closure: root extraction only.
Property: exact operational method identity.
Trust: kernel-only.
-/
theorem candidateD_iff_ruleDerivedPair {a b : SKTerm} :
    CandidateD.DPPair a b ↔ RuleDerivedPair a b := by
  constructor
  · intro h
    cases h with
    | succ x y n =>
        exact ⟨x, y, n, RootStep.succ x y n, rfl, rfl⟩
  · rintro ⟨x, y, n, _, ha, hb⟩
    subst a
    subst b
    exact CandidateD.DPPair.succ x y n

/--
Proves: the actual Candidate-D pair is strictly oriented by the rule-derived
third-counter projection.
Relation: CandidateD.DPPair.
Closure: transformed edges only.
Property: strict projection.
Trust: kernel-only.
-/
theorem projection_strict :
    StrictNatProjection CandidateD.DPPair CandidateD.sDepth :=
  fun h => CandidateD.dp_pair_decreases h

/--
Proves: the actual transformed pair problem is well founded, and the strict
projection theorem is the premise consumed by this proof.
Relation: CandidateD.DPPairRev.
Closure: transformed edges only.
Property: SN / well-foundedness.
Trust: kernel-only.
-/
theorem pair_problem_wf_from_projection :
    WellFounded CandidateD.DPPairRev :=
  wf_reverse_of_strictNatProjection projection_strict

/--
Proves: every actual transformed pair carries the same counter descent used by
the fixed-schema contextual soundness proof.
Relation: CandidateD.DPPair and DPSoundness.Descent.
Closure: transformed call and one structural counter descent.
Property: same-input dependency witness.
Trust: kernel-only.
-/
theorem pair_is_counter_descent {a b : SKTerm} (h : CandidateD.DPPair a b) :
    ∃ x y n : SKTerm,
      a = f x y (s n) ∧ b = f x y n ∧
        KO7Benchmark.PaperB.DPSoundness.Descent n (s n) := by
  cases h with
  | succ x y n =>
      exact ⟨x, y, n, rfl, rfl,
        Or.inr (KO7Benchmark.PaperB.DPSoundness.ImmSub.s_arg n)⟩

/--
Proves: full contextual Step is strongly normalizing for the exact schema.
The imported proof is the schema-specialized subterm-criterion soundness proof;
its recursive-rule branch descends from S(n) to n through ImmSub.s_arg.
Relation: SchemaTests.Step, reversed as DPSoundness.StepRev.
Closure: full contextual closure.
Property: SN / well-foundedness.
Trust: kernel-only.
-/
theorem full_contextual_step_wf :
    WellFounded KO7Benchmark.PaperB.DPSoundness.StepRev :=
  KO7Benchmark.PaperB.DPSoundness.wf_StepRev

/--
The complete fixed-schema receipt. It keeps method identity, transformed-pair
orientation, transformed-pair well-foundedness, and full contextual source
termination in one theorem without packaging them in a forgeable public record.
-/
theorem fixed_schema_route :
    (∀ {a b : SKTerm}, CandidateD.DPPair a b ↔ RuleDerivedPair a b) ∧
      StrictNatProjection CandidateD.DPPair CandidateD.sDepth ∧
      WellFounded CandidateD.DPPairRev ∧
      WellFounded KO7Benchmark.PaperB.DPSoundness.StepRev := by
  refine ⟨?_, projection_strict, pair_problem_wf_from_projection, full_contextual_step_wf⟩
  intro a b
  exact candidateD_iff_ruleDerivedPair

/-- An empty transformed relation is strictly oriented by every rank. -/
def EmptyPair (_ _ : SKTerm) : Prop := False

theorem emptyPair_projection_strict :
    StrictNatProjection EmptyPair CandidateD.sDepth := by
  intro a b h
  exact False.elim h

theorem emptyPair_wf : WellFounded (fun a b : SKTerm => EmptyPair b a) :=
  wf_reverse_of_strictNatProjection emptyPair_projection_strict

/--
Countermodel for dropping exact extraction: the empty transformed problem is
strictly projected and well founded, but it is not the pair problem extracted
from the live recursive rule.
-/
theorem emptyPair_not_ruleDerived :
    ¬ (∀ {a b : SKTerm}, EmptyPair a b ↔ RuleDerivedPair a b) := by
  intro h
  have hiff := h (a := f z z (s z)) (b := f z z z)
  have hr : RuleDerivedPair (f z z (s z)) (f z z z) :=
    ⟨z, z, z, RootStep.succ z z z, rfl, rfl⟩
  exact hiff.mpr hr

/--
Countermodel for dropping strict projection: even on the real extracted pair,
the constant rank cannot orient the transformed successor call.
-/
theorem constant_projection_fails :
    ¬ StrictNatProjection CandidateD.DPPair (fun _ : SKTerm => 0) := by
  intro h
  have hlt := h (CandidateD.DPPair.succ z z z)
  exact (Nat.lt_irrefl 0) hlt

end Schema

namespace TransportCountermodel

/-- A one-state source relation with an immediate self-loop. -/
def Loop (_ _ : Unit) : Prop := True

/-- An empty transformed relation on the same carrier. -/
def Empty (_ _ : Unit) : Prop := False

theorem empty_projection_strict :
    StrictNatProjection Empty (fun _ : Unit => 0) := by
  intro a b h
  exact False.elim h

theorem empty_wf : WellFounded (fun a b : Unit => Empty b a) :=
  wf_reverse_of_strictNatProjection empty_projection_strict

theorem loop_not_wf : ¬ WellFounded (fun a b : Unit => Loop b a) := by
  intro hwf
  exact (hwf.asymmetric () ()) trivial trivial

/--
Countermodel for dropping source-to-pair soundness: an exact/vacuous transformed
problem can be strictly projected and well founded while the source relation
loops. Thus transformed-pair well-foundedness alone never proves source
termination.
-/
theorem no_transport_from_empty_pair_to_loop :
    ¬ (WellFounded (fun a b : Unit => Empty b a) →
        WellFounded (fun a b : Unit => Loop b a)) := by
  intro h
  exact loop_not_wf (h empty_wf)

/--
Countermodel for weakening the target from full contextual closure to a root
subrelation: a terminating empty root relation can coexist with a looping full
relation on the same carrier.
-/
theorem root_wf_does_not_force_context_wf :
    WellFounded (fun a b : Unit => Empty b a) ∧
      ¬ WellFounded (fun a b : Unit => Loop b a) :=
  ⟨empty_wf, loop_not_wf⟩

end TransportCountermodel

namespace Control

open KO7Benchmark.SANSTests
open KO7Benchmark.SANSTests.SANSTerm

/-- The transformed call extracted from the actual SANS recursive root rule. -/
def RuleDerivedPair (a b : SANSTerm) : Prop :=
  ∃ x y n : SANSTerm,
    RootStep (f x y (s n)) (g (f x y n)) ∧
      a = f x y (s n) ∧ b = f x y n

/-- SANS has exactly the same third-counter transformed-call shape. -/
theorem dpPair_iff_ruleDerivedPair {a b : SANSTerm} :
    DependencyPairsWitness.DPPair a b ↔ RuleDerivedPair a b := by
  constructor
  · intro h
    cases h with
    | succ x y n =>
        exact ⟨x, y, n, RootStep.succ x y n, rfl, rfl⟩
  · rintro ⟨x, y, n, _, ha, hb⟩
    subst a
    subst b
    exact DependencyPairsWitness.DPPair.succ x y n

theorem projection_strict :
    StrictNatProjection
      DependencyPairsWitness.DPPair DependencyPairsWitness.sDepth :=
  fun h => DependencyPairsWitness.dp_pair_decreases h

theorem pair_problem_wf_from_projection :
    WellFounded DependencyPairsWitness.DPPairRev :=
  wf_reverse_of_strictNatProjection projection_strict

/-- The SANS control is also strongly normalizing under full contextual Step. -/
theorem full_contextual_step_wf :
    WellFounded LinearWitness.StepRev :=
  LinearWitness.wf_StepRev

/--
On the control, the same rule-derived transformed-call projection is available,
but it is not needed to escape duplication: the direct linear measure also
strictly decreases on every full contextual step.
-/
theorem projection_and_direct_routes :
    WellFounded DependencyPairsWitness.DPPairRev ∧
      (∀ {a b : SANSTerm}, Step a b →
        LinearWitness.mu b < LinearWitness.mu a) ∧
      WellFounded LinearWitness.StepRev :=
  ⟨pair_problem_wf_from_projection, LinearWitness.mu_step_decreases,
    full_contextual_step_wf⟩

end Control

end KO7Benchmark.ScoringAnchors.ProjectionRoute


