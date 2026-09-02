# Test 07 Lean verification report

Date: 2026-07-26; scoped direct-family facade added and rebuilt 2026-08-02

State: `plain Lean project -> L1 proved -> L2 simplification-order obstruction proved -> strict-Nat-interpretation strengthening proved -> scoped tested-direct-family facade proved -> universal S4 additive obstruction replayed -> no holes`

## Project layout and commands

- Standalone Lake driver: `results/test-07-propagation-fac-tests/verification/lean/`
- Lean sources: `lean/Test07Verification/`
- Toolchain: `leanprover/lean4:v4.22.0-rc4`
- Standalone dependency set: Lean core only, no Mathlib dependency
- Targeted build: `lake build Test07Verification`
- Build exit status: 0
- New facade check: `lake env lean ../../../../lean/Test07Verification/FacDirectMethodObstructions.lean`, exit 0
- Reused S4 citation audit: `lake env lean Test07Verification/SchemaCitationAudit.lean` in the existing benchmark Lean project, exit 0
- Logs: `verification/lean/lean_L1.log`, `lean_L2.log`, `lean_L2_Nat.log`, `lean_build.log`, `lean_schema_citation_audit.log`

No source contains `sorry`, `admit`, `native_decide`, or `sorryAx`.

## New theorem inventory

| Artifact | Exact theorem | Scope | Axioms |
|---|---|---|---|
| L1 | `Test07Verification.AdditiveDuplicationObstruction.every_additive_weight_has_nondecreasing_ag316_instance` | For every natural-valued additive per-symbol assignment, supplies `x = s(0)`, `y = var 0` with RHS weight at least LHS weight for `times(x,s(y)) -> plus(times(x,y),x)` | `propext`, `Quot.sound` |
| L2 | `Test07Verification.FacSimplificationOrderObstruction.no_simplification_order_orients_fac_rule` | Any transitive, irreflexive, proper-subterm, context-monotone strict relation cannot orient the factorial rule | none |
| L2-Nat helper | `strictlyIncreasing_ge_identity` | Every strictly increasing `Nat -> Nat` function is inflationary | none |
| L2-Nat helper | `strictlyIncreasing_monotone` | Strict increase implies weak monotonicity on Nat | none |
| L2-Nat strengthening | `no_strictly_monotone_nat_interpretation_orients_fac_rule` | No Nat interpretation strict in `p`, `fac`, and the first `times` argument can orient the factorial rule, regardless of `s` | none |
| L2 facade | `no_simplification_order_attempt_orients_factorial_rule` | No attempt carrying the four simplification-order laws can orient the factorial rule for all substitutions | none |
| L2 facade | `no_strict_nat_interpretation_attempt_orients_factorial_rule` | No attempt carrying the strict-Nat interpretation interface can orient the factorial rule for all valuations | none |
| L2 facade umbrella | `no_tested_direct_attempt_orients_factorial_rule` | No member of the explicitly represented two-family universe, simplification orders or strict Nat interpretations, can orient the factorial rule | none |

The L2-Nat strengthening was added because the abstract simplification-order theorem should not be misreported as covering a semantic interpretation that lacks the subterm property. It directly closes the strictly monotone Nat polynomial class named in M3.

## Verbatim `#print axioms` output

```text
'Test07Verification.AdditiveDuplicationObstruction.every_additive_weight_has_nondecreasing_ag316_instance' depends on axioms: [propext,
 Quot.sound]
```

```text
'Test07Verification.FacSimplificationOrderObstruction.no_simplification_order_orients_fac_rule' does not depend on any axioms
```

```text
'Test07Verification.StrictMonotoneInterpretationObstruction.strictlyIncreasing_ge_identity' does not depend on any axioms
'Test07Verification.StrictMonotoneInterpretationObstruction.strictlyIncreasing_monotone' does not depend on any axioms
'Test07Verification.StrictMonotoneInterpretationObstruction.no_strictly_monotone_nat_interpretation_orients_fac_rule' does not depend on any axioms
```

```text
'Test07Verification.FacDirectMethodObstructions.no_simplification_order_attempt_orients_factorial_rule' does not depend on any axioms
'Test07Verification.FacDirectMethodObstructions.no_strict_nat_interpretation_attempt_orients_factorial_rule' does not depend on any axioms
'Test07Verification.FacDirectMethodObstructions.no_tested_direct_attempt_orients_factorial_rule' does not depend on any axioms
```

Reused S4 citations were independently imported and audited:

