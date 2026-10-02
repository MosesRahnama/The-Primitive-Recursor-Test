"""Source-bound occurrence sums and replayed argument-count counterexamples."""

from __future__ import annotations

import re
from collections import Counter
from itertools import product

from .canonical import fold_glyph_tokens, fold_presentation
from .native_math import (
    _coefficient_dominates,
    poly_add,
    poly_const,
    poly_eval,
    poly_sub,
    poly_var,
)
from .proof_obligations import _parsed_rules, _polynomial, _substitute, _variables
from .structural_premises import _replay_step, _step


def _count(term, weights, signature):
    head, args = term
    if head not in signature:
        return poly_var(head)
    result = poly_const(weights.get(head, 0))
    for arg in args:
        result = poly_add(result, _count(arg, weights, signature))
    return result


def occurrence_sum_decision(weights, rules, signature):
    """Prove all rule differences symbolically, or return an actual ground step."""
    if (not isinstance(weights, dict) or not weights or not set(weights) <= set(signature)
            or any(type(w) is not int or w <= 0 for w in weights.values())):
        return {"holds": None, "reason": "invalid_occurrence_weights"}
    parsed = _parsed_rules(rules, signature)
    constants = sorted(s for s, p in signature.items() if not p)
    if not constants:
        return {"holds": None, "reason": "no_ground_term_inhabitant"}
    seed = constants[0], ()
    terms = [seed] + [(s, (seed,) * len(p)) for s, p in sorted(signature.items()) if p]
    table = []
    for rule, lhs, rhs in parsed:
        difference = poly_sub(_count(lhs, weights, signature), _count(rhs, weights, signature))
        proved = _coefficient_dominates(difference, 1, 0)
        table.append({"rule": rule["name"], "difference": _polynomial(difference), "proved": proved})
        if proved or set(rule) - {"name", "lhs", "rhs"}:
            continue
        variables = sorted(_variables(lhs, signature))
        if len(variables) > 4:
            continue
        for values in product(terms, repeat=len(variables)):
            substitution = dict(zip(variables, values))
            source = _substitute(lhs, substitution)
            step = _step(rule, lhs, rhs, substitution, source, [])
            left, right = _replay_step(step, parsed, signature)
            a, b = [poly_eval(_count(t, weights, signature), {}) for t in (left, right)]
            if a <= b:
                return {"holds": False, "reason": "ground_occurrence_sum_counterexample",
                        "weights": weights, "rule_table": table, "replay_verified": True,
                        "witness": {"type": "reachable_rule_counterexample", **step,
                                    "source_value": a, "target_value": b}}
    proved = all(row["proved"] for row in table)
    return {"holds": True if proved else None, "reason": "symbolic_occurrence_sum_descent"
            if proved else "occurrence_sum_descent_not_proved", "weights": weights,
            "rule_table": table, "context_increment": "C[t] has value count(t) + count(C[hole])",
            "variable_count_lower_bound": 0,
            "supported_targets": ["full_contextual_sn", "root_only_termination", "local_descent"]
            if proved else []}


def _text(value, contract):
    value = fold_glyph_tokens(fold_presentation(value, markdown_emphasis=True), contract.glyph_folds)
    for item in ("\\[", "\\]", "\\(", "\\)", "$", "\\#"):
        value = value.replace(item, "#" if item == "\\#" else "")
    return re.sub(r"\s+", " ", value).strip()


