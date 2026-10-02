"""Ground counterexamples to an explicitly universal precedence constraint."""

import re
from itertools import permutations, product

from .canonical import canonical_status, fold_glyph_tokens, fold_presentation
from .native_math import _lpo_rule_table, render_term
from .proof_obligations import _parsed_rules, _substitute, _variables
from .structural_premises import _replay_step, _step


def omitted_source_status(claim):
    """Do not certify default lex when a retained quote specifies another status."""
    mode = claim.get("mathematical_core", {}).get("payload", {}).get("status", {}).get("mode", "unspecified")
    for anchors in claim.get("evidence_by_pass", {}).values():
        for anchor in anchors if isinstance(anchors, list) else []:
            text = re.sub(r"\s+", " ", fold_presentation(anchor.get("text", ""), markdown_emphasis=True)).lower()
            if re.search(r"lexicographically from right to left", text) and mode != "reverse":
                return "source_reverse_status_not_transcribed"
            if re.search(r"comparing the multiset of arguments", text) and mode != "multiset":
                return "source_multiset_status_not_transcribed"
    return None


def quoted_universal_precedence(claim, contract):
    payload = claim.get("transcription", {})
    if (claim.get("kind") not in {"rpo", "lpo"} or claim.get("specificity") != "concrete"
            or set(payload) != {"precedence", "precedence_quantifier", "status"}
            or payload["precedence_quantifier"] != "forall_total_extensions"):
        return None
    status = canonical_status(payload["status"])
    if status.get("mode") != "lex" or status.get("argument_order") is not None:
        return None
    text = re.sub(r"\s+", " ", fold_glyph_tokens(
        fold_presentation(payload["precedence"], markdown_emphasis=True), contract.glyph_folds)).strip()
    match = re.fullmatch(
        r"puts ([A-Za-z][A-Za-z0-9_]*) strictly above ([A-Za-z][A-Za-z0-9_]*) "
        r"and that puts every proper constructor above ([A-Za-z][A-Za-z0-9_]*)", text)
    if not match or not set(match.groups()) <= set(contract.signature):
        return None
    higher, lower, zero = match.groups()
    # With a single constant, the positive-arity constructors are exactly the
    # signature minus that constant. No arbitrary constructor subset is inferred.
    if [s for s, p in contract.signature.items() if not p] != [zero] or higher == lower:
        return None
    unary = sorted(s for s, p in contract.signature.items() if len(p) == 1)
    if not unary or len(contract.signature) > 7:
        return None
    seed = zero, ()
    terms = [seed, (unary[0], (seed,))]
    constraints = {(higher, lower)} | {(s, zero) for s in contract.signature if s != zero}
    parsed = _parsed_rules(contract.rules, contract.signature)
    for order in permutations(sorted(contract.signature)):
        edges = {(a, b) for i, a in enumerate(order) for b in order[i+1:]}
        if not constraints <= edges:
            continue
        for rule, lhs, rhs in parsed:
            if set(rule) - {"name", "lhs", "rhs"}:
                continue
            variables = sorted(_variables(lhs, contract.signature))
            if len(variables) > 3:
                continue
            for values in product(terms, repeat=len(variables)):
                substitution = dict(zip(variables, values))
                source = _substitute(lhs, substitution)
                step = _step(rule, lhs, rhs, substitution, source, [])
                left, right = _replay_step(step, parsed, contract.signature)
                # The fruit surface restricts eq_diff. Record only witnesses
                # satisfying that guard, even on the unguarded source contract.
                guard = None
                if rule["name"] == "eq_diff":
                    if (lhs != ("eqW", (("a", ()), ("b", ())))
                            or rhs != ("integrate", (("merge", (("a", ()), ("b", ()))),))
                            or left[1][0] == left[1][1]):
                        continue
                    guard = {"predicate": "distinct_eqW_arguments", "arguments":
                             [render_term(t) for t in left[1]]}
                table = _lpo_rule_table(edges, ({"name": rule["name"], "lhs": render_term(left),
                                               "rhs": render_term(right)},), set(contract.signature))
                if not table[0]["oriented"]:
                    proof = {"holds": False, "reason": "universal_precedence_ground_counterexample",
                             "total_order": list(order), "required_edges": sorted(constraints),
                             "rule_table": table, "replay_verified": True,
                             "witness": {"type": "reachable_rule_counterexample", **step, "guard": guard}}
                    return proof, list(claim["evidence"]), "universal_precedence_as_stated"
    return None
