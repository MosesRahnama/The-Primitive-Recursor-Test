import Test07Verification.FacSimplificationOrderObstruction
import Test07Verification.StrictMonotoneInterpretationObstruction

set_option autoImplicit false

namespace Test07Verification.FacDirectMethodObstructions

/--
The laws used by the factorial obstruction for a strict simplification order.
Concrete LPO, RPO, or KBO implementations are covered only after proving that
their strict relation satisfies these four fields.
-/
structure SimplificationOrderAttempt where
  gt : FacSimplificationOrderObstruction.Term ->
    FacSimplificationOrderObstruction.Term -> Prop
  transitive : FacSimplificationOrderObstruction.Transitive gt
  irreflexive : FacSimplificationOrderObstruction.Irreflexive gt
  properSubterm : FacSimplificationOrderObstruction.HasProperSubtermProperty gt
  contextMonotone : FacSimplificationOrderObstruction.ContextMonotone gt

/--
The semantic data used by the strictly monotone natural-number obstruction.
Strictly monotone polynomial interpretations over `Nat` are instances of this
interface once the three required strictness proofs are supplied.
-/
structure StrictNatInterpretationAttempt where
  s : Nat -> Nat
  p : Nat -> Nat
  fac : Nat -> Nat
  times : Nat -> Nat -> Nat
  pStrict : StrictMonotoneInterpretationObstruction.StrictlyIncreasing p
  facStrict : StrictMonotoneInterpretationObstruction.StrictlyIncreasing fac
  timesLeftStrict : forall b,
    StrictMonotoneInterpretationObstruction.StrictlyIncreasing
      (fun a => times a b)

/--
Exactly the two direct-method families discharged by the current Test 07 Lean
proofs. This type is intentionally not a classification of all direct methods:
it excludes weak or capped interpretations, matrix interpretations, and every
other family not represented by one of these constructors.
-/
inductive TestedDirectAttempt where
  | simplificationOrder (attempt : SimplificationOrderAttempt)
  | strictNatInterpretation (attempt : StrictNatInterpretationAttempt)

/--
The usual all-substitutions orientation obligation for the factorial rule
`fac(s(x)) -> times(fac(p(s(x))), s(x))`, specialized to each represented
direct-method family.
-/
def OrientsFactorialRule : TestedDirectAttempt -> Prop
  | .simplificationOrder attempt =>
      forall x,
        attempt.gt
          (.fac (.s x))
          (.times (.fac (.p (.s x))) (.s x))
  | .strictNatInterpretation attempt =>
      forall x,
        attempt.fac (attempt.s x) >
          attempt.times
            (attempt.fac (attempt.p (attempt.s x)))
            (attempt.s x)

/--
No lawful simplification-order attempt can orient the factorial rule. This is
the formal adapter used for LPO, RPO, and KBO only when the concrete order has
the laws packaged by `SimplificationOrderAttempt`.
-/
theorem no_simplification_order_attempt_orients_factorial_rule
    (attempt : SimplificationOrderAttempt) :
    Not (OrientsFactorialRule (.simplificationOrder attempt)) := by
  intro horients
  exact
    FacSimplificationOrderObstruction.no_simplification_order_orients_fac_rule
      attempt.gt
      attempt.transitive
      attempt.irreflexive
      attempt.properSubterm
      attempt.contextMonotone
      (.var 0)
      (horients (.var 0))

/--
No strictly monotone natural-number interpretation attempt can orient the
factorial rule. In particular, this rules out strictly monotone polynomial
interpretations over `Nat` satisfying the displayed strictness interface.
-/
theorem no_strict_nat_interpretation_attempt_orients_factorial_rule
    (attempt : StrictNatInterpretationAttempt) :
    Not (OrientsFactorialRule (.strictNatInterpretation attempt)) := by
  intro horients
  exact
    StrictMonotoneInterpretationObstruction.no_strictly_monotone_nat_interpretation_orients_fac_rule
      attempt.s
      attempt.p
      attempt.fac
      attempt.times
      attempt.pStrict
      attempt.facStrict
      attempt.timesLeftStrict
      0
      (horients 0)

/--
No attempt in the explicitly represented Test 07 direct-family universe
orients the factorial rule.
-/
theorem no_tested_direct_attempt_orients_factorial_rule
    (attempt : TestedDirectAttempt) :
    Not (OrientsFactorialRule attempt) := by
  cases attempt with
  | simplificationOrder orderAttempt =>
      exact no_simplification_order_attempt_orients_factorial_rule orderAttempt
  | strictNatInterpretation interpretationAttempt =>
      exact
        no_strict_nat_interpretation_attempt_orients_factorial_rule
          interpretationAttempt

#check @no_simplification_order_attempt_orients_factorial_rule
#check @no_strict_nat_interpretation_attempt_orients_factorial_rule
#check @no_tested_direct_attempt_orients_factorial_rule

#print axioms no_simplification_order_attempt_orients_factorial_rule
#print axioms no_strict_nat_interpretation_attempt_orients_factorial_rule
#print axioms no_tested_direct_attempt_orients_factorial_rule

end Test07Verification.FacDirectMethodObstructions
