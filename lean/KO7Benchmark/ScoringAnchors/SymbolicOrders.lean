/- 
Relation: SchemaKernel root rules, Demarcation.LPO, SchemaMPO.MPO, and the SANS root-rule templates.
Closure: root for symbolic/path-order method statements; no contextual-closure theorem is inferred from a root orientation alone.
Property: exact variable-condition barriers, a coefficient-weighted variable barrier, exact LPO precedence success/failure, native specialized-MPO root termination, and SANS controls.
Trust: mathlib and existing project modules only; no sorry, admit, new axiom, native_decide, unsafe, partial, or opaque.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.CandidateC_KBOFailure
import KO7Benchmark.PaperB.Demarcation
import KO7Benchmark.SchemaTests.PathOrderFailurePatterns
import KO7Benchmark.SchemaTests.SchemaSpecializedMPO
import KO7Benchmark.SANSTests.KBOStyleSupport

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.SymbolicOrders

namespace NecessaryConditions

open KO7Benchmark.SchemaTests
open SKTerm

/-- Any relation satisfying the standard KBO variable condition fails to
orient the duplicating recursive rule. This is a necessary-condition barrier,
not a formalization of the complete KBO relation. -/
theorem standard_variable_condition_blocks_recursive_rule
    (gt : SKTerm → SKTerm → Prop)
    (hvc : CandidateC.RespectsVariableCondition gt) :
    ¬ gt CandidateC.succLhs CandidateC.succRhs := by
  intro horient
  have hmono := hvc.count_mono (v := 1) horient
  simp at hmono

/-- The family form of the standard variable-condition obstruction. -/
theorem standard_variable_condition_family_empty :
    ¬ ∃ gt : SKTerm → SKTerm → Prop,
        CandidateC.RespectsVariableCondition gt ∧
          gt CandidateC.succLhs CandidateC.succRhs :=
  CandidateC.no_variable_condition_orientation

/-- Coefficient of variable `v` in a linear constructor-coefficient weight.
Constructor constants do not affect this coefficient and are absent. -/
def weightedCoeff
    (sArg gLeft gRight fFirst fSecond fThird v : Nat) : SKTerm → Nat
  | .var w => if v = w then 1 else 0
  | .z => 0
  | .s t => sArg * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v t
  | .g a b =>
      gLeft * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v a +
      gRight * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v b
  | .f x y n =>
      fFirst * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v x +
      fSecond * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v y +
      fThird * weightedCoeff sArg gLeft gRight fFirst fSecond fThird v n

/-- The coefficient-weighted variable condition for an order relation:
every variable coefficient on the right is at most its coefficient on the left.
This is a necessary substitution-stability condition, not a definition of KBO. -/
def RespectsWeightedVariableCondition
    (sArg gLeft gRight fFirst fSecond fThird : Nat)
    (gt : SKTerm → SKTerm → Prop) : Prop :=
  ∀ {s t : SKTerm} {v : Nat}, gt s t →
    weightedCoeff sArg gLeft gRight fFirst fSecond fThird v t ≤
      weightedCoeff sArg gLeft gRight fFirst fSecond fThird v s

/-- On the copied variable `y`, the recursive rule has coefficient
`fSecond` on the left and `gLeft + gRight * fSecond` on the right. -/
theorem weightedCoeff_recursive_y
    (sArg gLeft gRight fFirst fSecond fThird : Nat) :
    weightedCoeff sArg gLeft gRight fFirst fSecond fThird 1
        CandidateC.succLhs = fSecond ∧
    weightedCoeff sArg gLeft gRight fFirst fSecond fThird 1
        CandidateC.succRhs = gLeft + gRight * fSecond := by
  constructor
  · simp [weightedCoeff, CandidateC.succLhs]
  · simp [weightedCoeff, CandidateC.succRhs]

/-- Positive use of the copied argument by both relevant `G` paths forces
the weighted coefficient of `y` to grow. No positivity assumption is needed
on the other constructor arguments. -/
theorem weightedCoeff_recursive_y_strictly_grows
    (sArg gLeft gRight fFirst fSecond fThird : Nat)
    (hLeft : 0 < gLeft) (hRight : 0 < gRight) :
    weightedCoeff sArg gLeft gRight fFirst fSecond fThird 1
        CandidateC.succLhs <
      weightedCoeff sArg gLeft gRight fFirst fSecond fThird 1
        CandidateC.succRhs := by
  rw [(weightedCoeff_recursive_y
      sArg gLeft gRight fFirst fSecond fThird).1,
    (weightedCoeff_recursive_y
      sArg gLeft gRight fFirst fSecond fThird).2]
  nlinarith

