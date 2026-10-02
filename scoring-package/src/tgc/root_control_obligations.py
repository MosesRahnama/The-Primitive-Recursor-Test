"""Source-stated root-control obligations and replayable counterexamples."""

from __future__ import annotations

import re
from typing import Any

from .canonical import fold_presentation
from .measure_eval import parse_term, render_term


def source_objects(claim: dict[str, Any]) -> dict[str, Any]:
    if "checker_objects_by_pass" in claim:
        objects = claim["checker_objects_by_pass"]
        return objects if isinstance(objects, dict) else {"invalid": objects}
    return {"representative": claim.get("representative_checker_object") or {
        "kind": "root_control_proof", "payload": {},
    }}


def _text(value: str) -> str:
    value = fold_presentation(value, markdown_emphasis=True).replace("$", "")
    return re.sub(r"\s+", " ", value).strip().rstrip(".").lower()


def _subst(term, bindings):
    if not term[1] and term[0] in bindings:
        return bindings[term[0]]
    return term[0], tuple(_subst(arg, bindings) for arg in term[1])


def _nodes(term):
    yield term
    for arg in term[1]:
        yield from _nodes(arg)


def _ground_seed(rules, symbols):
    constants = sorted({
        node[0] for rule in rules for side in ("lhs", "rhs")
        for node in _nodes(parse_term(rule[side]))
        if not node[1] and node[0] in symbols
    })
    return (constants[0], ()) if constants else None


def projection_pump(rules, symbols, bound: int) -> dict[str, Any] | None:
    """C[x] -> x gives C^(n+1)[g] -> ... -> g, for every finite n."""
    seed = _ground_seed(rules, symbols)
    if seed is None:
        return None
    for rule in rules:
        # This certificate concerns unconditional first-order rules only.
        if set(rule) - {"name", "lhs", "rhs"}:
            continue
        lhs, rhs = parse_term(rule["lhs"]), parse_term(rule["rhs"])
        if rhs[1] or rhs[0] in symbols or not lhs[1]:
            continue
        variables = {node[0] for node in _nodes(lhs)
                     if not node[1] and node[0] not in symbols}
        if rhs[0] not in variables:
            continue
        fixed = {name: seed for name in variables - {rhs[0]}}
        context = _subst(lhs, fixed)
        # This is a compact induction certificate, not a bounded search.
        # The sample records at most four terms; the length is symbolic.
        sample = [seed]
        for _ in range(min(bound + 1, 3)):
            sample.append(_subst(context, {rhs[0]: sample[-1]}))
        return {
            "type": "projection_rule_arbitrarily_long_root_chains",
            "rule": rule["name"], "lhs": rule["lhs"], "rhs": rule["rhs"],
            "parameter": rhs[0], "ground_seed": render_term(seed),
            "fixed_substitution": {k: render_term(v) for k, v in sorted(fixed.items())},
            "context_pattern": render_term(context),
            "recurrence": "T(0)=ground_seed; T(k+1)=context_pattern[parameter:=T(k)]",
            "step_identity": "T(k+1) -> T(k) by the named rule at the root",
            "claimed_bound": bound, "chain_length": bound + 1,
            "sample_chain": [render_term(term) for term in reversed(sample)],
            "sample_is_full_chain": bound <= 2,
        }
    return None


def _subterm_counterexample(rules, symbols):
    seed = _ground_seed(rules, symbols)
    if seed is None:
        return None
    for rule in rules:
        if set(rule) - {"name", "lhs", "rhs"}:
            continue
        lhs, rhs = parse_term(rule["lhs"]), parse_term(rule["rhs"])
        variables = {node[0] for side in (lhs, rhs) for node in _nodes(side)
                     if not node[1] and node[0] not in symbols}
        bindings = dict.fromkeys(variables, seed)
        left, right = _subst(lhs, bindings), _subst(rhs, bindings)
        if not any(right == node for arg in left[1] for node in _nodes(arg)):
            return {"type": "rhs_not_proper_subterm", "rule": rule["name"],
                    "lhs": render_term(left), "rhs": render_term(right),
                    "substitution": {k: render_term(v) for k, v in sorted(bindings.items())}}
    return None