def quoted_occurrence_sum(claim, contract):
    if claim.get("kind") != "additive_measure" or claim.get("claimed_target") != "full_contextual_sn":
        return None
    payload = claim.get("transcription", {})
    if set(payload) - {"named", "comparison", "rule_scope"}:
        return None
    if payload.get("comparison", "strict") != "strict":
        return None
    if "rule_scope" in payload and set(payload["rule_scope"]) != {r["name"] for r in contract.rules}:
        return None
    texts = [_text(a["text"], contract) for a in claim.get("evidence", [])]
    strict = any(re.fullmatch(
        r"Then every rewrite step strictly decreases (?:\\mu|μ)\s*:", t) or re.fullmatch(
        r"No rule can increase the number of S's, so every reduction sequence strictly decreases "
        r"this measure, which is bounded below by zero\. Hence, all reduction sequences are finite\.", t)
        for t in texts)
    if not strict:
        return None
    candidates = []
    for text in texts:
        simple = re.fullmatch(
            r"A simple termination argument is based on a measure that counts the number of "
            r"([A-Za-z][A-Za-z0-9_]*)-symbols in the term\.", text)
        if simple:
            candidates.append({simple[1]: 1})
        formula = re.fullmatch(
            r"(?:\\mu|μ)\(t\)\s*=\s*(#[A-Za-z][A-Za-z0-9_]*\(t\)"
            r"(?:\s*\+\s*#[A-Za-z][A-Za-z0-9_]*\(t\))*)"
            r"(?:\s*\(the total number of occurrences of [A-Za-z0-9_, ]+ in the term\)\.)?", text)
        if formula:
            candidates.append(dict(Counter(re.findall(r"#([A-Za-z][A-Za-z0-9_]*)\(t\)", formula[1]))))
    if not candidates or any(w != candidates[0] for w in candidates):
        return None
    weights = candidates[0]
    if not set(weights) <= set(contract.signature):
        return None
    if payload.get("named") is not None and not (
            len(weights) == 1 and list(weights.values()) == [1]
            and payload["named"] == "symbol_count_" + next(iter(weights))):
        return None
    proof = occurrence_sum_decision(weights, contract.rules, contract.signature)
    return proof, list(claim["evidence"]), "whole_term_occurrence_sum_as_stated"


def _leading(term, symbol):
    count = 0
    while term[0] == symbol and len(term[1]) == 1:
        count += 1
        term = term[1][0]
    return count


def _multiset(term, recursive, argument, successor):
    head, args = term
    values = [_leading(args[argument-1], successor)] if head == recursive else []
    return values + [v for arg in args for v in _multiset(arg, recursive, argument, successor)]


def argument_count_refutation(recursive, argument, successor, rules, signature, *, multiset):
    """An inner projection can expose a successor in the surviving outer call."""
    if (recursive not in signature or successor not in signature or len(signature[successor]) != 1
            or type(argument) is not int or not 1 <= argument <= len(signature[recursive])):
        return None
    constants = sorted(s for s, p in signature.items() if not p)
    if not constants:
        return None
    seed = constants[0], ()
    parsed = _parsed_rules(rules, signature)
    for rule, lhs, rhs in parsed:
        if set(rule) - {"name", "lhs", "rhs"} or rhs[1] or rhs[0] in signature:
            continue
        substitution = dict.fromkeys(_variables(lhs, signature), seed)
        substitution[rhs[0]] = successor, (seed,)
        inner = _substitute(lhs, substitution)
        args = [seed] * len(signature[recursive])
        args[argument-1] = inner
        step = _step(rule, lhs, rhs, substitution, (recursive, tuple(args)), [argument])
        source, target = _replay_step(step, parsed, signature)
        if multiset:
            a, b = [_multiset(t, recursive, argument, successor) for t in (source, target)]
            # A larger maximum refutes the strict multiset extension of > on N:
            # the new maximum cannot be removed from or dominated by the source.
            refuted = bool(a and b) and max(b) > max(a)
        else:
            a, b = [_leading(t[1][argument-1], successor) for t in (source, target)]
            refuted = b > a
        if refuted:
            return {"holds": False, "reason": "replayed_argument_count_counterexample",
                    "recursive_symbol": recursive, "argument": argument, "successor": successor,
                    "scope": "all_recursive_subterms_multiset" if multiset else "surviving_outer_call",
                    "replay_verified": True, "witness": {**step, "source_value": a, "target_value": b}}
    return None


