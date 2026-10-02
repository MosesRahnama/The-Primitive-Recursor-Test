# TGC v3 construction registry — Schema Test A

Choose the mathematical object the response actually supplies. Copy its generated template; do not reconstruct a claim object from memory.

| kind | source cue | transform adapter | field-evidence unit | template |
|---|---|---|---|---|
| `additive_measure` | one numeric quantity on whole terms claimed to decrease (named standard measure or a map) | `polynomial_definitions_v3` | `definition_entries` | `templates/additive_measure.json` |
| `call_measure` | a measure tracking an argument of the recursive symbol (type it via the CONVERSION DICTIONARY) | `generic_v3` | `top_level` | `templates/call_measure.json` |
| `counter_projection` | the counter-argument projection (argument of the recursive symbol that counts down) | `generic_v3` | `top_level` | `templates/counter_projection.json` |
| `dp_projection` | dependency pairs / subterm criterion projecting a named argument across recursive calls | `generic_v3` | `top_level` | `templates/dp_projection.json` |
| `global_multiset_measure` | a multiset over ALL subterms compared in the multiset extension | `generic_v3` | `top_level` | `templates/global_multiset_measure.json` |
| `kbo_weights` | a Knuth-Bendix order: symbol weights, optional precedence | `generic_v3` | `top_level` | `templates/kbo_weights.json` |
| `lex_tuple` | an ORDERED tuple of component measures compared lexicographically (one object, never split) | `generic_v3` | `top_level` | `templates/lex_tuple.json` |
| `lpo` | a lexicographic path order given by a precedence (named LPO only) | `path_order_v3` | `top_level` | `templates/lpo.json` |
| `other_unparseable` | a stated termination-proof construction no other kind can carry (LAST resort) | `generic_v3` | `top_level` | `templates/other_unparseable.json` |
| `phased_measure` | a phased/composite argument: one quantity strictly decreases, residual subsystem terminates between | `generic_v3` | `top_level` | `templates/phased_measure.json` |
| `poly_interpretation` | a polynomial/numeric interpretation assigning an expression to signature symbols | `polynomial_definitions_v3` | `definition_entries` | `templates/poly_interpretation.json` |
| `recursive_aux_measure` | an auxiliary function DEFINED by recursion on term syntax (delta count, reduction height) | `generic_v3` | `top_level` | `templates/recursive_aux_measure.json` |
| `root_control_proof` | root-step control/case analysis: every step yields a proper subterm or an immediately-normal root | `generic_v3` | `top_level` | `templates/root_control_proof.json` |
| `rpo` | a recursive path order / LPO-RPO alias phrase given by a precedence, optional status | `path_order_v3` | `top_level` | `templates/rpo.json` |
| `size_change` | size-change termination / SCT graph argument | `generic_v3` | `top_level` | `templates/size_change.json` |
| `structural_induction_untyped` | structural/accessibility induction claimed WITHOUT a separate measure object | `generic_v3` | `top_level` | `templates/structural_induction_untyped.json` |
