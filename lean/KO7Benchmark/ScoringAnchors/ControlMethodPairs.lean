/-
  Exact two-system control pairs for scorer-side necessary conditions.

  Relation: the duplicating `SchemaTests.RootStep` / contextual `Step`
    system and the copy-removed `SANSTests.RootStep` / contextual `Step`
    system, using their actual term signatures and recursive rule templates.
  Closure: variable-occurrence, depth, max, and head-rank statements are
    root-rule conditions; full contextual `Step` appears only in the final
    strong-normalization control.
  Property: variable-occurrence nonincrease fails on the schema recursive
    rule but holds on SANS; ordinary depth and constructor-offset maximum
    families fail on both systems; the raw recursive head-rank route requires
    `F > G` on both systems. These are exact necessary-condition or direct
    measure statements, not proxy definitions of KBO, LPO, RPO, or another
    named termination method.
  Trust: Mathlib and existing benchmark source modules only; no sorry,
    admit, new axiom, native_decide, unsafe, partial, or opaque declaration.
-/
import Mathlib.Tactic
import KO7Benchmark.SchemaTests.CandidateC_KBOFailure
import KO7Benchmark.SchemaTests.CandidateA_PathOrderSupport
import KO7Benchmark.SchemaTests.NonlinearWitness
import KO7Benchmark.SANSTests.KBOStyleSupport
import KO7Benchmark.SANSTests.PathOrderSupport
import KO7Benchmark.SANSTests.LinearWitness

set_option autoImplicit false

namespace KO7Benchmark.ScoringAnchors.ControlMethodPairs

/-! ## 1. Structural pair: variable-occurrence nonincrease -/

namespace VariableOccurrence

/-- The method-independent variable-occurrence condition on the schema
recursive rule template. It is only a necessary-condition predicate. -/
def SchemaRecursiveNonincrease : Prop :=
  ∀ v : Nat,
    KO7Benchmark.SchemaTests.CandidateC.countVar v
        KO7Benchmark.SchemaTests.CandidateC.succRhs ≤
      KO7Benchmark.SchemaTests.CandidateC.countVar v
        KO7Benchmark.SchemaTests.CandidateC.succLhs

/-- The same method-independent condition on the actual SANS recursive
rule template. -/
def SANSRecursiveNonincrease : Prop :=
  ∀ v : Nat,
    KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.succRhs ≤
      KO7Benchmark.SANSTests.KBOStyleSupport.countVar v
        KO7Benchmark.SANSTests.KBOStyleSupport.succLhs

/-- On the schema, the copied payload variable occurs once on the source
and twice on the target. -/
theorem schema_payload_count_grows :
    KO7Benchmark.SchemaTests.CandidateC.countVar 1
        KO7Benchmark.SchemaTests.CandidateC.succLhs = 1 ∧
      KO7Benchmark.SchemaTests.CandidateC.countVar 1
        KO7Benchmark.SchemaTests.CandidateC.succRhs = 2 :=
  ⟨KO7Benchmark.SchemaTests.CandidateC.countVar_succLhs_y,
    KO7Benchmark.SchemaTests.CandidateC.countVar_succRhs_y⟩

/-- On SANS, the corresponding payload variable occurs once on each side. -/
theorem sans_payload_count_preserved :
    KO7Benchmark.SANSTests.KBOStyleSupport.countVar 1
        KO7Benchmark.SANSTests.KBOStyleSupport.succLhs = 1 ∧
      KO7Benchmark.SANSTests.KBOStyleSupport.countVar 1
        KO7Benchmark.SANSTests.KBOStyleSupport.succRhs = 1 := by
  constructor <;> rfl

/-- The variable-occurrence condition is impossible on the schema recursive
rule. No named ordering relation is asserted here. -/
theorem schema_recursive_nonincrease_fails :
    ¬ SchemaRecursiveNonincrease := by
  intro h
  have hbad := h 1
  rw [KO7Benchmark.SchemaTests.CandidateC.countVar_succRhs_y,
    KO7Benchmark.SchemaTests.CandidateC.countVar_succLhs_y] at hbad
  exact (by decide : ¬ (2 : Nat) ≤ 1) hbad