_BOUND = re.compile(
    r"(?:the )?maximum length of (?:any|every) (?:root )?reduction chain "
    r"is at most (?P<n>[0-9]{1,100})(?=$|\s*\(|\.(?=$|\s))"
)
_BASE_PRINCIPLES = {
    "case analysis on the rule table", "case analysis", "rule table", "rule_table",
    "every step yields a proper subterm or an immediately-normal root",
    "every root step yields a proper subterm or a root-normal term",
    "proper subterm or root-normal", "proper_subterm_or_root_normal",
}


def _principle_bound(text):
    # The conclusion is a complete final clause, possibly following a
    # because-list. Conditions, negations and restricted examples do not type.
    if re.search(r"\b(?:if|suppose|assuming|not|unless|example only)\b", text):
        return None
    match = re.search(
        r"(?:^|, )any reduction sequence is (?:trivially )?finite "
        r"\(with a maximum length of (?P<n>[0-9]{1,100})\)$", text)
    return int(match["n"]) if match else None


def _rule_heads(rules):
    return {parse_term(rule["lhs"])[0] for rule in rules}


def _named_symbols(text, symbols):
    return {
        symbol
        for symbol in symbols
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])",
            text,
            re.IGNORECASE,
        )
    }


def _head_fact(text, rules, symbols):
    """Decide a closed statement about rule heads or redex roots."""

    heads = _rule_heads(rules)
    named = _named_symbols(text, symbols)
    low = _text(text)
    no_rule = re.search(
        r"(?:no (?:rewrite )?rules? (?:exist )?for|has no (?:rewrite )?rules?|"
        r"no rule with .* root of the left-hand side|no lhs rules|"
        r"which has no (?:rewrite )?rules?|inert \(no rules\))",
        low,
    )
    if no_rule and named:
        absent = sorted(named - heads)
        contradicted = sorted(named & heads)
        return {
            "holds": not contradicted,
            "reason": "stated_symbols_have_no_rule_heads" if not contradicted
            else "stated_head_absence_false",
            "stated_symbols": sorted(named),
            "absent_rule_heads": absent,
            "contradicted_rule_heads": contradicted,
            "actual_rule_heads": sorted(heads),
        }
    redex = re.search(
        r"(?:all )?redexes? (?:are|involve|possible|occur).*?"
        r"(?:at |within |solely at )?([a-z][a-z0-9_]*)[- ]applications?",
        low,
    ) or re.search(
        r"reductions? only occur within ([a-z][a-z0-9_]*)[- ]applications?",
        low,
    )
    if redex:
        folded = next(
            (symbol for symbol in symbols if symbol.lower() == redex[1].lower()),
            None,
        )
        if folded is None:
            return None
        return {
            "holds": heads == {folded},
            "reason": "every_rule_has_the_stated_redex_head" if heads == {folded}
            else "stated_exclusive_redex_head_false",
            "stated_head": folded,
            "actual_rule_heads": sorted(heads),
        }
    return None