/-- The coefficient-weighted variable condition cannot coexist with orientation
of the recursive rule when the copied `y` is used with positive coefficients
on both relevant `G` paths. -/
theorem positive_weighted_variable_condition_blocks_recursive_rule
    (sArg gLeft gRight fFirst fSecond fThird : Nat)
    (hLeft : 0 < gLeft) (hRight : 0 < gRight)
    (gt : SKTerm → SKTerm → Prop)
    (hvc : RespectsWeightedVariableCondition
      sArg gLeft gRight fFirst fSecond fThird gt) :
    ¬ gt CandidateC.succLhs CandidateC.succRhs := by
  intro horient
  have hle := hvc (v := 1) horient
  have hlt := weightedCoeff_recursive_y_strictly_grows
    sArg gLeft gRight fFirst fSecond fThird hLeft hRight
  exact (Nat.not_lt_of_ge hle) hlt

/-- A root-rank comparison without `F > G` cannot use the precedence route.
This is only a necessary-condition proxy; the native LPO theorem is separate. -/
theorem root_rank_route_fails_without_F_gt_G
    (rank : CandidateA.PrecSym → Nat)
    (h : ¬ rank CandidateA.PrecSym.g < rank CandidateA.PrecSym.f)
    (x y n : SKTerm) :
    ¬ rank (CandidateA.rootSym (g y (f x y n))) <
      rank (CandidateA.rootSym (f x y (s n))) :=
  PathOrderFailurePatterns.no_F_gt_G_route_fails rank h x y n

end NecessaryConditions

namespace SANSControls

open KO7Benchmark.SANSTests
open SANSTerm

/-- The ordinary standard KBO variable condition holds on both SANS rule
templates. This is the exact control for the duplicating-system failure. -/
theorem standard_variable_condition_holds_on_sans_templates :
    (∀ v : Nat,
      KBOStyleSupport.countVar v KBOStyleSupport.baseRhs ≤
        KBOStyleSupport.countVar v KBOStyleSupport.baseLhs) ∧
    (∀ v : Nat,
      KBOStyleSupport.countVar v KBOStyleSupport.succRhs ≤
        KBOStyleSupport.countVar v KBOStyleSupport.succLhs) :=
  ⟨KBOStyleSupport.variable_condition_base,
    KBOStyleSupport.variable_condition_succ⟩

/-- Unit positive subterm coefficients on the SANS signature. -/
def unitWeightedCoeff (v : Nat) : SANSTerm → Nat
  | .var w => if v = w then 1 else 0
  | .z => 0
  | .s t => unitWeightedCoeff v t
  | .g t => unitWeightedCoeff v t
  | .f x y n => unitWeightedCoeff v x + unitWeightedCoeff v y + unitWeightedCoeff v n

theorem unitWeightedCoeff_eq_countVar (v : Nat) (t : SANSTerm) :
    unitWeightedCoeff v t = KBOStyleSupport.countVar v t := by
  induction t with
  | var w => rfl
  | z => rfl
  | s t ih => simpa [unitWeightedCoeff, KBOStyleSupport.countVar] using ih
  | g t ih => simpa [unitWeightedCoeff, KBOStyleSupport.countVar] using ih
  | f x y n ihx ihy ihn =>
      simp [unitWeightedCoeff, KBOStyleSupport.countVar, ihx, ihy, ihn]

/-- At the all-one positive coefficient assignment, the weighted variable
condition holds on both SANS rule templates. -/
theorem unit_positive_weighted_condition_holds_on_sans_templates :
    (∀ v : Nat,
      unitWeightedCoeff v KBOStyleSupport.baseRhs ≤
        unitWeightedCoeff v KBOStyleSupport.baseLhs) ∧
    (∀ v : Nat,
      unitWeightedCoeff v KBOStyleSupport.succRhs ≤
        unitWeightedCoeff v KBOStyleSupport.succLhs) := by
  constructor
  · intro v
    rw [unitWeightedCoeff_eq_countVar, unitWeightedCoeff_eq_countVar]
    exact KBOStyleSupport.variable_condition_base v
  · intro v
    rw [unitWeightedCoeff_eq_countVar, unitWeightedCoeff_eq_countVar]
    exact KBOStyleSupport.variable_condition_succ v

