 /-
   Candidate (A): LPO/RPO-style path order with chosen precedence F > G > S > Z.

   Status: SUCCEEDS as an imported precedence-based method.

   This benchmark file does not mechanize a full generic LPO/RPO library.
   Instead it records the exact local rule-shape obligations behind the
   candidate-A argument and closes the overall success status with the
   benchmark-local strong-normalization witness already proved in
   `NonlinearWitness.lean`.

   That is enough for the Test 12 answer key: candidate (A) is a genuine
   yes-side method, but its proof apparatus is globally imported and therefore
   boundary-external.
 -/
 import Mathlib.Tactic
 import KO7Benchmark.SchemaTests.SchemaKernel
 import KO7Benchmark.SchemaTests.NonlinearWitness
 
 namespace KO7Benchmark.SchemaTests.CandidateA
 
 open KO7Benchmark.SchemaTests
 open SKTerm
 
 /-- The precedence declared by candidate (A). -/
 inductive PrecSym where
   | var | z | s | g | f
 deriving DecidableEq, Repr
 
 /-- Root symbol of a schema-kernel term. -/
 def rootSym : SKTerm → PrecSym
   | var _ => PrecSym.var
   | z => PrecSym.z
   | s _ => PrecSym.s
   | g _ _ => PrecSym.g
   | f _ _ _ => PrecSym.f
 
 /-- Numeric encoding of the chosen precedence F > G > S > Z > var. -/
 def precRank : PrecSym → Nat
   | PrecSym.var => 0
   | PrecSym.z => 1
   | PrecSym.s => 2
   | PrecSym.g => 3
   | PrecSym.f => 4
 
 @[simp] theorem rootSym_var (n : Nat) : rootSym (var n) = PrecSym.var := rfl
 @[simp] theorem rootSym_z : rootSym z = PrecSym.z := rfl
 @[simp] theorem rootSym_s (t : SKTerm) : rootSym (s t) = PrecSym.s := rfl
 @[simp] theorem rootSym_g (a b : SKTerm) : rootSym (g a b) = PrecSym.g := rfl
 @[simp] theorem rootSym_f (x y n : SKTerm) : rootSym (f x y n) = PrecSym.f := rfl
 
 @[simp] theorem prec_F_gt_G : precRank PrecSym.g < precRank PrecSym.f := by decide
 @[simp] theorem prec_G_gt_S : precRank PrecSym.s < precRank PrecSym.g := by decide
 @[simp] theorem prec_S_gt_Z : precRank PrecSym.z < precRank PrecSym.s := by decide
 @[simp] theorem prec_Z_gt_var : precRank PrecSym.var < precRank PrecSym.z := by decide
 
 /-- Benchmark-local imported witness used to close the success status of (A). -/
 abbrev stepWitness : SKTerm → Nat := NonlinearWitness.muW
 
 /-- The base rule satisfies the usual subterm-style obligation behind (A). -/
 theorem candidateA_root_base_supported (x y : SKTerm) :
     stepWitness x < stepWitness (f x y z) := by
   simpa [stepWitness] using NonlinearWitness.muW_root_base x y
 
 /-- The recursive call is strictly smaller on the third argument. -/
theorem candidateA_recursive_call_smaller (x y n : SKTerm) :
    stepWitness (f x y n) < stepWitness (f x y (s n)) := by
  simp [stepWitness, NonlinearWitness.muW]

/-- The chosen precedence explicitly places `F` above `G`, matching the
candidate-A fixture. -/
theorem candidateA_declares_F_over_G (x y n : SKTerm) :
    precRank (rootSym (g y (f x y n))) < precRank (rootSym (f x y (s n))) := by
  simp [precRank, rootSym]

/-- The recursive rule satisfies the local comparison used in the usual
path-order argument for candidate (A). -/
theorem candidateA_root_succ_supported (x y n : SKTerm) :
     stepWitness (g y (f x y n)) < stepWitness (f x y (s n)) := by
   simpa [stepWitness] using NonlinearWitness.muW_root_succ x y n
 
 /-- Re-export of the full context-closed strong-normalization witness so that
 candidate (A) is closed locally inside the benchmark project. -/
 abbrev StepRev : SKTerm → SKTerm → Prop := NonlinearWitness.StepRev
 
 theorem candidateA_success_status : WellFounded StepRev := by
   exact NonlinearWitness.wf_StepRev
 
 end KO7Benchmark.SchemaTests.CandidateA

