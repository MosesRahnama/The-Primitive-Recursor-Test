/-
  Polynomial failure patterns for Schema A.

  The successful polynomial witnesses must strictly decrease on the full
  context-closed `Step` relation, not only on the two root rules. These lemmas
  mechanize common ways a candidate polynomial can pass a root-only check while
  failing as a termination witness.
-/
import KO7Benchmark.SchemaTests.SchemaKernel

namespace KO7Benchmark.SchemaTests.PolynomialFailurePatterns

open KO7Benchmark.SchemaTests
open SKTerm

/-- If an interpretation is insensitive to F's payload argument at clock value Z,
then it cannot strictly decrease on every context-closed step. -/
theorem no_f_payload_at_z_collapse_orients_step
    {mu : SKTerm -> Nat}
    (h : ∀ a t u, mu (f a t z) = mu (f a u z)) :
    ¬ (∀ {a b : SKTerm}, Step a b -> mu b < mu a) := by
  intro hstep
  have hroot : Step (f (var 0) (var 0) z) (var 0) :=
    Step.root (RootStep.base (var 0) (var 0))
  have hf :
      Step (f (var 0) (f (var 0) (var 0) z) z) (f (var 0) (var 0) z) :=
    Step.f_arg2 hroot
  have hlt :
      mu (f (var 0) (var 0) z) < mu (f (var 0) (f (var 0) (var 0) z) z) :=
    hstep hf
  rw [h (var 0) (var 0) (f (var 0) (var 0) z)] at hlt
  exact lt_irrefl _ hlt

/-- Function-form version: if at Z the F-clause depends only on its first
argument, root-rule checks do not certify the full TRS. -/
theorem no_f_payload_at_z_function_form_orients_step
    {mu : SKTerm -> Nat} {rho : SKTerm -> Nat}
    (h : ∀ a t, mu (f a t z) = rho a) :
    ¬ (∀ {a b : SKTerm}, Step a b -> mu b < mu a) :=
  no_f_payload_at_z_collapse_orients_step
    (fun a t u => (h a t).trans (h a u).symm)

/-- If G ignores its duplicated left payload, reducing inside that payload is
invisible to the interpretation. -/
theorem no_g_left_payload_function_form_orients_step
    {mu : SKTerm -> Nat} {rho : SKTerm -> Nat}
    (h : ∀ a b, mu (g a b) = rho b) :
    ¬ (∀ {a b : SKTerm}, Step a b -> mu b < mu a) := by
  intro hstep
  have hroot : Step (f (var 0) (var 0) z) (var 0) :=
    Step.root (RootStep.base (var 0) (var 0))
  have hg : Step (g (f (var 0) (var 0) z) z) (g (var 0) z) :=
    Step.g_left hroot
  have hlt : mu (g (var 0) z) < mu (g (f (var 0) (var 0) z) z) := hstep hg
  rw [h (var 0) z, h (f (var 0) (var 0) z) z] at hlt
  exact lt_irrefl _ hlt

/-- If G ignores its recursive-result argument, reducing inside that argument is
invisible to the interpretation. -/
theorem no_g_right_payload_function_form_orients_step
    {mu : SKTerm -> Nat} {rho : SKTerm -> Nat}
    (h : ∀ a b, mu (g a b) = rho a) :
    ¬ (∀ {a b : SKTerm}, Step a b -> mu b < mu a) := by
  intro hstep
  have hroot : Step (f (var 0) (var 0) z) (var 0) :=
    Step.root (RootStep.base (var 0) (var 0))
  have hg : Step (g z (f (var 0) (var 0) z)) (g z (var 0)) :=
    Step.g_right hroot
  have hlt : mu (g z (var 0)) < mu (g z (f (var 0) (var 0) z)) := hstep hg
  rw [h z (var 0), h z (f (var 0) (var 0) z)] at hlt
  exact lt_irrefl _ hlt

end KO7Benchmark.SchemaTests.PolynomialFailurePatterns
