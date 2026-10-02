namespace Test07Verification.AdditiveDuplicationObstruction

/-- Terms needed for the AG01/#3.16 duplicating rule. -/
inductive Term where
  | var : Nat -> Term
  | zero : Term
  | s : Term -> Term
  | plus : Term -> Term -> Term
  | times : Term -> Term -> Term
  deriving Repr

/-- A nonnegative additive assignment, represented by natural symbol weights. -/
structure SymbolWeights where
  zero : Nat
  s : Nat
  plus : Nat
  times : Nat

/-- The sum of the assigned weights over all function-symbol occurrences. -/
def additiveWeight (w : SymbolWeights) : Term -> Nat
  | .var _ => 0
  | .zero => w.zero
  | .s t => w.s + additiveWeight w t
  | .plus t u => w.plus + additiveWeight w t + additiveWeight w u
  | .times t u => w.times + additiveWeight w t + additiveWeight w u

/--
For every nonnegative additive symbol-weight assignment, the displayed AG01
duplicating rule has a concrete substitution instance whose right-hand side
does not have smaller weight.  Hence no such weight strictly orients every
instance of that rule from left to right.
-/
theorem every_additive_weight_has_nondecreasing_ag316_instance
    (w : SymbolWeights) :
    ∃ x y,
      additiveWeight w (.times x (.s y)) ≤
        additiveWeight w (.plus (.times x y) x) := by
  refine ⟨.s .zero, .var 0, ?_⟩
  have h :
      additiveWeight w (.plus (.times (.s .zero) (.var 0)) (.s .zero)) =
        additiveWeight w (.times (.s .zero) (.s (.var 0))) +
          (w.plus + w.zero) := by
    simp only [additiveWeight, Nat.add_zero]
    ac_rfl
  rw [h]
  exact Nat.le_add_right _ _

#print axioms every_additive_weight_has_nondecreasing_ag316_instance

end Test07Verification.AdditiveDuplicationObstruction