def _exposed_constructor_witness(rules, symbols):
    """A contextual step can expose a constructor in an outer call argument."""

    seed = _ground_seed(rules, symbols)
    if seed is None:
        return None
    arities = {}
    for rule in rules:
        for side in ("lhs", "rhs"):
            for node in _nodes(parse_term(rule[side])):
                if node[0] in symbols:
                    arities.setdefault(node[0], len(node[1]))
    unary = next(
        (
            symbol
            for symbol in sorted(symbols)
            if arities.get(symbol) == 1 and symbol not in _rule_heads(rules)
        ),
        None,
    )
    recursive = next(iter(sorted(_rule_heads(rules))), None)
    if recursive is None or unary is None:
        return None
    arity = next((len(parse_term(rule["lhs"])[1]) for rule in rules
                  if parse_term(rule["lhs"])[0] == recursive), 0)
    if arity < 1:
        return None
    for rule in rules:
        lhs, rhs = parse_term(rule["lhs"]), parse_term(rule["rhs"])
        if lhs[0] != recursive or rhs[1] or rhs[0] in symbols:
            continue
        variables = {node[0] for node in _nodes(lhs)
                     if not node[1] and node[0] not in symbols}
        if rhs[0] not in variables:
            continue
        constructed = (unary, (seed,))
        bindings = {name: seed for name in variables}
        bindings[rhs[0]] = constructed
        redex_before = _subst(lhs, bindings)
        redex_after = _subst(rhs, bindings)
        outer_args = [seed] * arity
        outer_args[-1] = redex_before
        before = (recursive, tuple(outer_args))
        outer_args[-1] = redex_after
        after = (recursive, tuple(outer_args))
        return {
            "type": "contextual_projection_exposes_constructor",
            "rule": rule["name"],
            "context": f"{recursive}(...,□)",
            "term_before": render_term(before),
            "term_after": render_term(after),
            "exposed_constructor": unary,
            "argument": arity,
        }
    return None


def _nested_redex_below_inert_head_witness(rules, symbols):
    """A constructor head with no rules does not freeze reducible arguments."""

    heads = _rule_heads(rules)
    for rule in rules:
        rhs = parse_term(rule["rhs"])
        if rhs[0] in heads:
            continue
        nested = next((node for node in _nodes(rhs) if node is not rhs and node[0] in heads), None)
        if nested is not None:
            return {
                "type": "nested_defined_symbol_below_inert_head",
                "rule": rule["name"],
                "rhs": rule["rhs"],
                "inert_head": rhs[0],
                "nested_rule_head": nested[0],
                "basis": "contextual rewriting permits a later step in that argument",
            }
    return None


def _growth_denial(text):
    return bool(re.search(
        r"(?:no (?:rewrite|rule)|nothing|cannot|can never).*?"
        r"(?:rebuild|re-expand|introduc|inject|increase|re-trigger).*?"
        r"(?:recursive|recursion|third argument|s\(?\.\.\.|duplication)",
        text,
    ))


def _root_termination_conclusion(text):
    return bool(re.search(
        r"(?:no way to build an infinite root-only reduction chain|"
        r"infinite (?:step|root) chains? (?:are|is) impossible|"
        r"paths? (?:are )?naturally bounded)",
        text,
    ))


