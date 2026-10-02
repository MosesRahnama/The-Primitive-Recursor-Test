# Deterministic transformation registry

Agents preserve source notation. Only the following versioned adapters may transform a transcription. Unsupported input remains visible and checker-unknown.

| kind | adapter | checker route | concrete requirements |
|---|---|---|---|
| `additive_measure` | `polynomial_definitions_v3` | `legacy_adapter` | registry any-of / none |
| `call_measure` | `generic_v3` | `legacy_adapter` | scope |
| `counter_projection` | `generic_v3` | `legacy_adapter` | argument |
| `dp_projection` | `generic_v3` | `legacy_adapter` | argument |
| `global_multiset_measure` | `generic_v3` | `legacy_adapter` | scope, element_measure, order |
| `kbo_weights` | `generic_v3` | `legacy_adapter` | weights, variant |
| `lex_tuple` | `generic_v3` | `legacy_adapter` | components |
| `lpo` | `path_order_v3` | `legacy_adapter` | precedence, precedence_quantifier |
| `other_unparseable` | `generic_v3` | `unsupported` | registry any-of / none |
| `phased_measure` | `generic_v3` | `legacy_adapter` | phases, composition |
| `poly_interpretation` | `polynomial_definitions_v3` | `legacy_adapter` | definitions |
| `recursive_aux_measure` | `generic_v3` | `legacy_adapter` | auxiliary, recursion_on |
| `root_control_proof` | `generic_v3` | `legacy_adapter` | relation, principle |
| `rpo` | `path_order_v3` | `legacy_adapter` | precedence, precedence_quantifier |
| `size_change` | `generic_v3` | `legacy_adapter` | argument |
| `structural_induction_untyped` | `generic_v3` | `legacy_adapter` | registry any-of / none |

`polynomial_definitions_v3` validates source-order definition blocks, signature membership, exact arity, unique source parameters, and the closed nonnegative `+`/`*` grammar before alpha-renaming.

`path_order_v3` parses only a closed precedence grammar, rejects unknown symbols/cycles, and preserves status plus explicit argument-comparison order in mathematical identity.

`generic_v3` performs only deterministic JSON/whitespace normalization and never invents an enum or missing field.
