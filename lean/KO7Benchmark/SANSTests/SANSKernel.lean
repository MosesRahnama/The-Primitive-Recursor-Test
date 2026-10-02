/-
  Schema Test A New System (SANS) kernel.

  (VAR x y n)
  (RULES
    F(x, y, Z)    -> x
    F(x, y, S(n)) -> G(F(x, y, n))
  )

  The only difference from the duplicating Schema A kernel is the step
  rule's right-hand side: `G` is unary here and receives only the
  recursive `F` call, so `y` is not duplicated. The non-duplicating
  shape is the whole point of the variant — the orientation obstruction
  that blocks direct measures on Schema A's rule is lifted.

  This file defines the term language, the root step relation, and the
  full context-closed step relation. It is intentionally parallel in
  structure to `KO7Benchmark/SchemaTests/SchemaKernel.lean`, differing
  only in that `g` is unary.
-/
import Mathlib.Data.Nat.Basic

namespace KO7Benchmark.SANSTests

inductive SANSTerm where
  | var : Nat → SANSTerm
  | z : SANSTerm
  | s : SANSTerm → SANSTerm
  | g : SANSTerm → SANSTerm
  | f : SANSTerm → SANSTerm → SANSTerm → SANSTerm
deriving DecidableEq, Repr

open SANSTerm

/-- Root steps of the SANS TRS. -/
inductive RootStep : SANSTerm → SANSTerm → Prop
  | base (x y : SANSTerm) : RootStep (f x y z) x
  | succ (x y n : SANSTerm) : RootStep (f x y (s n)) (g (f x y n))

/-- Standard contextual closure of the root rules. Note the absence of
`g_left` / `g_right` — SANS's `g` is unary, so only `g_arg` is needed. -/
inductive Step : SANSTerm → SANSTerm → Prop
  | root {t u : SANSTerm} : RootStep t u → Step t u
  | s_arg {t u : SANSTerm} : Step t u → Step (s t) (s u)
  | g_arg {t u : SANSTerm} : Step t u → Step (g t) (g u)
  | f_arg1 {t u b c : SANSTerm} : Step t u → Step (f t b c) (f u b c)
  | f_arg2 {a t u c : SANSTerm} : Step t u → Step (f a t c) (f a u c)
  | f_arg3 {a b t u : SANSTerm} : Step t u → Step (f a b t) (f a b u)

end KO7Benchmark.SANSTests
