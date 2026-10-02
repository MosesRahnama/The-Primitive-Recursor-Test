namespace CandidateAudit

inductive Trace : Type
| void : Trace
| delta : Trace -> Trace
| integrate : Trace -> Trace
| merge : Trace -> Trace -> Trace
| app : Trace -> Trace -> Trace
| recDelta : Trace -> Trace -> Trace -> Trace
| eqW : Trace -> Trace -> Trace

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

def mu1 : Trace -> Nat
| .void => 0
| .delta t => 1 + mu1 t
| .integrate t => 1 + mu1 t
| .merge a b => 1 + mu1 a + mu1 b
| .app a b => 1 + mu1 a + mu1 b
| .recDelta b s n => 1 + mu1 b + mu1 s + mu1 n
| .eqW a b => 3 + mu1 a + mu1 b

def mu2 : Trace -> Nat
| .void => 0
| .delta t => 1 + mu2 t
| .integrate t => 2 + mu2 t
| .merge a b => 2 + mu2 a + mu2 b
| .app a b => 1 + mu2 a + mu2 b
| .recDelta b s n => 5 + mu2 b + mu2 s + mu2 n
| .eqW a b => 5 + mu2 a + mu2 b

def mu3 : Trace -> Nat
| .void => 0
| .delta t => 1 + mu3 t
| .integrate t => 2 + mu3 t
| .merge a b => 1 + mu3 a + mu3 b
| .app a b => 2 + mu3 a + mu3 b
| .recDelta b s n => 1 + mu3 b + mu3 s + mu3 n
| .eqW a b => 4 + mu3 a + mu3 b

end CandidateAudit
