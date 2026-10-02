/-
  Counter erasure (ICLR Appendix C, Proposition 4).

  Relation: the erased two-rule system on a binary symbol Fbar,
      Fbar(x, y) -> x,   Fbar(x, y) -> G(y, Fbar(x, y)),
    obtained from the schema by deleting the third argument of F.
  Closure: full contextual closure `Step` (root steps under every constructor).
  Property: the erased system has an infinite reduction sequence, so it is not
    terminating; the reverse step relation is not well founded. The base rule
    remains available at every stage of the sequence.
  Trust: mathlib only; no sorry, no axiom, no native_decide.
-/
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.CounterErasure

/-- Terms of the erased signature: variables, Z, S, binary G, binary Fbar. -/
inductive ETerm
  | var : Nat → ETerm
  | z : ETerm
  | s : ETerm → ETerm
  | g : ETerm → ETerm → ETerm
  | fbar : ETerm → ETerm → ETerm
  deriving DecidableEq, Repr

open ETerm

/-- Root steps of the erased system. -/
inductive RootStep : ETerm → ETerm → Prop
  | base (x y : ETerm) : RootStep (fbar x y) x
  | succ (x y : ETerm) : RootStep (fbar x y) (g y (fbar x y))

/-- Full contextual closure of the root steps. -/
inductive Step : ETerm → ETerm → Prop
  | root {t u : ETerm} : RootStep t u → Step t u
  | s_arg {t u : ETerm} : Step t u → Step (s t) (s u)
  | g_left {t u b : ETerm} : Step t u → Step (g t b) (g u b)
  | g_right {a t u : ETerm} : Step t u → Step (g a t) (g a u)
  | fbar_left {t u b : ETerm} : Step t u → Step (fbar t b) (fbar u b)
  | fbar_right {a t u : ETerm} : Step t u → Step (fbar a t) (fbar a u)

/-- Reverse step relation: `StepRev a b` when `b` steps to `a`. -/
def StepRev : ETerm → ETerm → Prop := fun a b => Step b a

/-- `wrap y k t` is `G(y, G(y, ... G(y, t)))` with `k` occurrences of `G`. -/
def wrap (y : ETerm) : Nat → ETerm → ETerm
  | 0, t => t
  | k + 1, t => g y (wrap y k t)

/-- Stage `k` of the infinite sequence: `Fbar(x, y)` under `k` frames `G(y, _)`. -/
def orbit (x y : ETerm) (k : Nat) : ETerm := wrap y k (fbar x y)

theorem wrap_step (y : ETerm) (k : Nat) {t u : ETerm} (h : Step t u) :
    Step (wrap y k t) (wrap y k u) := by
  induction k with
  | zero => exact h
  | succ k ih => exact Step.g_right ih

theorem wrap_g_inner (y : ETerm) (k : Nat) (t : ETerm) :
    wrap y k (g y t) = wrap y (k + 1) t := by
  induction k with
  | zero => rfl
  | succ k ih => simp [wrap, ih]

/-- Each stage steps to the next by the recursive rule applied to the innermost
    `Fbar(x, y)`. -/
theorem orbit_step (x y : ETerm) (k : Nat) : Step (orbit x y k) (orbit x y (k + 1)) := by
  have h := wrap_step y k (Step.root (RootStep.succ x y))
  unfold orbit
  rw [wrap_g_inner] at h
  exact h

/-- The base rule is available at every stage as well. -/
theorem orbit_base_step (x y : ETerm) (k : Nat) : Step (orbit x y k) (wrap y k x) :=
  wrap_step y k (Step.root (RootStep.base x y))

/-- Proposition 4: the erased system has an infinite reduction sequence. -/
theorem counterErased_infinite_sequence (x y : ETerm) :
    ∃ seq : Nat → ETerm, ∀ k, Step (seq k) (seq (k + 1)) :=
  ⟨orbit x y, orbit_step x y⟩

/-- No element of a strictly descending chain is accessible. -/
theorem no_acc_of_chain {α : Type} {R : α → α → Prop} (seq : Nat → α)
    (h : ∀ k, R (seq (k + 1)) (seq k)) :
    ∀ a, Acc R a → ∀ k, a = seq k → False := by
  intro a ha
  induction ha with
  | intro a _ ih =>
      intro k hk
      subst hk
      exact ih (seq (k + 1)) (h k) (k + 1) rfl

/-- The reverse step relation of the erased system is not well founded. -/
theorem counterErased_not_wf : ¬ WellFounded StepRev := by
  intro hwf
  exact no_acc_of_chain (orbit z z) (fun k => orbit_step z z k) (orbit z z 0)
    (hwf.apply _) 0 rfl

end KO7Benchmark.PaperB.CounterErasure