/-- The same condition holds on the real SANS recursive rule template. -/
theorem sans_recursive_nonincrease_holds :
    SANSRecursiveNonincrease :=
  KO7Benchmark.SANSTests.KBOStyleSupport.variable_condition_succ

/-- Exact two-system structural control: the occurrence-count obstruction is
schema-only and must not be transferred to SANS. -/
theorem structural_control_pair :
    (¬ SchemaRecursiveNonincrease) ∧ SANSRecursiveNonincrease :=
  ⟨schema_recursive_nonincrease_fails, sans_recursive_nonincrease_holds⟩

end VariableOccurrence

/-! ## 2. Depth pair: copy removal does not rescue ordinary tree depth -/

namespace Depth

open KO7Benchmark.SchemaTests
open KO7Benchmark.SANSTests

/-- Ordinary constructor depth on the duplicating schema syntax. -/
def schemaDepth : KO7Benchmark.SchemaTests.SKTerm → Nat
  | .var _ => 1
  | .z => 1
  | .s t => schemaDepth t + 1
  | .g a b => max (schemaDepth a) (schemaDepth b) + 1
  | .f x y n => max (schemaDepth x) (max (schemaDepth y) (schemaDepth n)) + 1

/-- Ordinary constructor depth on the unary-G SANS syntax. -/
def sansDepth : KO7Benchmark.SANSTests.SANSTerm → Nat
  | .var _ => 1
  | .z => 1
  | .s t => sansDepth t + 1
  | .g t => sansDepth t + 1
  | .f x y n => max (sansDepth x) (max (sansDepth y) (sansDepth n)) + 1

def SchemaRootOrients : Prop :=
  ∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
    KO7Benchmark.SchemaTests.RootStep a b → schemaDepth b < schemaDepth a

def SANSRootOrients : Prop :=
  ∀ {a b : KO7Benchmark.SANSTests.SANSTerm},
    KO7Benchmark.SANSTests.RootStep a b → sansDepth b < sansDepth a

/-- Closed schema instance: ordinary depth rises from three to four. -/
theorem schema_depth_ground_counterexample :
    KO7Benchmark.SchemaTests.RootStep
        (.f .z (.s .z) (.s .z))
        (.g (.s .z) (.f .z (.s .z) .z)) ∧
      schemaDepth (.f .z (.s .z) (.s .z)) = 3 ∧
      schemaDepth (.g (.s .z) (.f .z (.s .z) .z)) = 4 := by
  exact ⟨KO7Benchmark.SchemaTests.RootStep.succ .z (.s .z) .z, rfl, rfl⟩

/-- Closed SANS instance: ordinary depth also rises from three to four. -/
theorem sans_depth_ground_counterexample :
    KO7Benchmark.SANSTests.RootStep
        (.f .z (.s .z) (.s .z))
        (.g (.f .z (.s .z) .z)) ∧
      sansDepth (.f .z (.s .z) (.s .z)) = 3 ∧
      sansDepth (.g (.f .z (.s .z) .z)) = 4 := by
  exact ⟨KO7Benchmark.SANSTests.RootStep.succ .z (.s .z) .z, rfl, rfl⟩

theorem schema_depth_not_root_orienting :
    ¬ SchemaRootOrients := by
  intro h
  have hlt := h
    (KO7Benchmark.SchemaTests.RootStep.succ
      KO7Benchmark.SchemaTests.SKTerm.z
      (KO7Benchmark.SchemaTests.SKTerm.s KO7Benchmark.SchemaTests.SKTerm.z)
      KO7Benchmark.SchemaTests.SKTerm.z)
  change (4 : Nat) < 3 at hlt
  exact (by decide : ¬ (4 : Nat) < 3) hlt