def quoted_multiset_refutation(claim, contract):
    if (claim.get("kind") not in {"call_measure", "global_multiset_measure"}
            or claim.get("claimed_target") != "full_contextual_sn"
            or contract.target_policy.get("relation_semantics") != "standard_contextual_closure"):
        return None
    texts = [_text(a["text"], contract) for a in claim.get("evidence", [])]
    for text in texts:
        match = re.fullmatch(
            r"By taking the well-founded multiset ordering over the natural numbers that count these "
            r"leading ([A-Za-z][A-Za-z0-9_]*)['’]s for all ([A-Za-z][A-Za-z0-9_]*)-subterms in a term, "
            r"each rewrite step produces a strictly smaller multiset\.", text)
        binding = next((re.fullmatch(
            r"Consequently, for any ([A-Za-z][A-Za-z0-9_]*)-subterm the number of leading "
            r"([A-Za-z][A-Za-z0-9_]*)-symbols in its third argument strictly decreases whenever that "
            r"subterm is rewritten, and no rule introduces new \1-subterms or increases that count elsewhere\.", t)
            for t in texts if t.startswith("Consequently,")), None)
        if match and binding and (binding[1], binding[2]) == (match[2], match[1]):
            payload = claim.get("transcription", {})
            if claim["kind"] == "call_measure":
                expected = {"argument": 3, "measure": match[1] + "_count", "measure_mode": "leading_chain",
                            "scope": "all_" + match[2] + "_subterms_multiset"}
            else:
                expected = {"element_measure": "the number of leading " + match[1] + "-symbols in its third argument",
                            "order": "well-founded multiset ordering over the natural numbers",
                            "scope": "all " + match[2] + "-subterms in a term", "definition": text}
            if any(k not in expected or (_text(v, contract) if isinstance(v, str) else v) != expected[k]
                   for k, v in payload.items()):
                continue
            proof = argument_count_refutation(match[2], 3, match[1], contract.rules,
                                               contract.signature, multiset=True)
            if proof:
                return proof, list(claim["evidence"]), "all_recursive_subterms_multiset_as_stated"
    return None


def global_argument_multiset_decision(recursive, argument, weights, rules, signature):
    """Check a nonduplicating rule schema and its enclosing-argument invariant."""
    if (recursive not in signature or type(argument) is not int
            or not 1 <= argument <= len(signature[recursive])
            or not isinstance(weights, dict) or not weights
            or not set(weights) <= set(signature)
            or any(type(w) is not int or w <= 0 for w in weights.values())):
        return {"holds": None, "reason": "invalid_multiset_parameters"}

    def occurrences(term, symbol):
        return ([term] if term[0] == symbol else []) + [
            found for child in term[1] for found in occurrences(child, symbol)]

    def variables(term):
        if term[0] not in signature:
            return Counter({term[0]: 1})
        return sum((variables(child) for child in term[1]), Counter())

    table = []
    for rule, lhs, rhs in _parsed_rules(rules, signature):
        left_variables, right_variables = variables(lhs), variables(rhs)
        calls = occurrences(rhs, recursive)
        if (set(rule) - {"name", "lhs", "rhs"} or lhs[0] != recursive
                or len(occurrences(lhs, recursive)) != 1 or len(calls) > 1
                or any(n != 1 for n in left_variables.values())
                or any(n > left_variables[v] for v, n in right_variables.items())):
            return {"holds": None, "reason": "multiset_rule_schema_not_supported"}
        ambient = poly_sub(_count(lhs, weights, signature), _count(rhs, weights, signature))
        ambient_ok = _coefficient_dominates(ambient, 0, 0)
        difference = (poly_sub(_count(lhs[1][argument-1], weights, signature),
                               _count(calls[0][1][argument-1], weights, signature))
                      if calls else None)
        root_ok = not calls or _coefficient_dominates(difference, 1, 0)
        table.append({"rule": rule["name"], "lhs": rule["lhs"], "rhs": rule["rhs"],
                      "left_linear": True, "no_variable_duplication": True,
                      "ambient_difference": _polynomial(ambient), "ambient_nonincrease": ambient_ok,
                      "root_element_removed": not calls,
                      "root_difference": _polynomial(difference) if difference is not None else None,
                      "root_strict": root_ok})
        if not ambient_ok or not root_ok:
            return {"holds": None, "reason": "multiset_obligation_not_proved", "rule_table": table}
    return {"holds": True, "reason": "symbolic_global_argument_multiset_descent",
            "recursive_symbol": recursive, "argument": argument, "weights": weights,
            "rule_table": table, "variable_measure_lower_bound": 0,
            "proof": {"redex": "one element removed or strictly decreased",
                      "substituted_terms": "occurrences retained unchanged or deleted; never copied",
                      "enclosing_calls": "additive argument value cannot increase under any rule",
                      "well_founded_order": "strict multiset extension of > on natural numbers"},
            "supported_targets": ["full_contextual_sn", "root_only_termination", "local_descent"]}


