namespace Test07Verification.StrictMonotoneInterpretationObstruction

def StrictlyIncreasing (f : Nat -> Nat) : Prop :=
  ∀ {a b}, a < b -> f a < f b

/-- Every strictly increasing self-map of `Nat` is inflationary. -/
theorem strictlyIncreasing_ge_identity
    (f : Nat -> Nat) (h : StrictlyIncreasing f) :
    ∀ n, n ≤ f n := by
  intro n
  induction n with
  | zero => exact Nat.zero_le _
  | succ n ih =>
      exact Nat.le_trans (Nat.succ_le_succ ih) (h (Nat.lt_succ_self n))

/-- Strict increase implies weak monotonicity on `Nat`. -/
theorem strictlyIncreasing_monotone
    (f : Nat -> Nat) (h : StrictlyIncreasing f)
    {a b : Nat} (hab : a ≤ b) :
    f a ≤ f b := by
  rcases Nat.eq_or_lt_of_le hab with hEq | hLt
  · cases hEq
    exact Nat.le_refl _
  · exact Nat.le_of_lt (h hLt)

/--
No natural-number interpretation that is strict in the predecessor symbol,
factorial symbol, and first multiplication argument can orient the factorial
rule.  This includes strictly monotone polynomial interpretations over `Nat`,
independently of the interpretations chosen for `s` and the unused symbols.
-/
theorem no_strictly_monotone_nat_interpretation_orients_fac_rule
    (s p fac : Nat -> Nat)
    (times : Nat -> Nat -> Nat)
    (hp : StrictlyIncreasing p)
    (hfac : StrictlyIncreasing fac)
    (htimesLeft : ∀ b, StrictlyIncreasing (fun a => times a b))
    (x : Nat) :
    ¬fac (s x) > times (fac (p (s x))) (s x) := by
  intro hforward
  have hp_ge : s x ≤ p (s x) :=
    strictlyIncreasing_ge_identity p hp (s x)
  have hfac_ge : fac (s x) ≤ fac (p (s x)) :=
    strictlyIncreasing_monotone fac hfac hp_ge
  have htimes_ge :
      fac (p (s x)) ≤ times (fac (p (s x))) (s x) :=
    strictlyIncreasing_ge_identity
      (fun a => times a (s x)) (htimesLeft (s x)) (fac (p (s x)))
  exact Nat.not_lt_of_ge (Nat.le_trans hfac_ge htimes_ge) hforward

#print axioms strictlyIncreasing_ge_identity
#print axioms strictlyIncreasing_monotone
#print axioms no_strictly_monotone_nat_interpretation_orients_fac_rule

end Test07Verification.StrictMonotoneInterpretationObstruction