theorem sans_depth_not_root_orienting :
    ¬ SANSRootOrients := by
  intro h
  have hlt := h
    (KO7Benchmark.SANSTests.RootStep.succ
      KO7Benchmark.SANSTests.SANSTerm.z
      (KO7Benchmark.SANSTests.SANSTerm.s KO7Benchmark.SANSTests.SANSTerm.z)
      KO7Benchmark.SANSTests.SANSTerm.z)
  change (4 : Nat) < 3 at hlt
  exact (by decide : ¬ (4 : Nat) < 3) hlt

/-- Exact two-system depth control: this barrier survives copy removal. -/
theorem depth_control_pair :
    (¬ SchemaRootOrients) ∧ (¬ SANSRootOrients) :=
  ⟨schema_depth_not_root_orienting, sans_depth_not_root_orienting⟩

end Depth

/-! ## 3. Maximum family pair: constructor-offset max fails on both -/

namespace Maximum

/-- Constructor-offset maximum interpretation on the schema signature. -/
structure SchemaMax where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace SchemaMax

def eval (M : SchemaMax) : KO7Benchmark.SchemaTests.SKTerm → Nat
  | .var _ => M.wVar
  | .z => M.wZ
  | .s t => M.wS + M.eval t
  | .g a b => M.wG + max (M.eval a) (M.eval b)
  | .f x y n => M.wF + max (M.eval x) (max (M.eval y) (M.eval n))

def OrientsRoot (M : SchemaMax) : Prop :=
  ∀ {a b : KO7Benchmark.SchemaTests.SKTerm},
    KO7Benchmark.SchemaTests.RootStep a b → M.eval b < M.eval a

def standard : SchemaMax := ⟨1, 1, 1, 1, 1⟩

theorem recursive_call_ties_source (M : SchemaMax) :
    M.eval (.f .z (.s .z) .z) =
      M.eval (.f .z (.s .z) (.s .z)) := by
  simp [eval]

theorem recursive_source_le_target (M : SchemaMax) :
    M.eval (.f .z (.s .z) (.s .z)) ≤
      M.eval (.g (.s .z) (.f .z (.s .z) .z)) := by
  rw [← recursive_call_ties_source M]
  have hmax :
      M.eval (.f .z (.s .z) .z) ≤
        max (M.eval (.s .z)) (M.eval (.f .z (.s .z) .z)) :=
    le_max_right _ _
  simp only [eval]
  omega

theorem no_member_orients_recursive_rule (M : SchemaMax) :
    ¬ (∀ x y n : KO7Benchmark.SchemaTests.SKTerm,
      M.eval (.g y (.f x y n)) < M.eval (.f x y (.s n))) := by
  intro h
  have hlt := h .z (.s .z) .z
  have hle := recursive_source_le_target M
  omega

theorem no_member_orients_root (M : SchemaMax) :
    ¬ M.OrientsRoot := by
  intro h
  apply no_member_orients_recursive_rule M
  intro x y n
  exact h (KO7Benchmark.SchemaTests.RootStep.succ x y n)

end SchemaMax

/-- Constructor-offset maximum interpretation on the real SANS signature. -/
structure SANSMax where
  wVar : Nat
  wZ : Nat
  wS : Nat
  wG : Nat
  wF : Nat

namespace SANSMax

def eval (M : SANSMax) : KO7Benchmark.SANSTests.SANSTerm → Nat
  | .var _ => M.wVar
  | .z => M.wZ
  | .s t => M.wS + M.eval t
  | .g t => M.wG + M.eval t
  | .f x y n => M.wF + max (M.eval x) (max (M.eval y) (M.eval n))

def OrientsRoot (M : SANSMax) : Prop :=
  ∀ {a b : KO7Benchmark.SANSTests.SANSTerm},
    KO7Benchmark.SANSTests.RootStep a b → M.eval b < M.eval a