def quoted_global_multiset(claim, contract):
    """Read closed field forms; do not replace leading depth by total count."""
    if (claim.get("kind") != "global_multiset_measure"
            or claim.get("claimed_target") != "full_contextual_sn"
            or contract.target_policy.get("relation_semantics") != "standard_contextual_closure"):
        return None
    payload = claim.get("transcription", {})
    if set(payload) != {"definition", "element_measure", "order", "scope"}:
        return None
    fields = {k: _text(v, contract) for k, v in payload.items()}
    quotes = [_text(a["text"], contract) for a in claim.get("evidence", [])]
    if not all(any(v in quote for quote in quotes) for v in fields.values()):
        return None
    scope = re.fullmatch(r"all (?:its )?([A-Za-z][A-Za-z0-9_]*)-occurrences(?: in a term)?", fields["scope"])
    if not scope or fields["order"] not in {
            "the well-founded multiset ordering over ℕ",
            "multiset extension of the well-founded order on natural-number term sizes"}:
        return None
    recursive = scope[1]
    if fields["element_measure"] == "third-argument sizes":
        expected = f'assign to each term the multiset of "third-argument sizes" of all its {recursive}-occurrences'
        weights = dict.fromkeys(contract.signature, 1)
    else:
        measure = re.fullmatch(r"the size \(number of ([A-Za-z][A-Za-z0-9_]*)/"
                               r"([A-Za-z][A-Za-z0-9_]*) constructor symbols\) of its third argument",
                               fields["element_measure"])
        if not measure:
            return None
        expected = (f"Assign to each {recursive}-subterm a weight equal to {fields['element_measure']}. "
                    f"Take the multiset of these weights over all {recursive}-occurrences in a term.")
        weights = dict.fromkeys(measure.groups(), 1)
    if fields["definition"] != expected:
        return None
    proof = global_argument_multiset_decision(recursive, 3, weights, contract.rules, contract.signature)
    return proof, list(claim["evidence"]), "global_argument_multiset_as_stated"


def quoted_inert_head(claim, contract):
    """Absence of head rules proves their nonexistence with any extra predicate."""
    if claim.get("kind") != "root_control_proof":
        return None
    payload = claim.get("transcription", {})
    if set(payload) != {"principle"}:
        return None
    text = _text(payload["principle"], contract)
    quotes = [_text(a["text"], contract) for a in claim.get("evidence", [])]
    if not any(text in quote for quote in quotes):
        return None
    symbol = r"[A-Za-z][A-Za-z0-9_]*"
    listing = rf"{symbol}(?:, {symbol})*(?:,? (?:or|and) {symbol})?"
    simple = re.fullmatch(rf"({symbol}) has no rewrite rules\.?", text)
    plural = re.fullmatch(rf"There are no rules for ({listing}) themselves"
                          rf"(?: - they are free constructors\.)?", text)
    plain = re.fullmatch(rf"There are no rules for ({listing})(?: - they are free constructors\.)?", text)
    having = re.fullmatch(rf"({listing}) having no defining rules", text)
    matched = simple or plural or plain or having
    if matched:
        heads = set(re.findall(symbol, matched[1])) - {"or", "and"}
        parsed = _parsed_rules(contract.rules, contract.signature)
        if heads <= set(contract.signature) and all(lhs[0] not in heads for _, lhs, _ in parsed):
            return ({"holds": True, "reason": "no_rule_has_the_stated_head", "heads": sorted(heads),
                     "rule_heads": {r["name"]: lhs[0] for r, lhs, _ in parsed}, "supported_targets": [],
                     "not_certified": ["constructor_application_normality", "contextual_termination"]},
                    list(claim["evidence"]), "absence_of_head_rules_as_stated")
        return None
    match = re.fullmatch(
        r"There is no rule for ([A-Za-z][A-Za-z0-9_]*) that can rebuild an "
        r"([A-Za-z][A-Za-z0-9_]*)\(\.\.\., \.\.\., ([A-Za-z][A-Za-z0-9_]*)\(\.\.\.\)\) "
        r"or otherwise create a cycle\.", text)
    if not match or not set(match.groups()) <= set(contract.signature):
        return None
    parsed = _parsed_rules(contract.rules, contract.signature)
    if any(lhs[0] == match[1] for _, lhs, _ in parsed):
        return None
    return ({"holds": True, "reason": "no_rule_has_the_stated_head", "head": match[1],
             "rule_heads": {r["name"]: lhs[0] for r, lhs, _ in parsed}, "supported_targets": [],
             "not_certified": ["constructor_application_normality", "contextual_termination"]},
            list(claim["evidence"]), "absence_of_head_rules_as_stated")
