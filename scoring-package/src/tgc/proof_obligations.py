"""Exact checks for rule-restricted size claims and ground-term interpretations."""

from __future__ import annotations

from itertools import product
from typing import Any

from .canonical import parse_polynomial
from .native_math import (
    INTERPRETATION_DOMAIN_LOWER_BOUNDS,
    _coefficient_dominates,
    _interpret_term,
    _typed_interpretation,
    parse_term,
    poly_add,
    poly_const,
    poly_eval,
    poly_sub,
    poly_substitute,
    poly_var,
    poly_vars,
    render_term,
)


def interpretation_payload_matches(core, payload, signature):
    interpretation, issue = _typed_interpretation(core, signature)
    mapping = payload.get("map")
    if issue or not isinstance(mapping, dict) or set(mapping) != set(signature):
        return False
    return (payload.get("domain", "N") == core.get("payload", {}).get("domain", "N")
            and all(isinstance(mapping[s], str)
                    and parse_polynomial(mapping[s], set(params)) == polynomial
                    for s, (params, polynomial) in interpretation.items()))


def _polynomial(value):
    return [{"coefficient": c, "powers": dict(m)} for m, c in sorted(value.items())]


def _variables(term, signature):
    head, args = term
    if head not in signature:
        if args:
            raise ValueError("unknown function symbol")
        return {head}
    if len(args) != len(signature[head]):
        raise ValueError("constructor arity mismatch")
    return set().union(*(_variables(a, signature) for a in args))


def _parsed_rules(rules, signature):
    parsed, names = [], set()
    for rule in rules:
        name = rule.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("blank or duplicate rule name")
        names.add(name)
        lhs, rhs = parse_term(rule["lhs"]), parse_term(rule["rhs"])
        if lhs[0] not in signature or not _variables(rhs, signature) <= _variables(lhs, signature):
            raise ValueError("invalid rule variables or root")
        parsed.append((rule, lhs, rhs))
    if not parsed:
        raise ValueError("empty rule table")
    return parsed


def _size(term, signature):
    head, args = term
    if head not in signature:
        return poly_var(head)
    value = poly_const(1)
    for arg in args:
        value = poly_add(value, _size(arg, signature))
    return value


def _substitute(term, substitution):
    head, args = term
    if head in substitution:
        return substitution[head]
    return head, tuple(_substitute(a, substitution) for a in args)


def rule_size_decision(rule_names, comparison, rules, signature) -> dict[str, Any]:
    """Check node-count descent only on the explicitly selected rules."""
    if (not isinstance(rule_names, list) or not rule_names
            or any(not isinstance(n, str) for n in rule_names)
            or len(rule_names) != len(set(rule_names)) or comparison not in {"strict", "weak"}):
        return {"holds": None, "reason": "invalid_rule_scope_or_comparison"}
    try:
        parsed = _parsed_rules(rules, signature)
    except (KeyError, TypeError, ValueError) as error:
        return {"holds": None, "reason": str(error)}
    if not set(rule_names) <= {r["name"] for r, _, _ in parsed}:
        return {"holds": None, "reason": "unknown_rule_name"}
    constants = sorted(s for s, params in signature.items() if not params)
    if not constants:
        return {"holds": None, "reason": "no_ground_term_inhabitant"}
    base = constants[0], ()
    terms = [base]
    constructors = sorted(s for s, params in signature.items() if params)
    if constructors:
        symbol = constructors[0]
        for _ in range(8):
            terms.append((symbol, (terms[-1],) + (base,) * (len(signature[symbol]) - 1)))
    threshold = 1 if comparison == "strict" else 0
    table = []
    unresolved = False
    for rule, lhs, rhs in parsed:
        if rule["name"] not in rule_names:
            continue
        difference = poly_sub(_size(lhs, signature), _size(rhs, signature))
        proved = _coefficient_dominates(difference, threshold, 1)
        row = {"rule": rule["name"], "lhs": rule["lhs"], "rhs": rule["rhs"],
               "size_difference": _polynomial(difference), "variable_size_lower_bound": 1,
               "proved": proved}
        table.append(row)
        if proved:
            continue
        unresolved = True
        variables = sorted(_variables(lhs, signature))
        # This search supplies actual ground terms; exhausting it proves nothing.
        if len(variables) > 4 or rule.get("guard"):
            continue
        for values in product(terms, repeat=len(variables)):
            substitution = dict(zip(variables, values))
            sizes = {v: poly_eval(_size(t, signature), {}) for v, t in substitution.items()}
            if poly_eval(difference, sizes) >= threshold:
                continue
            source, target = _substitute(lhs, substitution), _substitute(rhs, substitution)
            return {"holds": False, "reason": "ground_rule_size_counterexample",
                    "rule_scope": sorted(rule_names), "comparison": comparison,
                    "rule_table": table,
                    "witness": {"type": "reachable_rule_counterexample", "rule": rule["name"],
                                "substitution": {v: render_term(t) for v, t in substitution.items()},
                                "source": render_term(source), "target": render_term(target),
                                "source_size": poly_eval(_size(source, signature), {}),
                                "target_size": poly_eval(_size(target, signature), {})}}
    return {"holds": None if unresolved else True,
            "reason": "unproved_size_obligation" if unresolved else "symbolic_rule_size_descent",
            "rule_scope": sorted(rule_names), "comparison": comparison, "rule_table": table,
            "supported_targets": ["local_descent"] if not unresolved else [],
            "context_scope": "selected_rules_only"}