```text
'KO7Benchmark.PaperB.schema_polynomial_not_adequate' does not depend on any axioms
'KO7Benchmark.PaperB.AdditiveSKMeasure.no_additive_orients_schema_recursive_root' depends on axioms: [propext,
 Quot.sound]
'KO7Benchmark.PaperB.AdditiveSKMeasure.no_additive_orients_schema_step' depends on axioms: [propext, Quot.sound]
'KO7Benchmark.SchemaTests.CandidateB.interpB_not_step_orienting' depends on axioms: [propext]
```

## L1 proof content

The weight function assigns natural weights to `zero`, `s`, `plus`, and `times` and sums them over occurrences. Variables contribute zero. For arbitrary weights, instantiate the duplicating rule with `x = s(zero)` and `y = var 0`. Lean proves by associative/commutative normalization that the RHS weight equals the LHS weight plus `w.plus + w.zero`, hence it is never strictly smaller.

This proves exactly the nonnegative additive-symbol-weight obstruction. It does not claim that every linear algebra or every dependency-pair reduction pair fails.

## L2 proof content

For arbitrary `x`, let:

- `lhs = fac(s(x))`
- `rhs = times(fac(p(s(x))), s(x))`

The proper-subterm property gives `p(s(x)) > s(x)` and `rhs > fac(p(s(x)))`. Context monotonicity through `fac` gives `fac(p(s(x))) > lhs`. Transitivity yields `rhs > lhs`; an assumed `lhs > rhs` then violates irreflexivity. The term type has five inductive constructors: four function constructors (`s`, `p`, `fac`, `times`) plus variable leaves.

The separate Nat theorem avoids importing the subterm property: every strictly increasing Nat self-map is inflationary, so `p(s(x)) >= s(x)`, strict `fac` is monotone, and strictness of `times` in its first argument makes the RHS at least the LHS.

## Scoped direct-family facade

`lean/Test07Verification/FacDirectMethodObstructions.lean` packages the two proved obstruction interfaces into an explicit sum type, `TestedDirectAttempt`, and proves that no member orients the factorial rule for all substitutions. Its simplification-order branch applies to LPO, RPO, or KBO only after the concrete relation is shown transitive, irreflexive, proper-subterm extending, and context monotone. Its semantic branch applies to strictly monotone natural-number interpretations, including strictly monotone Nat polynomial interpretations satisfying the displayed interface.

The umbrella is deliberately scoped. It does not represent weak or capped interpretations, matrix interpretations, or any other direct family. Therefore the Lean-backed public wording is "the tested direct families were provably unavailable," not "all direct methods provably fail."

## Reused S4 evidence

- `lean/KO7Benchmark/PaperB/SchemaAdditiveObstruction.lean`: `AdditiveSKMeasure.no_additive_orients_schema_recursive_root` and `AdditiveSKMeasure.no_additive_orients_schema_step`
- `lean/KO7Benchmark/PaperB/BoundaryWitness.lean:47`: `schema_polynomial_not_adequate`
- `lean/KO7Benchmark/SchemaTests/CandidateB_PolynomialCounterexample.lean`: `interpB_not_step_orienting`

All three source files compiled live. The `AdditiveSKMeasure` theorems are the exact universal S4 evidence required by M5: no natural-valued additive constructor-weight measure with positive `G` weight strictly decreases on the recursive root instance or on every contextual `Step`. `schema_polynomial_not_adequate` separately blocks the specified collapsed polynomial witness. `interpB_not_step_orienting` is a specific context-closure counterexample for `[G(a,b)] = b`; it is not reported as a universal polynomial impossibility theorem.

## Per-session claim map

`verification/lean/SESSION_CLAIM_MAP.csv` contains six literal-quote claim rows from four manually read armC responses. Mechanical post-validation confirmed every quote is a contiguous substring of its `response.txt`.

- Five rows are mapped to one or both proved obstruction theorems.
- One row is deliberately flagged `flagged_outside_L2_hypotheses`: its proposed capped predecessor `[p](n)=n-1` is neither a Nat polynomial nor strictly increasing, and the response gives no complete checkable interpretation. The plan explicitly required flagging such scope escapes instead of forcing L2.

## Honesty boundary

- PROVEN-IN-LEAN: the exact L1, L2, and L2-Nat theorem statements above.
- PROVEN-IN-LEAN: the three scoped facade theorems above, over exactly the two constructors of `TestedDirectAttempt`.
- PROVEN-IN-LEAN: the four cited S4 theorem statements, under their exact scopes, including the universal additive root and contextual obstructions.
- Not claimed: TTT2 `MAYBE` proves impossibility.
- Not claimed: L2 rules out weakly monotone or capped semantic interpretations that do not satisfy its hypotheses.
- Not claimed: the facade rules out matrix interpretations or all methods informally called direct.
- Not claimed: the standalone Lean files prove termination of S1-S4. Termination is carried by the CeTA-certified TTT2 artifacts.
