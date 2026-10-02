/-
  Duplication-count family for the two-rule recursor.

    F(x, y, Z)    -> x
    F(x, y, S(n)) -> G_k(y, ..., y, F(x, y, n))      (k copies of y)

  k = 0 is the matched nonduplicating control (Schema A New System),
  k = 1 is Schema A, and k = 2, 4, 8 are the payload-scaling arms.

  An additive measure assigns every symbol a natural weight and sums the
  weights over all occurrences.  For the family symbol G_k the sum runs over
  its k payload arguments and its recursive argument, so a k-fold copy of y
  contributes k * eval y.  Nothing else about the measure is constrained:
  the weight of G_k may depend on k and may be zero.

  Results, no sorry, baseline axioms only (propext, Quot.sound):
    * `deficit_identity`            eval rhs + wS = eval lhs + wG k + k * eval y
    * `no_additive_orients_dup`     for every k >= 1 and every weight assignment
                                    some instance of the recursive rule fails to
                                    decrease strictly
    * `additive_orients_k0`         at k = 0 one explicit additive measure
                                    strictly orients both rules on every instance
    * `burden_mono`                 for fixed weights and payload, the right-hand
                                    surplus is monotone in k
-/

namespace PayloadScaling.DuplicationCountObstruction

/-- Terms of the k-parameterised schema. `gk k y r` denotes
    G_k(y, …, y, r) with k copies of the payload y. -/
inductive Term where
  | var : Nat → Term
  | z   : Term
  | s   : Term → Term
  | gk  : Nat → Term → Term → Term
  | f   : Term → Term → Term → Term
  deriving Repr

/-- Natural symbol weights.  `wG k` is the weight of the family symbol G_k. -/
structure Weights where
  wVar : Nat
  wZ   : Nat
  wS   : Nat
  wF   : Nat
  wG   : Nat → Nat

namespace Weights

/-- Additive evaluation: the sum of symbol weights over every occurrence. -/
def eval (M : Weights) : Term → Nat
  | .var _      => M.wVar
  | .z          => M.wZ
  | .s t        => M.wS + M.eval t
  | .gk k y r   => M.wG k + k * M.eval y + M.eval r
  | .f x y n    => M.wF + M.eval x + M.eval y + M.eval n

@[simp] theorem eval_var (M : Weights) (i : Nat) : M.eval (.var i) = M.wVar := rfl
@[simp] theorem eval_z   (M : Weights) : M.eval .z = M.wZ := rfl
@[simp] theorem eval_s   (M : Weights) (t : Term) : M.eval (.s t) = M.wS + M.eval t := rfl
@[simp] theorem eval_gk  (M : Weights) (k : Nat) (y r : Term) :
    M.eval (.gk k y r) = M.wG k + k * M.eval y + M.eval r := rfl
@[simp] theorem eval_f   (M : Weights) (x y n : Term) :
    M.eval (.f x y n) = M.wF + M.eval x + M.eval y + M.eval n := rfl

end Weights

/-- S^j(t). -/
def sIter : Nat → Term → Term
  | 0,     t => t
  | j + 1, t => .s (sIter j t)

@[simp] theorem eval_sIter (M : Weights) (j : Nat) (t : Term) :
    M.eval (sIter j t) = j * M.wS + M.eval t := by
  induction j with
  | zero => simp [sIter]
  | succ j ih =>
    simp only [sIter, Weights.eval_s, ih, Nat.succ_mul]
    omega

/-- Left-hand side of the recursive rule. -/
def lhs (x y n : Term) : Term := .f x y (.s n)

/-- Right-hand side of the recursive rule at duplication count k. -/
def rhs (k : Nat) (x y n : Term) : Term := .gk k y (.f x y n)

/-- The exact accounting of one recursive step under any additive measure.
    The right-hand side gives up one S and gains the weight of G_k together
    with k further copies of the payload. -/
theorem deficit_identity (M : Weights) (k : Nat) (x y n : Term) :
    M.eval (rhs k x y n) + M.wS = M.eval (lhs x y n) + M.wG k + k * M.eval y := by
  simp only [rhs, lhs, Weights.eval_gk, Weights.eval_f, Weights.eval_s]
  omega

/-- For every k ≥ 1 and every additive weight assignment there is an instance
    of the recursive rule on which the measure does not strictly decrease.
    The witness pumps the payload to y := S^{wS}(Z), so that a single copy of
    y already outweighs the one S the rule removes. -/
theorem no_additive_orients_dup (M : Weights) (k : Nat) (hk : 1 ≤ k) :
    ∃ x y n : Term, M.eval (lhs x y n) ≤ M.eval (rhs k x y n) := by
  refine ⟨.z, sIter M.wS .z, .z, ?_⟩
  have hid := deficit_identity M k .z (sIter M.wS .z) .z
  have hy : M.wS ≤ M.eval (sIter M.wS .z) := by
    simp only [eval_sIter, Weights.eval_z]
    exact Nat.le_trans (Nat.le_mul_self M.wS) (Nat.le_add_right _ _)
  have hk' : M.eval (sIter M.wS .z) ≤ k * M.eval (sIter M.wS .z) :=
    Nat.le_mul_of_pos_left _ hk
  omega

/-- Consequently no additive measure strictly orients every instance of the
    recursive rule once the payload is copied at least once. -/
theorem no_additive_strict_dup (M : Weights) (k : Nat) (hk : 1 ≤ k) :
    ¬ (∀ x y n : Term, M.eval (rhs k x y n) < M.eval (lhs x y n)) := by
  intro h
  obtain ⟨x, y, n, hle⟩ := no_additive_orients_dup M k hk
  exact Nat.lt_irrefl _ (Nat.lt_of_lt_of_le (h x y n) hle)

/-- The contrast at k = 0.  One explicit additive measure, wF = wS = 1 and
    every other weight 0, strictly orients both rules on every instance, so
    the obstruction is carried entirely by the copied payload. -/
def k0Measure : Weights :=
  { wVar := 0, wZ := 0, wS := 1, wF := 1, wG := fun _ => 0 }

theorem additive_orients_k0_rec (x y n : Term) :
    k0Measure.eval (rhs 0 x y n) < k0Measure.eval (lhs x y n) := by
  simp [rhs, lhs, k0Measure, Weights.eval]

theorem additive_orients_k0_base (x y : Term) :
    k0Measure.eval x < k0Measure.eval (.f x y .z) := by
  simp only [Weights.eval_f, Weights.eval_z, k0Measure]
  omega

/-- For fixed weights and a fixed payload, the surplus the right-hand side
    carries over the left grows with the duplication count whenever the
    family weight does. -/
theorem burden_mono (M : Weights) (x y n : Term) {k₁ k₂ : Nat}
    (hk : k₁ ≤ k₂) (hG : M.wG k₁ ≤ M.wG k₂) :
    M.eval (rhs k₁ x y n) ≤ M.eval (rhs k₂ x y n) := by
  simp only [rhs, Weights.eval_gk]
  have := Nat.mul_le_mul_right (M.eval y) hk
  omega

#print axioms deficit_identity
#print axioms no_additive_orients_dup
#print axioms no_additive_strict_dup
#print axioms additive_orients_k0_rec
#print axioms additive_orients_k0_base
#print axioms burden_mono

end PayloadScaling.DuplicationCountObstruction