/-- The SANS fixture also satisfies the local weight and precedence obligations
recorded for its KBO-style proposal. This stops at those obligations because the
source module does not define a native KBO relation. -/
theorem sans_kbo_local_obligations :
    (∀ x y : SANSTerm,
      KBOStyleSupport.weight x <
        KBOStyleSupport.weight (f x y z)) ∧
    (∀ x y n : SANSTerm,
      KBOStyleSupport.weight (g (f x y n)) =
        KBOStyleSupport.weight (f x y (s n))) ∧
    (∀ x y n : SANSTerm,
      PathOrderSupport.precRank
          (PathOrderSupport.rootSym (g (f x y n))) <
        PathOrderSupport.precRank
          (PathOrderSupport.rootSym (f x y (s n)))) :=
  ⟨KBOStyleSupport.root_base_weight_drop,
    KBOStyleSupport.root_succ_weight_tie,
    KBOStyleSupport.root_succ_prec_breaks_tie⟩

end SANSControls

namespace NativeLPO

/-- For the actual native LPO relation in `Demarcation`, both schema rules
are oriented exactly when the precedence puts `F` above `G`. -/
theorem orients_schema_iff_F_gt_G
    (P : KO7Benchmark.PaperB.Demarcation.Sym →
      KO7Benchmark.PaperB.Demarcation.Sym → Prop) :
    KO7Benchmark.PaperB.Demarcation.OrientsBothRules P ↔ P .f .g :=
  KO7Benchmark.PaperB.Demarcation.orientsBothRules_iff P

/-- Exact native-LPO failure theorem. -/
theorem fails_without_F_gt_G
    (P : KO7Benchmark.PaperB.Demarcation.Sym →
      KO7Benchmark.PaperB.Demarcation.Sym → Prop)
    (hFG : ¬ P .f .g) :
    ¬ KO7Benchmark.PaperB.Demarcation.OrientsBothRules P := by
  intro h
  exact hFG ((KO7Benchmark.PaperB.Demarcation.orientsBothRules_iff P).1 h)

/-- Exact native-LPO success theorem for the minimal precedence containing only
`F > G`. -/
theorem minimal_precedence_succeeds :
    KO7Benchmark.PaperB.Demarcation.OrientsBothRules
      (fun a b =>
        a = KO7Benchmark.PaperB.Demarcation.Sym.f ∧
        b = KO7Benchmark.PaperB.Demarcation.Sym.g) :=
  KO7Benchmark.PaperB.Demarcation.minimal_precedence_orients

/-- Across all 24 total precedences, exactly 12 put `F` above `G`; by
`orients_schema_iff_F_gt_G`, these are exactly the 12 native-LPO orienting orders. -/
theorem total_precedence_split :
    KO7Benchmark.PaperB.Demarcation.totalOrders.length = 24 ∧
    (KO7Benchmark.PaperB.Demarcation.totalOrders.filter fun l =>
      decide (KO7Benchmark.PaperB.Demarcation.precOf l .f .g)).length = 12 :=
  ⟨KO7Benchmark.PaperB.Demarcation.totalOrders_length,
    KO7Benchmark.PaperB.Demarcation.count_F_above_G⟩

end NativeLPO

namespace NativeMPO

open KO7Benchmark.SchemaTests

/-- The actual schema-specialized MPO orients every root rule. -/
theorem orients_every_root_step :
    ∀ {a b : SKTerm}, RootStep a b → SchemaMPO.MPO a b :=
  SchemaMPO.mpo_orients_rootStep

/-- The same-head multiset-style clause used by the recursive call is an actual
constructor of the native specialized MPO. -/
theorem recursive_call_is_mpo_smaller (x y n : SKTerm) :
    SchemaMPO.MPO (SKTerm.f x y (SKTerm.s n)) (SKTerm.f x y n) :=
  SchemaMPO.mpo_f_counter x y n

/-- Every native specialized-MPO comparison strictly decreases its Veblen
ordinal rank. -/
theorem native_ordinal_rank_decreases {a b : SKTerm}
    (h : SchemaMPO.MPO a b) :
    SchemaMPO.mpoOrd b < SchemaMPO.mpoOrd a :=
  SchemaMPO.mpoOrd_strict_of_mpo h

/-- The reverse native specialized-MPO relation is well founded by that ordinal
ranking. -/
theorem native_mpo_reverse_wellFounded : WellFounded SchemaMPO.MPORev :=
  SchemaMPO.wf_MPORev

/-- Root-step strong normalization follows from actual MPO orientation plus
native well-foundedness of that same MPO relation. This intentionally says only
`RootStep`; the specialized source has no general congruence clauses. -/
theorem rootStep_reverse_wellFounded_by_native_mpo :
    WellFounded (fun a b : SKTerm => RootStep b a) :=
  SchemaMPO.wf_RootStepRev_mpo

end NativeMPO

end KO7Benchmark.ScoringAnchors.SymbolicOrders