def check_payload(payload, rules, symbols, decision, relation_typer):
    """Check every stated field; a false conjunct refutes its containing claim."""
    if not isinstance(payload, dict):
        return {"verdict": "UNKNOWN", "detail": "root_control_payload_invalid"}
    principle = payload.get("principle")
    principle_text = _text(principle) if isinstance(principle, str) else ""
    relation = payload.get("relation")
    relation_text = _text(relation) if isinstance(relation, str) else ""
    relation_is_named_step = (
        relation_text in {"step", "the step relation"}
        and ("root" in principle_text or "literally defined" in principle_text)
    )
    accepted, reason = (
        (True, None)
        if relation_is_named_step
        else relation_typer("relation", relation)
    )
    if not accepted:
        return {"verdict": "UNKNOWN", "detail": reason}
    unknown = []
    if set(payload) - {"relation", "principle", "definition"}:
        unknown.append("root_control_extra_fields_untyped")
    # Refuting an explicit finite bound does not require interpreting the
    # response's separate explanation of why it believes that bound.
    definition = payload.get("definition")
    if definition not in (None, ""):
        definition_text = _text(definition) if isinstance(definition, str) else ""
        match = _BOUND.match(definition_text) if definition_text else None
        if match:
            witness = projection_pump(rules, symbols, int(match["n"]))
            if witness:
                return {"verdict": "REFUTED", "detail": "root_control_uniform_bound_false",
                        "field": "definition", "witness": witness}
        if definition_text not in {
            "making termination especially direct",
            "termination is quite direct",
        }:
            unknown.append("root_control_definition_untyped_or_unproved")
    if relation_text:
        fact = _head_fact(relation_text, rules, symbols)
        if fact is not None and not fact["holds"]:
            return {"verdict": "REFUTED", "detail": fact["reason"],
                    "field": "relation", "witness": fact}
        negative_context_scope = re.search(
            r"\b(?:no|lacks?)\b.*\b(?:contextual closure|congruence rules?)\b",
            relation_text,
        )
        if fact is None and not relation_is_named_step and not negative_context_scope and not re.search(
            r"\b(?:root|head|top-level|outermost|as written|literally defined)\b",
            relation_text,
        ):
            unknown.append("root_control_relation_obligation_unproved")
    if principle not in (None, ""):
        text = principle_text
        bound = _principle_bound(text)
        if bound is not None:
            witness = projection_pump(rules, symbols, bound)
            if witness:
                return {"verdict": "REFUTED", "detail": "root_control_uniform_bound_false",
                        "field": "principle", "witness": witness}
        if _growth_denial(text):
            witness = (
                _nested_redex_below_inert_head_witness(rules, symbols)
                if "re-trigger" in text
                else _exposed_constructor_witness(rules, symbols)
            )
            if witness:
                return {"verdict": "REFUTED", "detail": "root_control_context_growth_denial_false",
                        "field": "principle", "witness": witness}
            unknown.append("root_control_growth_denial_unproved")
        elif text in _BASE_PRINCIPLES:
            pass
        elif _root_termination_conclusion(text):
            if not decision["holds"]:
                unknown.append("root_control_termination_conclusion_unproved")
        elif re.search(r"first rule .*?(?:terminates immediately|base case)", text):
            first = rules[0] if rules else None
            if first is None:
                unknown.append("root_control_base_rule_missing")
            else:
                root = parse_term(first["lhs"])[0]
                if any(node[0] == root for node in _nodes(parse_term(first["rhs"]))):
                    unknown.append("root_control_base_rule_recurs")
        elif (fact := _head_fact(text, rules, symbols)) is not None:
            if not fact["holds"]:
                return {"verdict": "REFUTED", "detail": fact["reason"],
                        "field": "principle", "witness": fact}
        elif re.fullmatch(r"(?:making )?termination (?:is |even )?(?:quite |especially )?"
                          r"(?:direct|simpler)(?: since paths are naturally bounded)?", text):
            if not decision["holds"]:
                unknown.append("root_control_termination_summary_unproved")
        elif re.fullmatch(
                r"(?:as literally defined, step only rewrites at the root, and )?"
                r"every non-collapsing rule produces a term whose root has no applicable rule; "
                r"the collapsing rules expose a proper subterm(?:\. thus infinite step chains are impossible)?",
                text):
            if not decision["holds"]:
                unknown.append("root_control_rule_partition_unproved")
        elif text == (
            "rules either expose an existing proper subterm or produce a term whose "
            "outer constructor has no applicable rule"
        ):
            if not decision["holds"]:
                unknown.append("root_control_rule_partition_unproved")
        elif text == "every root step yields a proper subterm":
            if not all(row["rhs_proper_subterm_of_lhs"] for row in decision["table"]):
                witness = _subterm_counterexample(rules, symbols)
                if witness:
                    return {"verdict": "REFUTED", "detail": "root_control_subterm_claim_false",
                            "field": "principle", "witness": witness}
                unknown.append("root_control_subterm_claim_unproved")
        elif text in {"every rule's rhs is a normal form or blocks",
                      "every root step yields a root-normal term"}:
            if not all(row["rhs_root_irreducible_all_instances"] for row in decision["table"]):
                witness = projection_pump(rules, symbols, 1)
                if witness:
                    return {"verdict": "REFUTED", "detail": "root_control_rhs_normal_claim_false",
                            "field": "principle", "witness": witness}
                unknown.append("root_control_rhs_normal_claim_unproved")
        else:
            unknown.append("root_control_principle_untyped")
    if unknown:
        return {"verdict": "UNKNOWN", "detail": "|".join(unknown)}
    return {"verdict": "PASS" if decision["holds"] else "REFUTED",
            "detail": "root_control_rule_table_holds" if decision["holds"]
            else "root_control_principle_fails"}
