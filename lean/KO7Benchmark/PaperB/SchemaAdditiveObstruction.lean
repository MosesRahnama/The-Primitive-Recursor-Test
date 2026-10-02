/-
  Additive-layer duplication obstruction for the primitive duplicating schema.
  Mechanizes Lemma A.6 (additive obstruction) in Rahnama_PRT_Benchmark_NeurIPS.tex.

  The proof pumps the substitution y := S(Z) (i.e. sIter 1 Z), a ground
  term. With k=1, both sides expand linearly and omega closes the contradiction
  via M.wG_pos. (k=M.wS+1 also works but requires nonlinear arithmetic;
  k=1 is simpler and sufficient.)

  Architectural spec: lean-dev.md §4.2.
-/
import KO7Benchmark.PaperB.Basic
import Mathlib.Tactic

namespace KO7Benchmark.PaperB

open KO7Benchmark.SchemaTests
open SKTerm

/-! ## Additive constructor-weight measures over SKTerm -/

structure AdditiveSKMeasure where
  wVar : Nat
  wZ   : Nat
  wS   : Nat
  wG   : Nat
  wF   : Nat
  wG_pos : 0 < wG

namespace AdditiveSKMeasure

def eval (M : AdditiveSKMeasure) : SKTerm → Nat
  | var _   => M.wVar
  | z       => M.wZ
  | s t     => M.wS + M.eval t
  | g a b   => M.wG + M.eval a + M.eval b
  | f x y n => M.wF + M.eval x + M.eval y + M.eval n

-- Definitional @[simp] equations for eval
@[simp] theorem eval_var (M : AdditiveSKMeasure) (n : Nat) :
    M.eval (var n) = M.wVar := rfl
@[simp] theorem eval_z (M : AdditiveSKMeasure) :
    M.eval z = M.wZ := rfl
@[simp] theorem eval_s (M : AdditiveSKMeasure) (t : SKTerm) :
    M.eval (s t) = M.wS + M.eval t := rfl
@[simp] theorem eval_g (M : AdditiveSKMeasure) (a b : SKTerm) :
    M.eval (g a b) = M.wG + M.eval a + M.eval b := rfl
@[simp] theorem eval_f (M : AdditiveSKMeasure) (x y n : SKTerm) :
    M.eval (f x y n) = M.wF + M.eval x + M.eval y + M.eval n := rfl

-- sIter k t = S^k(t): ground-term pumping helper
def sIter : Nat → SKTerm → SKTerm
  | 0,   t => t
  | k+1, t => s (sIter k t)

@[simp] theorem eval_sIter (M : AdditiveSKMeasure) (k : Nat) (t : SKTerm) :
    M.eval (sIter k t) = k * M.wS + M.eval t := by
  induction k with
  | zero => simp [sIter]
  | succ k ih =>
    simp only [sIter, eval_s, ih]
    ring

-- No additive measure orients the recursive rule at the root level.
-- Pump y := sIter 1 z = S(Z). The resulting inequality requires M.wG + M.wZ < 0,
-- contradicting M.wG_pos.
theorem no_additive_orients_schema_recursive_root
    (M : AdditiveSKMeasure) :
    ¬ (∀ x y n : SKTerm,
        M.eval (g y (f x y n)) < M.eval (f x y (s n))) := by
  intro h
  have hlt := h z (sIter 1 z) z
  simp only [eval_g, eval_f, eval_s, eval_sIter, eval_z, Nat.one_mul] at hlt
  have hG : 0 < M.wG := M.wG_pos
  omega

-- Context-closed corollary: no additive measure strictly decreases on Step.
theorem no_additive_orients_schema_step
    (M : AdditiveSKMeasure) :
    ¬ (∀ {a b : SKTerm}, Step a b → M.eval b < M.eval a) := by
  intro h
  apply no_additive_orients_schema_recursive_root M
  intro x y n
  exact h (Step.root (RootStep.succ x y n))

end AdditiveSKMeasure

end KO7Benchmark.PaperB
