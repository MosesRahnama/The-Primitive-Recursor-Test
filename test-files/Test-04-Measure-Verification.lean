namespace TermProof

inductive Trace : Type
| void : Trace
| delta : Trace → Trace
| integrate : Trace → Trace
| merge : Trace → Trace → Trace
| app : Trace → Trace → Trace
| recDelta : Trace → Trace → Trace → Trace
| eqW : Trace → Trace → Trace
open Trace

inductive Step : Trace → Trace → Prop
| R_int_delta    : ∀ t,     Step (integrate (delta t)) void
| R_merge_void_left  : ∀ t, Step (merge void t) t
| R_merge_void_right : ∀ t, Step (merge t void) t
| R_merge_cancel : ∀ t,     Step (merge t t) t
| R_rec_zero     : ∀ b s,   Step (recDelta b s void) b
| R_rec_succ     : ∀ b s n, Step (recDelta b s (delta n)) (app s (recDelta b s n))
| R_eq_refl      : ∀ a,     Step (eqW a a) void
| R_eq_diff      : ∀ a b,   Step (eqW a b) (integrate (merge a b))

def phase : Trace → Nat
| .recDelta _ _ (.delta _) => 1
| _ => 0

def cost : Trace → Nat
| .void            => 0
| .delta t         => 1 + cost t
| .integrate t     => 1 + cost t
| .merge a b       => 1 + cost a + cost b
| .app a b         => 1 + cost a + cost b
| .recDelta b s n  => 1 + cost b + cost s + cost n
| .eqW a b         => 3 + cost a + cost b

def measure (t : Trace) : Nat × Nat := (phase t, cost t)

end TermProof
