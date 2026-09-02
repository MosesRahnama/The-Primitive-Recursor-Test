/-!
# Surface-transport witnesses

Core-only Lean 4 transports of two recursive equations frozen from the
Archive of Formal Proofs.  These definitions are deliberately generic in
non-recursive operations because termination depends only on the recursive
List/Nat argument.

No `partial`, `unsafe`, `axiom`, or `sorry` declarations are used.
-/

universe uα uβ uW uG uC uT

namespace SurfaceTransport

/--
Transport of AFP `exec_walk_weight`.

The fixed function parameter `W` occurs both outside and inside the unique
recursive call.  The decreasing parameter is `path`, and the call is made on
the strict list subterm `y :: xs`.
-/
def execWalkWeight
    {α : Type uα} {β : Type uβ}
    [OfNat β 0] [HAdd β β β]
    (W : α → α → β) (path : List α) : β :=
  match path with
  | [] => 0
  | [_] => 0
  | x :: y :: xs => W x y + execWalkWeight W (y :: xs)
termination_by structural path

/--
Transport of AFP `extract_prefix` with its source-level `let` preserved.
The recursive result `memo` is computed once and then used twice.
-/
def extractPrefix
    {Weight : Type uW} {Graph : Type uG}
    {EClass : Type uC} {Term : Type uT}
    (bestEClassTerm : Weight → List Term → EClass → Term)
    (nthEClass : Graph → Nat → EClass)
    (w : Weight) (graph : Graph) (n : Nat) : List Term :=
  match n with
  | 0 => []
  | Nat.succ i =>
      let memo := extractPrefix bestEClassTerm nthEClass w graph i
      memo ++ [bestEClassTerm w memo (nthEClass graph i)]
termination_by structural n

/- The following equation checks are kernel-reduced (`rfl`). -/

@[simp] theorem execWalkWeight_nil
    {α : Type uα} {β : Type uβ}
    [OfNat β 0] [HAdd β β β]
    (W : α → α → β) :
    execWalkWeight W [] = 0 := rfl

@[simp] theorem execWalkWeight_singleton
    {α : Type uα} {β : Type uβ}
    [OfNat β 0] [HAdd β β β]
    (W : α → α → β) (x : α) :
    execWalkWeight W [x] = 0 := rfl

@[simp] theorem execWalkWeight_cons_cons
    {α : Type uα} {β : Type uβ}
    [OfNat β 0] [HAdd β β β]
    (W : α → α → β) (x y : α) (xs : List α) :
    execWalkWeight W (x :: y :: xs) =
      W x y + execWalkWeight W (y :: xs) := rfl

@[simp] theorem extractPrefix_zero
    {Weight : Type uW} {Graph : Type uG}
    {EClass : Type uC} {Term : Type uT}
    (bestEClassTerm : Weight → List Term → EClass → Term)
    (nthEClass : Graph → Nat → EClass)
    (w : Weight) (graph : Graph) :
    extractPrefix bestEClassTerm nthEClass w graph 0 = [] := rfl

@[simp] theorem extractPrefix_succ
    {Weight : Type uW} {Graph : Type uG}
    {EClass : Type uC} {Term : Type uT}
    (bestEClassTerm : Weight → List Term → EClass → Term)
    (nthEClass : Graph → Nat → EClass)
    (w : Weight) (graph : Graph) (i : Nat) :
    extractPrefix bestEClassTerm nthEClass w graph (Nat.succ i) =
      let memo := extractPrefix bestEClassTerm nthEClass w graph i
      memo ++ [bestEClassTerm w memo (nthEClass graph i)] := rfl

end SurfaceTransport