def standard : SANSMax := ⟨1, 1, 1, 1, 1⟩

theorem recursive_call_ties_source (M : SANSMax) :
    M.eval (.f .z (.s .z) .z) =
      M.eval (.f .z (.s .z) (.s .z)) := by
  simp [eval]

theorem recursive_source_le_target (M : SANSMax) :
    M.eval (.f .z (.s .z) (.s .z)) ≤
      M.eval (.g (.f .z (.s .z) .z)) := by
  rw [← recursive_call_ties_source M]
  simp only [eval]
  omega

theorem no_member_orients_recursive_rule (M : SANSMax) :
    ¬ (∀ x y n : KO7Benchmark.SANSTests.SANSTerm,
      M.eval (.g (.f x y n)) < M.eval (.f x y (.s n))) := by
  intro h
  have hlt := h .z (.s .z) .z
  have hle := recursive_source_le_target M
  omega

theorem no_member_orients_root (M : SANSMax) :
    ¬ M.OrientsRoot := by
  intro h
  apply no_member_orients_recursive_rule M
  intro x y n
  exact h (KO7Benchmark.SANSTests.RootStep.succ x y n)

end SANSMax

/-- Both families are concretely inhabited, so the paired emptiness theorem
below is not vacuous. -/
theorem max_families_inhabited :
    (∃ M : SchemaMax, M = SchemaMax.standard) ∧
      (∃ M : SANSMax, M = SANSMax.standard) :=
  ⟨⟨SchemaMax.standard, rfl⟩, ⟨SANSMax.standard, rfl⟩⟩

/-- Exact family-level pair: no constructor-offset max member orients all root
rules on either system. This obstruction is not duplication-specific. -/
theorem max_family_control_pair :
    (¬ ∃ M : SchemaMax, M.OrientsRoot) ∧
      (¬ ∃ M : SANSMax, M.OrientsRoot) := by
  constructor
  · rintro ⟨M, h⟩
    exact SchemaMax.no_member_orients_root M h
  · rintro ⟨M, h⟩
    exact SANSMax.no_member_orients_root M h

end Maximum

/-! ## 4. Head-rank pair: the raw recursive root route needs F > G in both -/

namespace HeadRank

/-- This is only a root-symbol ranking condition for the schema recursive
rule. It is not a definition of a path order. -/
def SchemaRecursiveHeadStrict
    (rank : KO7Benchmark.SchemaTests.CandidateA.PrecSym → Nat) : Prop :=
  ∀ x y n : KO7Benchmark.SchemaTests.SKTerm,
    rank
        (KO7Benchmark.SchemaTests.CandidateA.rootSym
          (.g y (.f x y n))) <
      rank
        (KO7Benchmark.SchemaTests.CandidateA.rootSym
          (.f x y (.s n)))

/-- The same root-symbol ranking condition on the actual SANS recursive rule. -/
def SANSRecursiveHeadStrict
    (rank : KO7Benchmark.SANSTests.PathOrderSupport.PrecSym → Nat) : Prop :=
  ∀ x y n : KO7Benchmark.SANSTests.SANSTerm,
    rank
        (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
          (.g (.f x y n))) <
      rank
        (KO7Benchmark.SANSTests.PathOrderSupport.rootSym
          (.f x y (.s n)))

theorem schema_recursive_head_strict_iff_F_gt_G
    (rank : KO7Benchmark.SchemaTests.CandidateA.PrecSym → Nat) :
    SchemaRecursiveHeadStrict rank ↔
      rank KO7Benchmark.SchemaTests.CandidateA.PrecSym.g <
        rank KO7Benchmark.SchemaTests.CandidateA.PrecSym.f := by
  constructor
  · intro h
    simpa [SchemaRecursiveHeadStrict,
      KO7Benchmark.SchemaTests.CandidateA.rootSym] using
      h KO7Benchmark.SchemaTests.SKTerm.z
        KO7Benchmark.SchemaTests.SKTerm.z
        KO7Benchmark.SchemaTests.SKTerm.z
  · intro h x y n
    simpa [KO7Benchmark.SchemaTests.CandidateA.rootSym] using h

