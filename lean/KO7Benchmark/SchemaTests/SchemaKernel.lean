/-
  Schema-kernel TRS: the two-rule system used in Test 12.

  (VAR x y n)
  (RULES
    F(x, y, Z) -> x
    F(x, y, S(n)) -> G(y, F(x, y, n))
  )

  This file defines the term language, the root step relation,
  and the full context-closed step relation.
-/
import Mathlib.Data.Nat.Basic

namespace KO7Benchmark.SchemaTests

inductive SKTerm where
  | var : Nat → SKTerm
  | z : SKTerm
  | s : SKTerm → SKTerm
  | g : SKTerm → SKTerm → SKTerm
  | f : SKTerm → SKTerm → SKTerm → SKTerm
deriving DecidableEq, Repr

open SKTerm

/-- Root steps of the schema-kernel TRS. -/
inductive RootStep : SKTerm → SKTerm → Prop
  | base (x y : SKTerm) : RootStep (f x y z) x
  | succ (x y n : SKTerm) : RootStep (f x y (s n)) (g y (f x y n))

/-- Standard contextual closure of the root rules. -/
inductive Step : SKTerm → SKTerm → Prop
  | root {t u : SKTerm} : RootStep t u → Step t u
  | s_arg {t u : SKTerm} : Step t u → Step (s t) (s u)
  | g_left {t u b : SKTerm} : Step t u → Step (g t b) (g u b)
  | g_right {a t u : SKTerm} : Step t u → Step (g a t) (g a u)
  | f_arg1 {t u b c : SKTerm} : Step t u → Step (f t b c) (f u b c)
  | f_arg2 {a t u c : SKTerm} : Step t u → Step (f a t c) (f a u c)
  | f_arg3 {a b t u : SKTerm} : Step t u → Step (f a b t) (f a b u)

end KO7Benchmark.SchemaTests