def ground_term_interpretation_decision(core, rules, signature, lower_bound) -> dict[str, Any]:
    """Prove a stated range invariant, then strict descent on ground terms.

    The declared codomain is retained. This proves no claim about arbitrary
    valuations outside the proved term range.
    """
    if type(lower_bound) is not int or not 0 <= lower_bound <= 1024:
        return {"holds": None, "reason": "invalid_term_lower_bound"}
    try:
        interpretation, issue = _typed_interpretation(core, signature)
        parsed = _parsed_rules(rules, signature)
    except (KeyError, TypeError, ValueError) as error:
        return {"holds": None, "reason": str(error)}
    if issue:
        return {"holds": None, "reason": issue}
    domain = core.get("payload", {}).get("domain", "N")
    domain_lower = INTERPRETATION_DOMAIN_LOWER_BOUNDS.get(domain)
    if domain_lower is None or lower_bound < domain_lower:
        return {"holds": None, "reason": "range_does_not_establish_declared_codomain"}
    if not any(not p for p in signature.values()):
        return {"holds": None, "reason": "no_ground_term_inhabitant"}
    closure, monotonicity, orientation = [], [], []
    common = {"statement": "ground_term_interpretation_contextual_descent",
              "declared_codomain": domain, "stated_term_lower_bound": lower_bound,
              "closure_table": closure, "monotonicity_table": monotonicity,
              "rule_table": orientation,
              "arbitrary_carrier_valuations_certified": False}
    for symbol, (parameters, polynomial) in sorted(interpretation.items()):
        if any(c < 0 for c in polynomial.values()):
            return {"holds": None, "reason": "negative_constructor_coefficient", **common}
        minimum = poly_eval(polynomial, dict.fromkeys(parameters, lower_bound))
        closure.append({"symbol": symbol, "value_at_lower_bound": minimum,
                        "nonnegative_coefficients": True, "closed": minimum >= lower_bound})
        if minimum < lower_bound:
            return {"holds": None, "reason": "term_range_induction_not_proved", **common}
        for i, parameter in enumerate(parameters, 1):
            bumped = poly_substitute(polynomial, {parameter: poly_add(poly_var(parameter), poly_const(1))})
            difference = poly_sub(bumped, polynomial)
            proved = _coefficient_dominates(difference, 1, lower_bound)
            monotonicity.append({"symbol": symbol, "argument": i, "proved": proved,
                                 "unit_increment": _polynomial(difference)})
            if not proved:
                return {"holds": None, "reason": "term_range_monotonicity_not_proved", **common}
    for rule, lhs, rhs in parsed:
        difference = poly_sub(_interpret_term(lhs, interpretation, set(signature)),
                              _interpret_term(rhs, interpretation, set(signature)))
        proved = _coefficient_dominates(difference, 1, lower_bound)
        orientation.append({"rule": rule["name"], "difference": _polynomial(difference),
                            "variables": sorted(poly_vars(difference)), "proved": proved})
        if not proved:
            return {"holds": None, "reason": "term_range_rule_descent_not_proved", **common}
    return {"holds": True, "reason": "range_induction_and_contextual_descent",
            "supported_targets": ["full_contextual_sn", "root_only_termination", "local_descent"],
            **common}
