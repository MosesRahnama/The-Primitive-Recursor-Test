"""Replay ground counterexamples to three structural assertions about rewriting."""

from __future__ import annotations

from .native_math import parse_term, render_term
from .proof_obligations import _parsed_rules, _substitute, _variables


def _at(term, position):
    for index in position:
        if type(index) is not int or not 1 <= index <= len(term[1]):
            raise ValueError("invalid term position")
        term = term[1][index - 1]
    return term


def _replace(term, position, replacement):
    if not position:
        return replacement
    index, *rest = position
    _at(term, [index])
    args = list(term[1])
    args[index - 1] = _replace(args[index - 1], rest, replacement)
    return term[0], tuple(args)


def _paths(term, wanted, path=()):
    if term == wanted:
        yield list(path)
    for index, child in enumerate(term[1], 1):
        yield from _paths(child, wanted, (*path, index))


def _step(rule, lhs, rhs, substitution, context, position):
    source = _replace(context, position, _substitute(lhs, substitution))
    target = _replace(source, position, _substitute(rhs, substitution))
    return {"rule": rule["name"], "position": position,
            "substitution": {v: render_term(t) for v, t in sorted(substitution.items())},
            "source": render_term(source), "target": render_term(target)}


def _replay_step(step, parsed, signature):
    rule, lhs, rhs = next(r for r in parsed if r[0]["name"] == step["rule"])
    if set(rule) - {"name", "lhs", "rhs"}:
        raise ValueError("conditional or unsupported rule")
    substitution = {v: parse_term(t) for v, t in step["substitution"].items()}
    if set(substitution) != _variables(lhs, signature):
        raise ValueError("substitution does not bind precisely the rule variables")
    source, target = parse_term(step["source"]), parse_term(step["target"])
    if any(_variables(t, signature) for t in [source, target, *substitution.values()]):
        raise ValueError("counterexample must be a well-formed ground term")
    if _at(source, step["position"]) != _substitute(lhs, substitution):
        raise ValueError("source does not match the instantiated rule")
    if _replace(source, step["position"], _substitute(rhs, substitution)) != target:
        raise ValueError("target is not the stated contextual rewrite")
    return source, target


def replay_structural_refutation(statement, witness, rules, signature, relation):
    """Verify the rewrite and the violated predicate; never infer from search failure."""
    if relation != "standard_contextual_closure":
        return False
    try:
        parsed = _parsed_rules(rules, signature)
        steps = witness["steps"]
        replayed = [_replay_step(step, parsed, signature) for step in steps]
        kind, *args = statement
        if kind == "universal_wrapper_normality" and len(args) == 1 and len(steps) == 1:
            source, _ = replayed[0]
            return source[0] == args[0] and len(source[1]) == 1 and steps[0]["position"] == [1]
        if kind == "base_case_stops_rewriting" and len(args) == 2 and len(steps) == 2:
            symbol, base = args
            first, middle = replayed[0]
            second, _ = replayed[1]
            return (steps[0]["position"] == [] and steps[1]["position"] == []
                    and first[0] == symbol and (base, ()) in first[1] and middle == second)
        if kind == "only_outermost_redexes" and len(args) == 1 and len(steps) == 2:
            first, _ = replayed[0]
            second, _ = replayed[1]
            return (first == second and first[0] == args[0]
                    and steps[0]["position"] == [] and bool(steps[1]["position"]))
    except (ValueError, KeyError, TypeError, IndexError, StopIteration):
        return False
    return False


def structural_refutation(statement, rules, signature, relation):
    """Construct a ground rewrite witness, then check it with the replay function."""
    if relation != "standard_contextual_closure":
        return None
    try:
        parsed = _parsed_rules(rules, signature)
    except (ValueError, TypeError, KeyError):
        return None
    unconditional = [r for r in parsed if set(r[0]) <= {"name", "lhs", "rhs"}]
    constants = sorted(s for s, params in signature.items() if not params)
    if not constants or not unconditional:
        return None
    seed = constants[0], ()
    kind, *args = statement
    for inner_rule, inner_lhs, inner_rhs in unconditional:
        inner_sub = dict.fromkeys(_variables(inner_lhs, signature), seed)
        redex = _substitute(inner_lhs, inner_sub)
        witness = None
        if kind == "universal_wrapper_normality" and len(args) == 1:
            wrapper = args[0]
            if wrapper not in signature or len(signature[wrapper]) != 1:
                continue
            context = wrapper, (redex,)
            witness = {"type": "reducible_constructor_application", "steps": [
                _step(inner_rule, inner_lhs, inner_rhs, inner_sub, context, [1])],
                "argument_instance": render_term(redex)}
        elif kind in {"base_case_stops_rewriting", "only_outermost_redexes"}:
            for rule, lhs, rhs in unconditional:
                if not args or lhs[0] != args[0]:
                    continue
                if kind == "base_case_stops_rewriting":
                    if len(args) != 2 or (args[1], ()) not in lhs[1]:
                        continue
                    if rhs[1] or rhs[0] in signature:
                        continue
                    variables = [rhs[0]]
                else:
                    if len(args) != 1:
                        continue
                    variables = sorted(_variables(lhs, signature))
                for variable in variables:
                    substitution = dict.fromkeys(_variables(lhs, signature), seed)
                    substitution[variable] = redex
                    source = _substitute(lhs, substitution)
                    first = _step(rule, lhs, rhs, substitution, source, [])
                    if kind == "base_case_stops_rewriting":
                        second = _step(inner_rule, inner_lhs, inner_rhs, inner_sub, redex, [])
                    else:
                        position = next((p for p in _paths(lhs, (variable, ())) if p), None)
                        if position is None:
                            continue
                        second = _step(inner_rule, inner_lhs, inner_rhs, inner_sub, source, position)
                    witness = {"type": kind + "_counterexample", "steps": [first, second]}
                    if replay_structural_refutation(statement, witness, rules, signature, relation):
                        return _decision(statement, witness, relation)
        if witness and replay_structural_refutation(statement, witness, rules, signature, relation):
            return _decision(statement, witness, relation)
    return None


def _decision(statement, witness, relation):
    return {"holds": False, "reason": "replayed_structural_counterexample",
            "statement": list(statement), "relation": relation,
            "witness": witness, "replay_verified": True}