theorem sans_recursive_head_strict_iff_F_gt_G
    (rank : KO7Benchmark.SANSTests.PathOrderSupport.PrecSym → Nat) :
    SANSRecursiveHeadStrict rank ↔
      rank KO7Benchmark.SANSTests.PathOrderSupport.PrecSym.g <
        rank KO7Benchmark.SANSTests.PathOrderSupport.PrecSym.f := by
  constructor
  · intro h
    simpa [SANSRecursiveHeadStrict,
      KO7Benchmark.SANSTests.PathOrderSupport.rootSym] using
      h KO7Benchmark.SANSTests.SANSTerm.z
        KO7Benchmark.SANSTests.SANSTerm.z
        KO7Benchmark.SANSTests.SANSTerm.z
  · intro h x y n
    simpa [KO7Benchmark.SANSTests.PathOrderSupport.rootSym] using h

/-- The required head-rank condition is inhabited on the schema syntax. -/
theorem schema_head_condition_nonvacuous :
    SchemaRecursiveHeadStrict
      KO7Benchmark.SchemaTests.CandidateA.precRank :=
  KO7Benchmark.SchemaTests.CandidateA.candidateA_declares_F_over_G

/-- The same required condition is inhabited on the SANS syntax. -/
theorem sans_head_condition_nonvacuous :
    SANSRecursiveHeadStrict
      KO7Benchmark.SANSTests.PathOrderSupport.precRank :=
  KO7Benchmark.SANSTests.PathOrderSupport.declares_F_over_G

/-- Exact two-system head-rank control: copy removal does not change the
necessary `F > G` comparison for a proof route that relies on the two root
symbols alone. -/
theorem head_rank_control_pair :
    SchemaRecursiveHeadStrict
        KO7Benchmark.SchemaTests.CandidateA.precRank ∧
      SANSRecursiveHeadStrict
        KO7Benchmark.SANSTests.PathOrderSupport.precRank :=
  ⟨schema_head_condition_nonvacuous, sans_head_condition_nonvacuous⟩

end HeadRank

/-! ## 5. Termination control -/

/-- Failure of the depth/max families is not a nontermination result.
Both exact contextual systems are strongly normalizing by independent
whole-system witnesses. -/
theorem both_contextual_systems_wellFounded :
    WellFounded KO7Benchmark.SchemaTests.NonlinearWitness.StepRev ∧
      WellFounded KO7Benchmark.SANSTests.LinearWitness.StepRev :=
  ⟨KO7Benchmark.SchemaTests.NonlinearWitness.wf_StepRev,
    KO7Benchmark.SANSTests.LinearWitness.wf_StepRev⟩

/-- Compact scorer receipt for the four transfer decisions in this module. -/
theorem transfer_classification :
    ((¬ VariableOccurrence.SchemaRecursiveNonincrease) ∧
      VariableOccurrence.SANSRecursiveNonincrease) ∧
    ((¬ Depth.SchemaRootOrients) ∧ (¬ Depth.SANSRootOrients)) ∧
    ((¬ ∃ M : Maximum.SchemaMax, M.OrientsRoot) ∧
      (¬ ∃ M : Maximum.SANSMax, M.OrientsRoot)) ∧
    (HeadRank.SchemaRecursiveHeadStrict
        KO7Benchmark.SchemaTests.CandidateA.precRank ∧
      HeadRank.SANSRecursiveHeadStrict
        KO7Benchmark.SANSTests.PathOrderSupport.precRank) :=
  ⟨VariableOccurrence.structural_control_pair,
    Depth.depth_control_pair,
    Maximum.max_family_control_pair,
    HeadRank.head_rank_control_pair⟩

end KO7Benchmark.ScoringAnchors.ControlMethodPairs
