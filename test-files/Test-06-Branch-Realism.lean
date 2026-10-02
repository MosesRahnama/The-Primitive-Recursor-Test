namespace BranchRealism

inductive Trace : Type
| void : Trace
| delta : Trace -> Trace
| integrate : Trace -> Trace
| merge : Trace -> Trace -> Trace
| app : Trace -> Trace -> Trace
| recDelta : Trace -> Trace -> Trace -> Trace
| eqW : Trace -> Trace -> Trace

deriving DecidableEq, Repr

open Trace

inductive Step : Trace -> Trace -> Prop
| R_int_delta : forall t, Step (integrate (delta t)) void
| R_merge_void_left : forall t, Step (merge void t) t
| R_merge_void_right : forall t, Step (merge t void) t
| R_merge_cancel : forall t, Step (merge t t) t
| R_rec_zero : forall b s, Step (recDelta b s void) b
| R_rec_succ : forall b s n, Step (recDelta b s (delta n)) (app s (recDelta b s n))
| R_eq_refl : forall a, Step (eqW a a) void
| R_eq_diff : forall a b, Step (eqW a b) (integrate (merge a b))

def kappa : Trace -> Nat
| .void => 0
| .delta t => kappa t
| .integrate t => kappa t
| .merge a b => Nat.max (kappa a) (kappa b)
| .app a b => Nat.max (kappa a) (kappa b)
| .recDelta b s (.delta n) => Nat.max (Nat.max (kappa b) (kappa s)) (kappa n) + 1
| .recDelta b s n => Nat.max (Nat.max (kappa b) (kappa s)) (kappa n)
| .eqW a b => Nat.max (kappa a) (kappa b)

@[simp] lemma kappa_void : kappa void = 0 := rfl
@[simp] lemma kappa_delta (t) : kappa (delta t) = kappa t := rfl
@[simp] lemma kappa_integrate (t) : kappa (integrate t) = kappa t := rfl
@[simp] lemma kappa_merge (a b) : kappa (merge a b) = Nat.max (kappa a) (kappa b) := rfl
@[simp] lemma kappa_app (a b) : kappa (app a b) = Nat.max (kappa a) (kappa b) := rfl
@[simp] lemma kappa_eqW (a b) : kappa (eqW a b) = Nat.max (kappa a) (kappa b) := rfl
@[simp] lemma kappa_rec_delta (b s n) :
  kappa (recDelta b s (delta n)) =
    Nat.max (Nat.max (kappa b) (kappa s)) (kappa n) + 1 := rfl

theorem kappa_rec_delta_step (b s n : Trace) :
  kappa (recDelta b s (delta n)) = kappa (recDelta b s n) + 1 := by
  sorry

theorem kappa_rec_succ_drop (b s n : Trace) :
  kappa (app s (recDelta b s n)) < kappa (recDelta b s (delta n)) := by
  rw [kappa_rec_delta_step]
  sorry

end BranchRealism
