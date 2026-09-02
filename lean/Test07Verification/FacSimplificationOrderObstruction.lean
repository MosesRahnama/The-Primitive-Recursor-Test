namespace Test07Verification.FacSimplificationOrderObstruction

/-- Four function constructors plus variable leaves for the factorial obstruction. -/
inductive Term where
  | var : Nat -> Term
  | s : Term -> Term
  | p : Term -> Term
  | fac : Term -> Term
  | times : Term -> Term -> Term
  deriving Repr

/-- One-hole contexts over the factorial-obstruction signature. -/
inductive Context where
  | hole : Context
  | s : Context -> Context
  | p : Context -> Context
  | fac : Context -> Context
  | timesLeft : Context -> Term -> Context
  | timesRight : Term -> Context -> Context

def Context.plug : Context -> Term -> Term
  | .hole, t => t
  | .s c, t => .s (c.plug t)
  | .p c, t => .p (c.plug t)
  | .fac c, t => .fac (c.plug t)
  | .timesLeft c u, t => .times (c.plug t) u
  | .timesRight u c, t => .times u (c.plug t)

/-- Strict proper-subterm containment, including transitive containment. -/
inductive ProperSubterm : Term -> Term -> Prop where
  | sArg (t) : ProperSubterm t (.s t)
  | pArg (t) : ProperSubterm t (.p t)
  | facArg (t) : ProperSubterm t (.fac t)
  | timesLeft (t u) : ProperSubterm t (.times t u)
  | timesRight (t u) : ProperSubterm u (.times t u)
  | trans {t u v} : ProperSubterm t u -> ProperSubterm u v -> ProperSubterm t v

def Transitive (gt : Term -> Term -> Prop) : Prop :=
  ∀ {a b c}, gt a b -> gt b c -> gt a c

def Irreflexive (gt : Term -> Term -> Prop) : Prop :=
  ∀ t, ¬gt t t

def HasProperSubtermProperty (gt : Term -> Term -> Prop) : Prop :=
  ∀ {small big}, ProperSubterm small big -> gt big small

def ContextMonotone (gt : Term -> Term -> Prop) : Prop :=
  ∀ (c : Context) {a b}, gt a b -> gt (c.plug a) (c.plug b)

/--
No strict relation satisfying the core simplification-order laws can orient the
factorial rule from left to right.  The contradiction is structural: the right
side is strictly above `fac (p (s x))`, which is strictly above the left side.
-/
theorem no_simplification_order_orients_fac_rule
    (gt : Term -> Term -> Prop)
    (htrans : Transitive gt)
    (hirrefl : Irreflexive gt)
    (hsubterm : HasProperSubtermProperty gt)
    (hcontext : ContextMonotone gt)
    (x : Term) :
    ¬gt (.fac (.s x)) (.times (.fac (.p (.s x))) (.s x)) := by
  intro hforward
  have hp : gt (.p (.s x)) (.s x) :=
    hsubterm (.pArg (.s x))
  have hfac : gt (.fac (.p (.s x))) (.fac (.s x)) := by
    simpa [Context.plug] using hcontext (.fac .hole) hp
  have hrhs :
      gt (.times (.fac (.p (.s x))) (.s x)) (.fac (.p (.s x))) :=
    hsubterm (.timesLeft (.fac (.p (.s x))) (.s x))
  have hbackward :
      gt (.times (.fac (.p (.s x))) (.s x)) (.fac (.s x)) :=
    htrans hrhs hfac
  exact hirrefl _ (htrans hforward hbackward)

#print axioms no_simplification_order_orients_fac_rule

end Test07Verification.FacSimplificationOrderObstruction
