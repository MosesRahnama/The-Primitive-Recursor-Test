/-
  Search-budget invariance at the orientation boundary.

  Mechanizes the benchmark-local content of Rahnama_PRT_Benchmark.tex
  §7 ("why scaling does not move the PRT signature") and the
  representation-shift fracture clause it rests on: a proof search
  confined to the direct-whole and imported-whole witness languages
  produces no contract-admissible witness at any derivation budget,
  while the truth-level witness is already reachable inside the
  confined region. Enlarging the budget therefore changes nothing on
  the admissibility axis; crossing requires a representation lift, not
  more search.

  The companion operational-inexpressibility artifact carries the
  cross-paper form of this statement; this module is the benchmark
  stack's self-contained version over `WitnessOrder`.

  Relation: witness-order bookkeeping over `WLevel`; the KO7 tower's
  populated layers are cited from `WitnessOrder`.
  Property: metadata / admissibility-invariance theorem layer.
  Trust: kernel-only; baseline axioms.
-/
import KO7Benchmark.WitnessOrder
import Mathlib.Tactic

set_option autoImplicit false

namespace KO7Benchmark.PaperB.SearchBudgetInvariance

open KO7Benchmark.WitnessOrder

/-- A budgeted search procedure: the set of witness-language levels it
    has attempted within each derivation budget, monotone in the
    budget. -/
structure BudgetedSearch where
  attempts : Nat → WLevel → Prop
  budget_monotone :
    ∀ {m n : Nat}, m ≤ n → ∀ {ℓ : WLevel}, attempts m ℓ → attempts n ℓ

/-- A search is confined to the direct-whole and imported-whole
    languages when every attempted level at every budget sits at or
    below the imported-whole order. -/
def ConfinedToDirectAndImported (S : BudgetedSearch) : Prop :=
  ∀ (n : Nat) (ℓ : WLevel), S.attempts n ℓ → ℓ.toNat ≤ 1

/-- Contract admissibility requires a representation lift: every level
    the benchmark contract admits sits at or above the transformed-call
    order. -/
theorem admissible_requires_representation_lift :
    ∀ ℓ : WLevel, benchmarkContract.admissible ℓ → 2 ≤ ℓ.toNat := by
  intro ℓ h
  cases ℓ with
  | directWhole => simp [benchmarkContract] at h
  | importedWhole => simp [benchmarkContract] at h
  | transformedCall => decide
  | externalCert => decide

/-- **Search-budget invariance.** A confined search attempts no
    contract-admissible level at any budget. The statement is uniform
    in the budget, so enlarging the derivation budget cannot produce a
    contract-admissible attempt. -/
theorem confined_search_never_admissible (S : BudgetedSearch)
    (hS : ConfinedToDirectAndImported S) :
    ∀ (n : Nat) (ℓ : WLevel), S.attempts n ℓ →
      ¬ benchmarkContract.admissible ℓ := by
  intro n ℓ hAtt hAdm
  have h1 := hS n ℓ hAtt
  have h2 := admissible_requires_representation_lift ℓ hAdm
  omega

/-- **Truth without admissibility under confinement.** The KO7 tower
    carries a truth-level witness inside the confined region (the
    imported-whole layer), while a confined search attempts no
    admissible level at any budget. The two coordinates are therefore
    independent: budget growth can reach truth and still never reach
    admissibility. -/
theorem confined_truth_without_admissibility (S : BudgetedSearch)
    (hS : ConfinedToDirectAndImported S) :
    HasWitness ko7Tower WLevel.importedWhole ∧
      ∀ (n : Nat) (ℓ : WLevel), S.attempts n ℓ →
        ¬ benchmarkContract.admissible ℓ :=
  ⟨ko7_has_importedWhole_witness, confined_search_never_admissible S hS⟩

/-- Crossing the boundary is a level event, not a budget event: any
    contract witness for the KO7 tower sits at the transformed-call
    order or above, outside every confined search's attempt set. -/
theorem contract_witness_outside_confined_attempts (S : BudgetedSearch)
    (hS : ConfinedToDirectAndImported S)
    {ℓ : WLevel} (hAdm : benchmarkContract.admissible ℓ) :
    ∀ n : Nat, ¬ S.attempts n ℓ := by
  intro n hAtt
  exact confined_search_never_admissible S hS n ℓ hAtt hAdm

/-! ## Non-vacuity witness (release-gate R5) -/

/-- A concrete confined search: at every budget it attempts exactly the
    direct-whole and imported-whole languages. -/
def exampleConfinedSearch : BudgetedSearch where
  attempts := fun _ ℓ => ℓ = .directWhole ∨ ℓ = .importedWhole
  budget_monotone := by intros; assumption

theorem exampleConfinedSearch_confined :
    ConfinedToDirectAndImported exampleConfinedSearch := by
  intro n ℓ h
  rcases h with rfl | rfl <;> decide

/-- The example search attempts the imported-whole level at every
    budget, so the confinement hypothesis is not vacuous. -/
theorem exampleConfinedSearch_attempts_importedWhole (n : Nat) :
    exampleConfinedSearch.attempts n WLevel.importedWhole :=
  Or.inr rfl

end KO7Benchmark.PaperB.SearchBudgetInvariance
