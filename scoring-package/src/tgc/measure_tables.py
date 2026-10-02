"""Deterministic verdict tables for stated measures, premises and root claims.

Four checkers give the Tier 1 decision function a computed answer:

- :func:`measure_verdict` decides one stated reading of a measure slot. It
  evaluates the quantity on every ground term in a fixed bounded universe,
  applies every one-step rewrite of the stated target relation, and reports
  the first step on which the claimed comparison fails. A PASS verdict is
  returned only when the enumerated universe carries no failing step AND
  ``MEASURE_TRUTH.json`` lists the reading as proven with a theorem or
  certificate name. The bounded search guards a fresh truth table and never
  substitutes for the theorem.
- :func:`derive_carrier` reads a stated domain phrase and stated constant
  values and returns the carrier that the two statements pin down.
- :func:`premise_truth` decides every item of the surface premise catalogs,
  and every false item carries a ground counterexample computed here.
- :func:`root_only_decision` decides claims about the literal root relation of
  the Test 01 kernel, including a claimed uniform bound on chain length.

Enumeration contract. Ground terms are immutable tuples ``(symbol, children)``.
The universe holds every ground term with at most seven constructor symbols in
a fixed size-then-symbol order, followed by the counterexample shapes that the
surface scoring policies name. Steps are visited in a fixed order: term, then
position in pre-order with the root first, then rule in table order. Guards
declared on a rule restrict its instances: the fruit arm guards
``R_cherry_diff`` with distinct arguments, so an equality-difference step with
two equal arguments is a step of the KO7 relation and not of the fruit
relation.

The successor quantity names (``leading_S``, ``total_S``) read the instance's
own successor constructor, which is the symbol that the recursive rule's left
side wraps around the third argument (``S``, ``delta``, or ``grape``).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any

from .canonical import fold_presentation
from .measure_eval import _candidate_substitutions, _multiset_gt, parse_term, render_term
from .native_math import (
    poly_add,
    poly_const,
    poly_from_typed,
    poly_sub,
    poly_substitute,
    poly_var,
    poly_vars,
)
from .registry import fold_glyph_tokens
from .root_control_obligations import check_payload

Term = tuple[str, tuple]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_UNIVERSE_SIZE = 7
_MAX_UNIVERSE_TERMS = 4096
_MAX_CALL_INSTANCES = 4096
_MAX_CHAIN_DEPTH = 12

_QUANTITIES = (
    "leading_S",
    "total_S",
    "term_size",
    "depth",
    "recursive_symbol_count",
    # The next three are written out in full by some responses and named by none of the five
    # above. Only a second reader states them; the reading spread in method_policy never
    # ranges over them, so an unstated field keeps its old readings.
    "proper_subterm",  # the subterm order on the descending argument; recursive call only
    "F_plus_S_count",  # occurrences of the recursive symbol plus the successor symbol
    "S_plus_Z_count",  # occurrences of the successor symbol plus the constants
)
_SCOPES = (
    "rewritten_occurrence",
    "recursive_call",
    "whole_term",
    "all_recursive_subterms",
    "root_only",
    "current_redexes",  # the recursive-symbol subterms that match a rule at that moment
)
_AGGREGATES = ("none", "sum", "multiset", "max")
_STRENGTHS = ("strict", "weak", "exact_one")  # exact_one: the value falls by exactly one
_QUANTIFIERS = (
    "every_step",
    "every_rule_application",
    "recursive_call_only",
    "root_only",
)
_TARGETS = ("contextual", "root_only", "recursive_call_relation")

_SHAPE_TEMPLATES = (
    "F(F(Z,Z,S(Z)),Z,Z)",
    "F(Z,Z,F(S(Z),Z,Z))",
    "F(Z,F(Z,Z,S(S(Z))),S(Z))",
    "F(Z,Z,S(F(Z,S(S(Z)),S(Z))))",
    "F(F(Z,Z,Z),Z,G(Z,Z))",
    "G(F(Z,Z,Z))",
    "F(Z,F(Z,Z,Z),Z)",
    "F(F(Z,Z,Z),Z,Z)",
)

_CATALOG_OF = {
    "schema-a": "duplicating_schema_a",
    "test01-ko7": "duplicating_test01",
    "test01-fruit": "duplicating_test01",
    "schema-a-new": "sans",
}

_CATALOG_ITEMS = {
    "duplicating_schema_a": (
        "size_nonincreasing",
        "no_new_redexes",
        "payload_shared_cancels",
        "whole_term_multiset_decreases",
        "nonoverlap_determinism_wn_sn",
        "per_step_measure_decrease",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
    ),
    "duplicating_test01": (
        "size_nonincreasing",
        "no_new_redexes",
        "payload_shared_cancels",
        "whole_term_multiset_decreases",
        "nonoverlap_determinism_wn_sn",
        "per_step_measure_decrease",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
        "eq_diff_size_denied",
        "step_root_only_basis",
    ),
    "sans": (
        "g_normal_form",
        "only_outermost_f_redexes",
        "s_count_every_step_strict",
        "size_nonincreasing",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
    ),
}

_MEASURE_ANCHOR = {
    "duplicating_schema_a": "CandidateE.muE_not_step_orienting",
    "duplicating_test01": "BenchmarkContract.test1_directMeasure_not_adequate",
}


class _Unsupported(Exception):
    """The stated reading or input lies outside the enumerated semantics."""


def _norm(value: Any) -> str:
    text = fold_presentation(str(value if value is not None else ""))
    return re.sub(r"\s+", " ", text).strip().lower()


def _menu(value: Any, allowed: tuple[str, ...], field: str) -> str:
    text = _norm(value)
    for candidate in allowed:
        if candidate.lower() == text:
            return candidate
    raise _Unsupported(f"unknown_{field}[{text or 'empty'}]")


@dataclass(frozen=True)
class _Rule:
    name: str
    lhs: str
    rhs: str
    guard: tuple[str, tuple[str, ...]] | None


@dataclass(frozen=True)
class _Instance:
    key: str
    signature: tuple[tuple[str, tuple[str, ...]], ...]
    rules: tuple[_Rule, ...]
    recursive_symbol: str | None
    glyph_folds: tuple[tuple[str, str], ...]

    @property
    def symbols(self) -> frozenset[str]:
        return frozenset(symbol for symbol, _ in self.signature)

    @property
    def constants(self) -> tuple[str, ...]:
        return tuple(sorted(symbol for symbol, params in self.signature if not params))


def _guard_of(rule: dict[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    guard = rule.get("guard")
    if guard in (None, {}, ""):
        return None
    if not isinstance(guard, dict):
        raise _Unsupported("rule_guard_unexpressible")
    predicate = str(guard.get("predicate") or "")
    if not predicate.startswith("distinct"):
        raise _Unsupported("rule_guard_unexpressible")
    variables = guard.get("variables")
    if (
        isinstance(variables, list)
        and variables
        and all(isinstance(item, str) and item for item in variables)
    ):
        return predicate, tuple(variables)
    arguments = guard.get("arguments")
    if (
        isinstance(arguments, list)
        and arguments
        and all(isinstance(item, str) and item for item in arguments)
    ):
        return predicate + "@ground", tuple(arguments)
    raise _Unsupported("rule_guard_unexpressible")


def _freeze(raw: dict[str, Any]) -> _Instance:
    signature = raw.get("signature")
    if not isinstance(signature, dict) or not signature:
        raise _Unsupported("instance_signature_missing")
    frozen_signature = tuple(
        sorted(
            (str(symbol), tuple(str(item) for item in params))
            for symbol, params in signature.items()
        )
    )
    raw_rules = raw.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise _Unsupported("instance_rules_missing")
    rules: list[_Rule] = []
    for rule in raw_rules:
        if not isinstance(rule, dict):
            raise _Unsupported("instance_rule_malformed")
        name = rule.get("name")
        lhs = rule.get("lhs")
        rhs = rule.get("rhs")
        if not all(isinstance(item, str) and item for item in (name, lhs, rhs)):
            raise _Unsupported("instance_rule_malformed")
        rules.append(_Rule(str(name), str(lhs), str(rhs), _guard_of(rule)))
    recursive = raw.get("recursive_symbol")
    folds = raw.get("glyph_folds") or ()
    return _Instance(
        key=str(raw.get("instance_key") or "custom"),
        signature=frozen_signature,
        rules=tuple(rules),
        recursive_symbol=str(recursive) if isinstance(recursive, str) and recursive else None,
        glyph_folds=tuple(
            (str(left), str(right))
            for left, right in folds
            if isinstance(left, str) and isinstance(right, str)
        ),
    )


def _raw_instance(instance: Any) -> dict[str, Any] | None:
    if isinstance(instance, dict):
        return instance
    name = str(instance)
    candidates = (
        PACKAGE_ROOT / "spec" / "generated" / name / "v3" / "instance_config.json",
        PACKAGE_ROOT / "spec" / "v3" / "instances" / f"{name}.json",
    )
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _instance(instance: Any) -> _Instance:
    raw = _raw_instance(instance)
    if raw is None:
        raise _Unsupported(f"unknown_instance[{instance}]")
    return _freeze(raw)


def _rule_variables(lhs: Term, symbols: frozenset[str]) -> tuple[str, ...]:
    found: list[str] = []

    def visit(term: Term) -> None:
        head, children = term
        if head not in symbols and not children:
            if head not in found:
                found.append(head)
        for child in children:
            visit(child)

    visit(lhs)
    return tuple(found)


def _proper_subterm(inner: Term, outer: Term) -> bool:
    if inner == outer:
        return False
    return any(node == inner for node in _subterms(outer))


def _contains_symbol(term: Term, symbol: str) -> bool:
    return term[0] == symbol or any(_contains_symbol(child, symbol) for child in term[1])


def _subterms(term: Term):
    yield term
    for child in term[1]:
        yield from _subterms(child)


def _positions(term: Term, prefix: tuple[int, ...] = ()):
    yield prefix, term
    for index, child in enumerate(term[1], 1):
        yield from _positions(child, (*prefix, index))


def _subterm_at(term: Term, position: tuple[int, ...]) -> Term:
    node = term
    for index in position:
        node = node[1][index - 1]
    return node


def _replace_at(term: Term, position: tuple[int, ...], replacement: Term) -> Term:
    if not position:
        return replacement
    index, *rest = position
    children = list(term[1])
    children[index - 1] = _replace_at(children[index - 1], tuple(rest), replacement)
    return term[0], tuple(children)


def _match(pattern: Term, term: Term, symbols: frozenset[str], bindings: dict[str, Term]) -> bool:
    head, children = pattern
    if head not in symbols and not children:
        bound = bindings.get(head)
        if bound is None:
            bindings[head] = term
            return True
        return bound == term
    if head != term[0] or len(children) != len(term[1]):
        return False
    return all(_match(child, arg, symbols, bindings) for child, arg in zip(children, term[1]))


def _instantiate(pattern: Term, bindings: dict[str, Term], symbols: frozenset[str]) -> Term:
    head, children = pattern
    if head not in symbols and not children:
        if head not in bindings:
            raise _Unsupported(f"unbound_rule_variable[{head}]")
        return bindings[head]
    return head, tuple(_instantiate(child, bindings, symbols) for child in children)


def _guard_satisfied(rule: _Rule, bindings: dict[str, Term]) -> bool:
    if rule.guard is None:
        return True
    predicate, payload = rule.guard
    if predicate.endswith("@ground"):
        rendered = [render_term(parse_term(text)) for text in payload]
    else:
        rendered = [render_term(bindings[name]) for name in payload if name in bindings]
        if len(rendered) != len(payload):
            return False
    return len(set(rendered)) == len(rendered)


def _compositions(total: int, parts: int):
    if parts == 1:
        yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest


@lru_cache(maxsize=None)
def _universe(instance: _Instance) -> tuple[Term, ...]:
    signature = dict(instance.signature)
    constants = instance.constants
    terms: list[Term] = []
    if constants:
        layers: dict[int, list[Term]] = {1: [(symbol, ()) for symbol in constants]}
        ordered: list[Term] = list(layers[1])
        for size in range(2, _UNIVERSE_SIZE + 1):
            layer: list[Term] = []
            for symbol in sorted(signature):
                arity = len(signature[symbol])
                if arity == 0:
                    continue
                for split in _compositions(size - 1, arity):
                    pools = [layers.get(part, []) for part in split]
                    if any(not pool for pool in pools):
                        continue
                    for children in product(*pools):
                        layer.append((symbol, tuple(children)))
            layers[size] = layer
            ordered.extend(layer)
        terms = ordered[:_MAX_UNIVERSE_TERMS]
    known = set(terms)
    for shape in _shape_terms(instance):
        if shape not in known:
            known.add(shape)
            terms.append(shape)
    return tuple(terms)


def _shape_terms(instance: _Instance) -> tuple[Term, ...]:
    roles = _roles(instance)
    if not instance.constants:
        return ()
    substitutes = {
        "F": roles.get("F"),
        "G": roles.get("G"),
        "S": roles.get("S"),
        "Z": instance.constants[0],
    }
    shapes: list[Term] = []
    for template in _SHAPE_TEMPLATES:
        text = template
        missing = [key for key in ("F", "G", "S") if f"{key}(" in text and substitutes[key] is None]
        if missing:
            continue
        for key in ("F", "G", "S"):
            if f"{key}(" in text:
                text = text.replace(f"{key}(", f"{substitutes[key]}(")
        text = text.replace("Z", str(substitutes["Z"]))
        try:
            shapes.append(parse_term(text))
        except ValueError:
            continue
    return tuple(shapes)


@lru_cache(maxsize=None)
def _roles(instance: _Instance) -> dict[str, Any]:
    roles: dict[str, Any] = {
        "F": instance.recursive_symbol,
        "G": None,
        "S": None,
        "call_rule": None,
        "descending": None,
    }
    symbols = instance.symbols
    recursive = instance.recursive_symbol
    if recursive is None:
        return roles
    for rule in instance.rules:
        lhs = parse_term(rule.lhs)
        rhs = parse_term(rule.rhs)
        if lhs[0] != recursive:
            continue
        if roles["call_rule"] is None and _contains_symbol(rhs, recursive):
            roles["call_rule"] = rule.name
            if rhs[0] != recursive:
                roles["G"] = rhs[0]
            callee = next((node for node in _subterms(rhs) if node[0] == recursive), None)
            if callee is not None:
                for index in range(1, min(len(lhs[1]), len(callee[1])) + 1):
                    if _proper_subterm(callee[1][index - 1], lhs[1][index - 1]):
                        roles["descending"] = index
                        break
        if roles["call_rule"] == rule.name and len(lhs[1]) >= 3:
            third = lhs[1][2]
            if third[0] in symbols and third[1] and third[0] != recursive:
                roles["S"] = third[0]
    return roles


@dataclass(frozen=True)
class _Step:
    rule: str
    position: tuple[int, ...]
    before: Term
    after: Term
    redex: Term
    contractum: Term
    substitution: tuple[tuple[str, str], ...]


def _substitution_text(bindings: dict[str, Term]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((name, render_term(term)) for name, term in bindings.items()))


@lru_cache(maxsize=None)
def _all_steps(instance: _Instance) -> tuple[_Step, ...]:
    symbols = instance.symbols
    parsed = [(rule, parse_term(rule.lhs), parse_term(rule.rhs)) for rule in instance.rules]
    steps: list[_Step] = []
    for term in _universe(instance):
        for position, subterm in _positions(term):
            for rule, lhs, rhs in parsed:
                bindings: dict[str, Term] = {}
                if not _match(lhs, subterm, symbols, bindings):
                    continue
                if not _guard_satisfied(rule, bindings):
                    continue
                try:
                    redex = _instantiate(lhs, bindings, symbols)
                    contractum = _instantiate(rhs, bindings, symbols)
                except _Unsupported:
                    continue
                steps.append(
                    _Step(
                        rule=rule.name,
                        position=position,
                        before=_replace_at(term, position, redex),
                        after=_replace_at(term, position, contractum),
                        redex=redex,
                        contractum=contractum,
                        substitution=_substitution_text(bindings),
                    )
                )
    return tuple(steps)


@lru_cache(maxsize=None)
def _call_instances(instance: _Instance) -> tuple[tuple[_Step, Term, Term], ...]:
    """Ground instances of the recursive rule: (step, caller call, callee call)."""

    roles = _roles(instance)
    call_name = roles.get("call_rule")
    recursive = instance.recursive_symbol
    if call_name is None or recursive is None:
        return ()
    symbols = instance.symbols
    rule = next(rule for rule in instance.rules if rule.name == call_name)
    lhs, rhs = parse_term(rule.lhs), parse_term(rule.rhs)
    variables = _rule_variables(lhs, symbols)
    pool = list(_universe(instance))
    if not variables or not pool:
        return ()
    records: list[tuple[_Step, Term, Term]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    combos = 0
    for values in _candidate_substitutions(list(variables), pool):
        combos += 1
        if combos > _MAX_CALL_INSTANCES:
            break
        bindings = dict(zip(variables, values))
        if not _guard_satisfied(rule, bindings):
            continue
        key = _substitution_text(bindings)
        if key in seen:
            continue
        seen.add(key)
        caller = _instantiate(lhs, bindings, symbols)
        contractum = _instantiate(rhs, bindings, symbols)
        call_position = next(
            (position for position, node in _positions(rhs) if node[0] == recursive),
            None,
        )
        if call_position is None:
            continue
        callee = _subterm_at(contractum, call_position)
        if callee[0] != recursive:
            continue
        records.append(
            (
                _Step(
                    rule=rule.name,
                    position=(),
                    before=caller,
                    after=contractum,
                    redex=caller,
                    contractum=contractum,
                    substitution=key,
                ),
                caller,
                callee,
            )
        )
    return tuple(records)


def _quantity_value(instance: _Instance, term: Term, quantity: str) -> int:
    roles = _roles(instance)
    successor = roles.get("S")
    recursive = instance.recursive_symbol
    if quantity == "term_size":
        return sum(1 for _ in _subterms(term))
    if quantity == "depth":
        return _depth(term)
    if quantity == "recursive_symbol_count":
        if recursive is None:
            raise _Unsupported("recursive_symbol_unknown")
        return sum(1 for node in _subterms(term) if node[0] == recursive)
    if quantity == "total_S":
        if successor is None:
            raise _Unsupported("successor_symbol_unknown")
        return sum(1 for node in _subterms(term) if node[0] == successor)
    if quantity == "leading_S":
        if successor is None:
            raise _Unsupported("successor_symbol_unknown")
        length = 0
        node = term
        while node[0] == successor and node[1]:
            length += 1
            node = node[1][0]
        return length
    if quantity == "F_plus_S_count":
        if recursive is None or successor is None:
            raise _Unsupported("recursive_or_successor_symbol_unknown")
        return sum(1 for node in _subterms(term) if node[0] in (recursive, successor))
    if quantity == "S_plus_Z_count":
        if successor is None:
            raise _Unsupported("successor_symbol_unknown")
        constants = set(instance.constants)
        return sum(
            1
            for node in _subterms(term)
            if node[0] == successor or (not node[1] and node[0] in constants)
        )
    if quantity == "proper_subterm":
        # an order on terms, not a number: only the recursive-call comparison reads it
        raise _Unsupported("proper_subterm_needs_recursive_call_scope")
    raise _Unsupported(f"unknown_quantity[{quantity}]")


def _depth(term: Term) -> int:
    return 1 + max((_depth(child) for child in term[1]), default=0)


def _recursive_arguments(instance: _Instance, term: Term) -> tuple[Term, ...]:
    descending = _roles(instance).get("descending")
    recursive = instance.recursive_symbol
    if recursive is None or descending is None:
        raise _Unsupported("descending_argument_unknown")
    arguments: list[Term] = []
    for node in _subterms(term):
        if node[0] == recursive and len(node[1]) >= descending:
            arguments.append(node[1][descending - 1])
    return tuple(arguments)


@lru_cache(maxsize=None)
def _parsed_rules(instance: _Instance) -> tuple[tuple[_Rule, Term], ...]:
    return tuple((rule, parse_term(rule.lhs)) for rule in instance.rules)


def _is_redex(instance: _Instance, node: Term) -> bool:
    """True when some rule's left side, guard included, matches this subterm."""

    for rule, lhs in _parsed_rules(instance):
        bindings: dict[str, Term] = {}
        if _match(lhs, node, instance.symbols, bindings) and _guard_satisfied(rule, bindings):
            return True
    return False


def _redex_arguments(instance: _Instance, term: Term) -> tuple[Term, ...]:
    """The descending argument of every recursive-symbol subterm that is a redex now."""

    descending = _roles(instance).get("descending")
    recursive = instance.recursive_symbol
    if recursive is None or descending is None:
        raise _Unsupported("descending_argument_unknown")
    return tuple(
        node[1][descending - 1]
        for node in _subterms(term)
        if node[0] == recursive and len(node[1]) >= descending and _is_redex(instance, node)
    )


def _redex_count_of(instance: _Instance, term: Term, symbol: str) -> int:
    """How many subterms with head `symbol` match a rule's left side now."""

    return sum(1 for node in _subterms(term) if node[0] == symbol and _is_redex(instance, node))


def _aggregate_value(
    instance: _Instance,
    term: Term,
    quantity: str,
    aggregate: str,
    scope: str = "all_recursive_subterms",
):
    if scope == "current_redexes":
        arguments = _redex_arguments(instance, term)
    else:
        arguments = _recursive_arguments(instance, term)
    values = [_quantity_value(instance, argument, quantity) for argument in arguments]
    if aggregate == "sum":
        return sum(values)
    if aggregate == "max":
        return max(values, default=0)
    if aggregate == "multiset":
        return tuple(sorted(values, reverse=True))
    raise _Unsupported(f"unknown_aggregate[{aggregate}]")


def _holds_comparison(strength: str, before, after) -> bool:
    if strength == "exact_one":
        if isinstance(before, tuple) or isinstance(after, tuple):
            raise _Unsupported("exact_one_needs_a_number")
        return before - after == 1
    if isinstance(before, tuple) or isinstance(after, tuple):
        if tuple(before) == tuple(after):
            return strength == "weak"
        return _multiset_gt(tuple(before), tuple(after))
    if strength == "strict":
        return after < before
    return after <= before


def _reading_check(
    scope: str, aggregate: str, comparison_quantifier: str, proof_target: str
) -> None:
    if scope == "recursive_call":
        if comparison_quantifier != "recursive_call_only":
            raise _Unsupported("recursive_call_scope_requires_recursive_call_only")
        if proof_target != "recursive_call_relation":
            raise _Unsupported("recursive_call_scope_requires_recursive_call_relation")
        if aggregate != "none":
            raise _Unsupported("recursive_call_scope_does_not_aggregate")
        return
    if comparison_quantifier not in {"every_step", "every_rule_application", "root_only"}:
        raise _Unsupported(f"quantifier_not_expressible[{comparison_quantifier}]")
    if comparison_quantifier == "root_only" and scope not in {
        "whole_term",
        "rewritten_occurrence",
        "root_only",
    }:
        raise _Unsupported("root_only_quantifier_scope_mismatch")
    if scope in ("all_recursive_subterms", "current_redexes"):
        if aggregate == "none":
            raise _Unsupported("aggregate_missing_for_subterm_scope")
        return
    if aggregate != "none":
        raise _Unsupported("aggregate_without_subterm_scope")
    if scope == "root_only" and comparison_quantifier != "root_only":
        raise _Unsupported("root_only_scope_requires_root_only_quantifier")
    if proof_target not in {"contextual", "root_only"}:
        raise _Unsupported("proof_target_scope_mismatch")


def _reading_values(instance: _Instance, step: _Step, quantity: str, scope: str, aggregate: str):
    def value(term: Term):
        if aggregate == "none":
            return _quantity_value(instance, term, quantity)
        return _aggregate_value(instance, term, quantity, aggregate, scope)

    if scope in {"whole_term", "root_only", "all_recursive_subterms", "current_redexes"}:
        return value(step.before), value(step.after)
    if scope == "rewritten_occurrence":
        return value(step.redex), value(step.contractum)
    raise _Unsupported(f"unknown_scope[{scope}]")


def _render_value(value) -> Any:
    if isinstance(value, tuple):
        return list(value)
    return value


def _counterexample(instance: _Instance, step: _Step, before, after) -> dict[str, Any]:
    return {
        "term_before": render_term(step.before),
        "term_after": render_term(step.after),
        "rule": step.rule,
        "position": list(step.position),
        "value_before": _render_value(before),
        "value_after": _render_value(after),
        "step_kind": "root" if not step.position else "contextual",
        "substitution": dict(step.substitution),
    }


def _table_id(
    instance_key: str,
    quantity: str,
    scope: str,
    aggregate: str,
    comparison_strength: str,
    comparison_quantifier: str,
    proof_target: str,
) -> str:
    return "|".join(
        (
            instance_key,
            quantity,
            scope,
            aggregate,
            comparison_strength,
            comparison_quantifier,
            proof_target,
        )
    )


@lru_cache(maxsize=None)
def _truth_entries() -> dict[str, dict[str, Any]]:
    path = Path(__file__).with_name("MEASURE_TRUTH.json")
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return {}
    table: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("table_id"), str):
            table[entry["table_id"]] = entry
    return table


_VERDICT_MEMO: dict[tuple[str, ...], dict[str, Any]] = {}


def _remember(key: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any]:
    """Store one verdict and hand the caller its own copy."""

    _VERDICT_MEMO[key] = payload
    return dict(payload)


def measure_verdict(
    instance: Any,
    quantity: Any,
    scope: Any,
    aggregate: Any,
    comparison_strength: Any,
    comparison_quantifier: Any,
    proof_target: Any,
) -> dict[str, Any]:
    """Decide one stated reading of a measure slot over the bounded step universe."""

    try:
        frozen = _instance(instance)
    except _Unsupported as error:
        return {"verdict": "UNSUPPORTED", "reason": str(error)}
    try:
        quantity_value = _menu(quantity, _QUANTITIES, "quantity")
        scope_value = _menu(scope, _SCOPES, "scope")
        aggregate_value = _menu(aggregate, _AGGREGATES, "aggregate")
        strength = _menu(comparison_strength, _STRENGTHS, "comparison_strength")
        quantifier = _menu(comparison_quantifier, _QUANTIFIERS, "comparison_quantifier")
        target = _menu(proof_target, _TARGETS, "proof_target")
        _reading_check(scope_value, aggregate_value, quantifier, target)
    except _Unsupported as error:
        return {"verdict": "UNSUPPORTED", "reason": str(error)}
    table_id = _table_id(
        frozen.key, quantity_value, scope_value, aggregate_value, strength, quantifier, target
    )
    # The verdict is a function of the frozen instance and the six menu values alone, and
    # _find_failure walks the whole bounded step universe on every call. A scoring run asks for
    # the same reading hundreds of times, because a slot whose response leaves fields unwritten is
    # decided over every reading its menus permit. The memo returns the same answer sooner; a copy
    # goes out so a caller that edits its payload leaves the stored one alone.
    memo_key = (table_id,)
    cached = _VERDICT_MEMO.get(memo_key)
    if cached is not None:
        return dict(cached)
    try:
        failure = _find_failure(
            frozen, quantity_value, scope_value, aggregate_value, strength, quantifier, target
        )
    except _Unsupported as error:
        return _remember(memo_key, {"verdict": "UNSUPPORTED", "reason": str(error), "table_id": table_id})
    entry = _truth_entries().get(table_id)
    theorem = str((entry or {}).get("theorem") or "")
    if failure is not None:
        payload: dict[str, Any] = {
            "verdict": "REFUTED",
            "counterexample": failure,
            "table_id": table_id,
        }
        if entry is not None:
            payload["truth"] = {
                "status": entry.get("status"),
                "theorem": theorem,
                "basis": entry.get("basis"),
            }
        return _remember(memo_key, payload)
    if entry is not None:
        if entry.get("verdict") == "PASS" and entry.get("status") == "proven" and theorem:
            return _remember(memo_key, {
                "verdict": "PASS",
                "table_id": table_id,
                "theorem": theorem,
                "basis": entry.get("basis"),
            })
        return _remember(memo_key, {
            "verdict": "UNSUPPORTED",
            "reason": f"truth_table_declares_{entry.get('verdict') or 'unknown'}",
            "table_id": table_id,
        })
    return _remember(
        memo_key, {"verdict": "UNSUPPORTED", "reason": "reading_not_in_truth_table", "table_id": table_id}
    )


def step_values(
    instance: Any, term: Any, quantity: Any, scope: Any, aggregate: Any
) -> list[dict[str, Any]]:
    """One-step rows for one ground term under one stated reading.

    The term text folds through the contract's glyph table first, so a
    fruit-spelled term gives the same rows as its KO7 spelling.
    """

    frozen = _instance(instance)
    quantity_value = _menu(quantity, _QUANTITIES, "quantity")
    scope_value = _menu(scope, _SCOPES, "scope")
    aggregate_value = _menu(aggregate, _AGGREGATES, "aggregate")
    source = parse_term(fold_glyph_tokens(str(term), frozen.glyph_folds))
    rows: list[dict[str, Any]] = []
    for step in _all_steps(frozen):
        if step.before != source:
            continue
        before, after = _reading_values(frozen, step, quantity_value, scope_value, aggregate_value)
        rows.append(
            {
                "rule": step.rule,
                "position": list(step.position),
                "term_before": render_term(step.before),
                "term_after": render_term(step.after),
                "value_before": _render_value(before),
                "value_after": _render_value(after),
            }
        )
    return rows


def _find_failure(
    instance: _Instance,
    quantity: str,
    scope: str,
    aggregate: str,
    strength: str,
    quantifier: str,
    target: str,
) -> dict[str, Any] | None:
    if scope == "recursive_call":
        descending = _roles(instance).get("descending")
        if descending is None:
            raise _Unsupported("descending_argument_unknown")
        for step, caller, callee in _call_instances(instance):
            if quantity == "proper_subterm":
                # the callee's argument must be a proper subterm of the caller's argument
                if strength == "exact_one":
                    raise _Unsupported("exact_one_needs_a_number")
                caller_argument = caller[1][descending - 1]
                callee_argument = callee[1][descending - 1]
                holds = _proper_subterm(callee_argument, caller_argument) or (
                    strength == "weak" and callee_argument == caller_argument
                )
                if not holds:
                    return _counterexample(
                        instance, step, render_term(caller_argument), render_term(callee_argument)
                    )
                continue
            before = _quantity_value(instance, caller[1][descending - 1], quantity)
            after = _quantity_value(instance, callee[1][descending - 1], quantity)
            if not _holds_comparison(strength, before, after):
                return _counterexample(instance, step, before, after)
        return None
    root_only = quantifier == "root_only" or target == "root_only"
    collect = _redex_arguments if scope == "current_redexes" else _recursive_arguments
    for step in _all_steps(instance):
        if root_only and step.position:
            continue
        if (
            aggregate == "multiset"
            and not collect(instance, step.before)
            and not collect(instance, step.after)
        ):
            continue
        before, after = _reading_values(instance, step, quantity, scope, aggregate)
        if not _holds_comparison(strength, before, after):
            return _counterexample(instance, step, before, after)
    return None


# Written interpretations the polynomial reader cannot hold: `max`, `min` and a function of an
# argument's syntax. A response's map is evaluated on every ground term of the bounded universe
# and every step is compared. A failing step refutes the map; finding none proves nothing.
_EXPRESSION_GLYPHS = (
    ("\\cdot", "*"),
    ("\\times", "*"),
    ("·", "*"),
    ("×", "*"),
    ("^", "**"),
    ("{", "("),
    ("}", ")"),
    ("δcount", "dcount"),
)
_EXPRESSION_CALLS = frozenset({"max", "min", "dcount"})
_MAX_EXPONENT = 64


def _check_expression(node: ast.AST, parameters: frozenset[str]) -> None:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult, ast.Pow)):
        _check_expression(node.left, parameters)
        _check_expression(node.right, parameters)
        return
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and node.value >= 0
    ):
        return
    if isinstance(node, ast.Name) and node.id in parameters:
        return
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _EXPRESSION_CALLS
        and node.args
        and not node.keywords
    ):
        if node.func.id == "dcount":
            # dcount reads the argument term itself, so it takes exactly one parameter name
            if len(node.args) != 1 or not (
                isinstance(node.args[0], ast.Name) and node.args[0].id in parameters
            ):
                raise _Unsupported("dcount_needs_one_parameter")
            return
        for argument in node.args:
            _check_expression(argument, parameters)
        return
    raise _Unsupported(f"expression_operation_unreadable[{type(node).__name__}]")


def _expression_tree(expression: str, parameters: tuple[str, ...]) -> ast.AST:
    text = str(expression)
    for source, target in _EXPRESSION_GLYPHS:
        text = text.replace(source, target)
    try:
        tree = ast.parse(text.strip(), mode="eval").body
    except SyntaxError as error:
        raise _Unsupported("expression_unreadable") from error
    _check_expression(tree, frozenset(parameters))
    return tree


def _evaluate_expression(
    node: ast.AST,
    values: dict[str, int],
    arguments: dict[str, Term],
    successor: str | None,
) -> int:
    if isinstance(node, ast.Constant):
        return int(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.BinOp):
        left = _evaluate_expression(node.left, values, arguments, successor)
        right = _evaluate_expression(node.right, values, arguments, successor)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right > _MAX_EXPONENT:
            raise _Unsupported("exponent_outside_bounded_evaluation")
        return left**right
    if isinstance(node, ast.Call):
        name = node.func.id
        if name == "dcount":
            if successor is None:
                raise _Unsupported("successor_symbol_unknown")
            length, term = 0, arguments[node.args[0].id]
            while term[0] == successor and term[1]:
                length += 1
                term = term[1][0]
            return length
        items = [_evaluate_expression(item, values, arguments, successor) for item in node.args]
        return max(items) if name == "max" else min(items)
    raise _Unsupported("expression_operation_unreadable")


def written_expression_readable(expression: Any, parameters: Any) -> bool:
    """True when the bounded evaluator can read one written formula over these parameters."""

    try:
        _expression_tree(str(expression or ""), tuple(str(item) for item in parameters or ()))
    except _Unsupported:
        return False
    return True


def interpretation_refutation(
    instance: Any, definitions: Any, proof_target: Any = "contextual"
) -> dict[str, Any]:
    """Search the bounded step universe for a step on which a written interpretation does not fall.

    `definitions` maps each signature symbol to (parameters, expression). An expression uses
    `+`, `*`, `^`, `max`, `min`, natural numbers, the parameter names, and `dcount(p)`, the number
    of leading successor symbols of the argument term `p` (responses write it `δcount`). A step
    whose value does not strictly fall is REFUTED with both values. No failing step is
    UNSUPPORTED: this search refutes a map and never proves one.
    """

    try:
        frozen = _instance(instance)
        signature = dict(frozen.signature)
        if not isinstance(definitions, dict):
            raise _Unsupported("definitions_malformed")
        trees: dict[str, tuple[tuple[str, ...], ast.AST]] = {}
        for symbol, declared in signature.items():
            entry = definitions.get(symbol)
            if entry is None:
                raise _Unsupported(f"definition_missing[{symbol}]")
            parameters, expression = entry
            names = tuple(str(item) for item in parameters or ()) or tuple(declared)
            if len(names) != len(declared):
                raise _Unsupported(f"arity_mismatch[{symbol}]")
            trees[symbol] = (names, _expression_tree(str(expression), names))
        successor = _roles(frozen).get("S")
        memo: dict[Term, int] = {}

        def value(term: Term) -> int:
            known = memo.get(term)
            if known is not None:
                return known
            head, children = term
            names, tree = trees[head]
            values = {name: value(child) for name, child in zip(names, children)}
            result = _evaluate_expression(tree, values, dict(zip(names, children)), successor)
            memo[term] = result
            return result

        root_only = _norm(proof_target) == "root_only"
        for step in _all_steps(frozen):
            if root_only and step.position:
                continue
            before, after = value(step.before), value(step.after)
            if not after < before:
                return {
                    "verdict": "REFUTED",
                    "counterexample": _counterexample(frozen, step, before, after),
                    "basis": "the written map, evaluated on this ground step, does not fall",
                }
    except _Unsupported as error:
        return {"verdict": "UNSUPPORTED", "reason": str(error)}
    return {"verdict": "UNSUPPORTED", "reason": "no_failing_step_in_bounded_universe"}


_LEX_COMPONENT = re.compile(r"^(count|redexes)\(\s*([^()\s]+)\s*\)$")


def lex_tuple_refutation(
    instance: Any, components: Any, proof_target: Any = "contextual"
) -> dict[str, Any]:
    """Search the bounded step universe for a step a stated lexicographic tuple does not lower.

    `count(X)` counts the occurrences of symbol X. `redexes(X)` counts the subterms with head X
    that match a rule's left side at that moment, which no per-rule count difference can
    express, because a rewrite inside an argument changes it. A step whose tuple is not
    lexicographically smaller afterwards is REFUTED. No failing step is UNSUPPORTED.
    """

    try:
        frozen = _instance(instance)
        parsed: list[tuple[str, str]] = []
        for component in components or ():
            match = _LEX_COMPONENT.match(str(component).strip())
            if match is None:
                raise _Unsupported(f"component_unreadable[{component}]")
            symbol = fold_glyph_tokens(match.group(2), frozen.glyph_folds)
            if symbol not in frozen.symbols:
                raise _Unsupported(f"component_symbol_unknown[{symbol}]")
            parsed.append((match.group(1), symbol))
        if not parsed:
            raise _Unsupported("no_components")

        def value(term: Term) -> tuple[int, ...]:
            return tuple(
                sum(1 for node in _subterms(term) if node[0] == symbol)
                if kind == "count"
                else _redex_count_of(frozen, term, symbol)
                for kind, symbol in parsed
            )

        root_only = _norm(proof_target) == "root_only"
        for step in _all_steps(frozen):
            if root_only and step.position:
                continue
            before, after = value(step.before), value(step.after)
            if not after < before:  # tuples compare lexicographically
                return {
                    "verdict": "REFUTED",
                    "counterexample": _counterexample(frozen, step, before, after),
                    "basis": "the tuple is not lexicographically smaller after this step",
                }
    except _Unsupported as error:
        return {"verdict": "UNSUPPORTED", "reason": str(error)}
    return {"verdict": "UNSUPPORTED", "reason": "no_failing_step_in_bounded_universe"}


def _variable_size_delta(instance: _Instance, rule: _Rule) -> tuple[int, dict[str, int]]:
    """The affine size difference |rhs| - |lhs| plus the per-variable coefficients."""

    symbols = instance.symbols
    lhs, rhs = parse_term(rule.lhs), parse_term(rule.rhs)
    variables = _rule_variables(lhs, symbols)
    lhs_nodes = [node for node in _subterms(lhs) if not (node[0] in variables and not node[1])]
    rhs_nodes = [node for node in _subterms(rhs) if not (node[0] in variables and not node[1])]
    constant = len(rhs_nodes) - len(lhs_nodes)
    coefficients: dict[str, int] = {}
    for name in variables:
        left = sum(1 for node in _subterms(lhs) if node == (name, ()))
        right = sum(1 for node in _subterms(rhs) if node == (name, ()))
        coefficients[name] = right - left
    return constant, coefficients


def _max_size_delta(instance: _Instance, rule: _Rule) -> int | None:
    """Upper bound of |rhs| - |lhs| over ground instances, or None if unbounded."""

    constant, coefficients = _variable_size_delta(instance, rule)
    if any(value > 0 for value in coefficients.values()):
        return None
    return constant + sum(coefficients.values())


def _non_duplicating(instance: _Instance) -> bool:
    for rule in instance.rules:
        _, coefficients = _variable_size_delta(instance, rule)
        if any(value > 0 for value in coefficients.values()):
            return False
    return True


def _successor_delta(instance: _Instance, rule: _Rule) -> tuple[int, dict[str, int]] | None:
    """The successor-count difference as an affine function of variable counts."""

    successor = _roles(instance).get("S")
    if successor is None:
        return None
    symbols = instance.symbols
    lhs, rhs = parse_term(rule.lhs), parse_term(rule.rhs)
    variables = _rule_variables(lhs, symbols)

    def profile(term: Term) -> tuple[int, dict[str, int]]:
        constant = sum(1 for node in _subterms(term) if node[0] == successor)
        coefficients = {
            name: sum(1 for node in _subterms(term) if node == (name, ())) for name in variables
        }
        return constant, coefficients

    left_constant, left_coefficients = profile(lhs)
    right_constant, right_coefficients = profile(rhs)
    return (
        right_constant - left_constant,
        {name: right_coefficients[name] - left_coefficients[name] for name in variables},
    )


def _step_budget(instance: _Instance) -> bool:
    """True when successor count plus size bounds every chain of the instance."""

    for rule in instance.rules:
        size_delta = _max_size_delta(instance, rule)
        successor = _successor_delta(instance, rule)
        if size_delta is None or size_delta > 0 or successor is None:
            return False
        constant, coefficients = successor
        if constant > 0 or any(value > 0 for value in coefficients.values()):
            return False
        if size_delta <= -1:
            continue
        if constant <= -1:
            continue
        return False
    return True


def _first_step(instance: _Instance, predicate) -> _Step | None:
    for step in _all_steps(instance):
        if predicate(step):
            return step
    return None


def _one_step_results(instance: _Instance, term: Term) -> list[_Step]:
    return [step for step in _all_steps(instance) if step.before == term]


def _redex_count(instance: _Instance, term: Term) -> int:
    recursive = instance.recursive_symbol
    if recursive is None:
        return 0
    return sum(1 for node in _subterms(term) if node[0] == recursive)


def _size(term: Term) -> int:
    return sum(1 for _ in _subterms(term))


def _text_counterexample(step: _Step, detail: str) -> str:
    position = "root" if not step.position else str(list(step.position))
    return (
        f"{render_term(step.before)} -> {render_term(step.after)} "
        f"[rule {step.rule} at {position}]; {detail}"
    )


def _first_failing_step(
    instance: _Instance, quantity: str, scope: str, aggregate: str, strength: str
) -> tuple[_Step, Any, Any] | None:
    for step in _all_steps(instance):
        if (
            aggregate != "none"
            and not _recursive_arguments(instance, step.before)
            and not (_recursive_arguments(instance, step.after))
        ):
            continue
        before, after = _reading_values(instance, step, quantity, scope, aggregate)
        if not _holds_comparison(strength, before, after):
            return step, before, after
    return None


def _bound_of(instance: _Instance, term: Term) -> int | None:
    roles = _roles(instance)
    if roles.get("S") is None:
        return None
    return max(
        _quantity_value(instance, term, "total_S"),
        max(
            (_quantity_value(instance, node, "leading_S") for node in _subterms(term)),
            default=0,
        ),
    )


def _chain_longer_than_bound(instance: _Instance) -> dict[str, Any] | None:
    universe = _universe(instance)
    index = {term: position for position, term in enumerate(universe)}
    successors: dict[Term, list[_Step]] = {}
    for step in _all_steps(instance):
        successors.setdefault(step.before, []).append(step)
    for term in universe:
        bound = _bound_of(instance, term)
        if bound is None or bound < 1:
            continue
        path: list[_Step] = []
        dead: set[tuple[Term, int]] = set()

        def walk(node: Term, depth: int) -> bool:
            if len(path) > bound:
                return True
            if depth > min(bound + 1, _MAX_CHAIN_DEPTH):
                return False
            if (node, depth) in dead:
                return False
            ordered = sorted(
                successors.get(node, ()), key=lambda step: index.get(step.after, len(index))
            )
            for step in ordered:
                path.append(step)
                if walk(step.after, depth + 1):
                    return True
                path.pop()
            dead.add((node, depth))
            return False

        if walk(term, 0):
            return {
                "initial_term": render_term(term),
                "bound": bound,
                "chain_length": len(path),
                "chain": [render_term(path[0].before)] + [render_term(step.after) for step in path],
                "steps": [{"rule": step.rule, "position": list(step.position)} for step in path],
            }
    return None


def _base_rule(instance: _Instance) -> _Rule | None:
    """The recursive symbol's collapsing rule, whose third argument is a constant."""

    recursive = instance.recursive_symbol
    constants = set(instance.constants)
    if recursive is None:
        return None
    best: _Rule | None = None
    for rule in instance.rules:
        lhs = parse_term(rule.lhs)
        rhs = parse_term(rule.rhs)
        if lhs[0] != recursive or _contains_symbol(rhs, recursive):
            continue
        if len(lhs[1]) < 3 or lhs[1][2][0] not in constants or lhs[1][2][1]:
            continue
        if best is None or _size(lhs) < _size(parse_term(best.lhs)):
            best = rule
    return best


def _first_base_survivor(instance: _Instance) -> tuple[_Step, _Step] | None:
    base = _base_rule(instance)
    if base is None:
        return None
    for step in _all_steps(instance):
        if step.rule != base.name:
            continue
        follow = _one_step_results(instance, step.after)
        if follow:
            return step, follow[0]
    return None


def _wrapper_inside_step(instance: _Instance) -> _Step | None:
    wrapper = _roles(instance).get("G")
    if wrapper is None:
        return None
    for step in _all_steps(instance):
        if step.before[0] == wrapper and step.position:
            return step
    return None


def _only_inner_redex_term(instance: _Instance) -> Term | None:
    for term in _universe(instance):
        steps = _one_step_results(instance, term)
        if steps and all(step.position for step in steps):
            return term
    return None


def _first_growth_step(instance: _Instance, *, rule: str | None = None) -> _Step | None:
    return _first_step(
        instance,
        lambda step: (rule is None or step.rule == rule) and _size(step.after) > _size(step.before),
    )


def _first_new_redex_step(instance: _Instance) -> _Step | None:
    return _first_step(
        instance,
        lambda step: _redex_count(instance, step.after) > _redex_count(instance, step.before),
    )


def _duplicated_payload_step(instance: _Instance) -> tuple[_Step, str, int, int] | None:
    call_rule = _roles(instance).get("call_rule")
    if call_rule is None:
        return None
    rule = next((item for item in instance.rules if item.name == call_rule), None)
    if rule is None:
        return None
    symbols = instance.symbols
    lhs, rhs = parse_term(rule.lhs), parse_term(rule.rhs)
    for name in _rule_variables(lhs, symbols):
        left = sum(1 for node in _subterms(lhs) if node == (name, ()))
        right = sum(1 for node in _subterms(rhs) if node == (name, ()))
        if right > left:
            for step in _all_steps(instance):
                if step.rule == call_rule:
                    return step, name, left, right
            return None
    return None


def _size_nonincreasing(instance: _Instance, catalog: str) -> dict[str, Any]:
    deltas = [_max_size_delta(instance, rule) for rule in instance.rules]
    if all(delta is not None and delta <= 0 for delta in deltas):
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "every rule's size difference is at most zero for arbitrary payload sizes",
        }
    step = _first_growth_step(instance)
    if step is None:
        return {
            "truth": "unstated",
            "counterexample": "",
            "theorem": "",
            "basis": "size growth unproved",
        }
    detail = f"size {_size(step.before)} -> {_size(step.after)}"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "this rule instance grows the term",
    }


def _no_new_redexes(instance: _Instance, catalog: str) -> dict[str, Any]:
    step = _first_new_redex_step(instance)
    if step is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no step in the enumerated universe grows the recursive redex count",
        }
    detail = (
        f"recursive redexes {_redex_count(instance, step.before)} -> "
        f"{_redex_count(instance, step.after)}"
    )
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "the recursive rule copies the payload, and the payload carries a redex",
    }


def _payload_shared_cancels(instance: _Instance, catalog: str) -> dict[str, Any]:
    found = _duplicated_payload_step(instance)
    if found is None:
        return {
            "truth": "unstated",
            "counterexample": "",
            "theorem": "",
            "basis": "no duplicating rule found",
        }
    step, name, left, right = found
    detail = f"payload {name} occurs {left} time(s) left and {right} time(s) right"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "the payload is copied, so it does not cancel",
    }


def _whole_term_multiset_decreases(instance: _Instance, catalog: str) -> dict[str, Any]:
    found = _first_failing_step(instance, "depth", "all_recursive_subterms", "multiset", "strict")
    if found is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no step in the enumerated universe defeats the multiset comparison",
        }
    step, before, after = found
    detail = f"third-argument depth multiset {_render_value(before)} -> {_render_value(after)}"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": _MEASURE_ANCHOR.get(catalog, ""),
        "basis": "the copied payload adds an equal-valued element, defeating the multiset order",
    }


def _nonoverlap_determinism_wn_sn(instance: _Instance, catalog: str) -> dict[str, Any]:
    term = None
    for candidate in _universe(instance):
        results = {render_term(step.after) for step in _one_step_results(instance, candidate)}
        if len(results) >= 2:
            term = candidate
            break
    if term is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no enumerated term carries two distinct one-step results",
        }
    steps = _one_step_results(instance, term)
    rendered = sorted({render_term(step.after) for step in steps})
    position = "root" if not steps[0].position else str(list(steps[0].position))
    return {
        "truth": False,
        "counterexample": (
            f"{render_term(term)}; two distinct one-step results {rendered[0]} and "
            f"{rendered[1]} [rule {steps[0].rule} at {position}]"
        ),
        "theorem": "",
        "basis": "a term with two redexes has two one-step results, so reduction is not deterministic",
    }


def _per_step_measure_decrease(instance: _Instance, catalog: str) -> dict[str, Any]:
    found = _first_failing_step(instance, "total_S", "whole_term", "none", "strict")
    if found is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no step in the enumerated universe fails the total-S descent",
        }
    step, before, after = found
    detail = f"total S count {before} -> {after}, so the step does not strictly decrease"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": _MEASURE_ANCHOR.get(catalog, ""),
        "basis": "the all-step quantifier fails on a concrete step",
    }


def _per_term_bound(instance: _Instance, catalog: str) -> dict[str, Any]:
    if _non_duplicating(instance) and _step_budget(instance):
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": (
                "no rule copies a variable; no rule grows the successor count or the size, "
                "and every rule either shrinks the size or drops the successor count, so a "
                "chain stays shorter than the initial size plus successor count"
            ),
        }
    witness = _chain_longer_than_bound(instance)
    if witness is not None:
        return {
            "truth": False,
            "counterexample": (
                f"{witness['initial_term']} admits a chain of {witness['chain_length']} "
                f"steps while its successor-count and successor-depth bound is "
                f"{witness['bound']}"
            ),
            "theorem": _MEASURE_ANCHOR.get(catalog, ""),
            "basis": "the copied payload recreates work that the initial term does not bound",
            "witness": witness,
        }
    if _non_duplicating(instance):
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": (
                "no rule copies a variable and no enumerated chain exceeds the initial-term "
                "successor-count bound"
            ),
        }
    return {
        "truth": "unstated",
        "counterexample": "",
        "theorem": "",
        "basis": "no chain longer than the initial-term bound found",
    }


def _rule1_terminal(instance: _Instance, catalog: str) -> dict[str, Any]:
    found = _first_base_survivor(instance)
    if found is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no base-rule step in the enumerated universe leaves a reducible term",
        }
    step, follow = found
    detail = f"the result {render_term(step.after)} still rewrites by {follow.rule}"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "the released payload can carry a redex",
    }


def _wrapper_normal_form(instance: _Instance, catalog: str) -> dict[str, Any]:
    step = _wrapper_inside_step(instance)
    if step is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no step in the enumerated universe rewrites inside the wrapper",
        }
    detail = "the rewrite happens inside the wrapper's argument"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "rewriting reaches the wrapper's argument",
    }


def _eq_diff_size_denied(instance: _Instance, catalog: str) -> dict[str, Any]:
    rule = next((item for item in instance.rules if item.name == "eq_diff"), None)
    if rule is None:
        return {
            "truth": "unstated",
            "counterexample": "",
            "theorem": "",
            "basis": "the instance carries no equality-difference rule",
        }
    step = _first_growth_step(instance, rule=rule.name)
    if step is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no equality-difference instance grows the term",
        }
    detail = f"size {_size(step.before)} -> {_size(step.after)}"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "the equality-difference rule grows the term, and it is not the recursive rule",
    }


def _step_root_only_basis(instance: _Instance, catalog: str) -> dict[str, Any]:
    return {
        "truth": "wrong_target",
        "counterexample": "",
        "theorem": "",
        "basis": "the item describes the literal root relation, which is not the scored contextual target",
    }


def _only_outermost_f_redexes(instance: _Instance, catalog: str) -> dict[str, Any]:
    term = _only_inner_redex_term(instance)
    if term is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "every enumerated redex sits at the root",
        }
    step = _one_step_results(instance, term)[0]
    detail = "the only redex sits strictly inside an argument"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "an argument position carries a redex",
    }


def _s_count_every_step_strict(instance: _Instance, catalog: str) -> dict[str, Any]:
    found = _first_failing_step(instance, "total_S", "whole_term", "none", "strict")
    if found is None:
        return {
            "truth": True,
            "counterexample": "",
            "theorem": "",
            "basis": "no step in the enumerated universe fails the total-S descent",
        }
    step, before, after = found
    detail = f"total S count {before} -> {after}, so the step does not strictly decrease"
    return {
        "truth": False,
        "counterexample": _text_counterexample(step, detail),
        "theorem": "",
        "basis": "the base rule releases a term whose S count already appears on the left",
    }


_PREMISE_DECISIONS = {
    "size_nonincreasing": _size_nonincreasing,
    "no_new_redexes": _no_new_redexes,
    "payload_shared_cancels": _payload_shared_cancels,
    "whole_term_multiset_decreases": _whole_term_multiset_decreases,
    "nonoverlap_determinism_wn_sn": _nonoverlap_determinism_wn_sn,
    "per_step_measure_decrease": _per_step_measure_decrease,
    "per_term_bound": _per_term_bound,
    "rule1_terminal": _rule1_terminal,
    "wrapper_normal_form": _wrapper_normal_form,
    "eq_diff_size_denied": _eq_diff_size_denied,
    "step_root_only_basis": _step_root_only_basis,
    "only_outermost_f_redexes": _only_outermost_f_redexes,
    "s_count_every_step_strict": _s_count_every_step_strict,
    "g_normal_form": _wrapper_normal_form,
}


def premise_truth(instance: Any, item: Any) -> dict[str, Any]:
    """Decide one catalog item for one instance with a computed counterexample."""

    try:
        frozen = _instance(instance)
    except _Unsupported as error:
        return {"truth": "unstated", "counterexample": "", "theorem": "", "basis": str(error)}
    name = str(item if item is not None else "").strip()
    catalog = _CATALOG_OF.get(frozen.key)
    if catalog is None:
        return {
            "truth": "unstated",
            "counterexample": "",
            "theorem": "",
            "basis": f"no premise catalog for {frozen.key}",
        }
    if name not in _CATALOG_ITEMS[catalog]:
        return {
            "truth": "unstated",
            "counterexample": "",
            "theorem": "",
            "basis": f"unknown catalog item {name}",
        }
    try:
        return dict(_PREMISE_DECISIONS[name](frozen, catalog))
    except _Unsupported as error:
        return {"truth": "unstated", "counterexample": "", "theorem": "", "basis": str(error)}


_DOMAIN_PATTERNS = (
    (
        "N_ge_2",
        r"at\s+least\s+2|>=\s*2|≥\s*2|greater\s+than\s+1|\{2,\}|\{2,\s*3,\s*\.\.\.\}",
    ),
    (
        "N_ge_1",
        r"positive\s+integers?|strictly\s+positive|at\s+least\s+1|>=\s*1|≥\s*1"
        r"|nonnegative\s+integers?\s+(?:greater|larger)\s+than\s+zero"
        r"|natural\s+numbers?\s+(?:greater|larger)\s+than\s+zero"
        r"|\bN\+|N\^\+|N⁺|N\s*\+\s|N_\{?>0\}?|N\s*>\s*0|ℕ\s*\+|\{1,\}|starting\s+at\s+1",
    ),
    (
        "N",
        r"natural\s+numbers?|non-?negative\s+integers?|\bN\b|\bnat\b|ℕ|\{0,\}|including\s+zero",
    ),
)

_AMBIGUOUS_DOMAIN = re.compile(
    r"positive\s+integers?[^.;]{0,40}(?:including\s+zero|non-?negative)"
    r"|non-?negative[^.;]{0,40}positive\s+integers?"
    r"|(?:either|both)\s+N\s+(?:and|or)\s+N\+?"
    r"|unclear|ambiguous|two\s+possible\s+domains",
    re.IGNORECASE,
)

_CONSTANT_VALUE = re.compile(
    r"[\[\|⟦]?\s*([A-Za-z][A-Za-z0-9_]*)\s*[\]\|⟧]?\s*(?:=|:=|↦|\u21a6|->|→)\s*(-?[0-9]+)"
)

_DOMAIN_LOWER = {"N": 0, "N_ge_1": 1, "N_ge_2": 2}


def _stated_domain(text: str) -> str:
    folded = _norm(text)
    if not folded:
        return ""
    if _AMBIGUOUS_DOMAIN.search(folded):
        return "ambiguous"
    for name, pattern in _DOMAIN_PATTERNS:
        if re.search(pattern, folded, re.IGNORECASE):
            return name
    return ""


def derive_carrier(domain_quote: Any, constants_quote: Any) -> dict[str, Any]:
    """Read the carrier from a stated domain phrase and stated constant values."""

    domain_text = str(domain_quote if domain_quote is not None else "")
    constants_text = str(constants_quote if constants_quote is not None else "")
    domain = _stated_domain(domain_text)
    values: list[tuple[str, int]] = [
        (match.group(1), int(match.group(2))) for match in _CONSTANT_VALUE.finditer(constants_text)
    ]
    smallest = min((value for _, value in values), default=None)
    if smallest is not None and smallest < 0:
        return {
            "carrier": "ambiguous",
            "stated_lower": None,
            "basis": f"a stated constant value is negative: {smallest}",
        }
    if domain == "ambiguous":
        return {
            "carrier": "ambiguous",
            "stated_lower": None,
            "basis": "the domain statement conflicts with itself",
        }
    stated_lower = (
        None
        if smallest is None
        else "N_ge_2"
        if smallest >= 2
        else "N_ge_1"
        if smallest == 1
        else "N"
    )
    if domain and smallest is not None and smallest < _DOMAIN_LOWER[domain]:
        return {
            "carrier": "ambiguous",
            "stated_lower": stated_lower,
            "basis": f"domain {domain} conflicts with the smallest constant value {smallest}",
        }
    if domain and stated_lower is not None:
        return {
            "carrier": domain,
            "stated_lower": stated_lower,
            "basis": f"domain {domain}; smallest constant value {smallest}",
        }
    if domain:
        return {
            "carrier": domain,
            "stated_lower": None,
            "basis": f"domain {domain}; no constant values stated",
        }
    if stated_lower is not None:
        names = ", ".join(f"[{symbol}]={value}" for symbol, value in values)
        return {
            "carrier": stated_lower,
            "stated_lower": stated_lower,
            "basis": f"domain unstated; smallest constant value {smallest} ({names})",
        }
    return {
        "carrier": "unstated",
        "stated_lower": None,
        "basis": "no domain phrase and no constant values stated",
    }


def constructors_nondecreasing(definitions: Any, lower: int) -> bool:
    """True when every constructor formula is non-decreasing in each argument.

    A definition is one typed polynomial definition of a canonical mathematical
    core.  A formula is non-decreasing in one parameter when its one-step
    difference in that parameter has no negative coefficient after every
    variable is shifted up to the stated lower bound.  The lower bound is the
    smallest value that terms take, so a positive verdict licenses checking the
    rules above that bound rather than above zero.
    """

    if not isinstance(definitions, list) or not definitions:
        return False
    for definition in definitions:
        if not isinstance(definition, dict):
            return False
        polynomial = poly_from_typed(definition.get("polynomial") or {})
        if polynomial is None:
            return False
        parameters = definition.get("canonical_parameters") or []
        if not isinstance(parameters, list):
            return False
        for parameter in parameters:
            bumped = poly_substitute(
                polynomial,
                {parameter: poly_add(poly_var(parameter), poly_const(1))},
            )
            difference = poly_sub(bumped, polynomial)
            shifted = poly_substitute(
                difference,
                {
                    variable: poly_add(poly_var(variable), poly_const(lower))
                    for variable in poly_vars(difference)
                },
            )
            if any(coefficient < 0 for coefficient in shifted.values()):
                return False
    return True


_WORD_BOUNDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

_BOUND_TEXT = re.compile(
    r"at\s+most\s+(?P<n>[0-9]{1,3}|zero|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"|length\s+(?:of\s+)?(?P<m>[0-9]{1,3})\s*(?:or\s+less|max)"
    r"|\b(?P<r>[0-9]{1,2})\s*(?:-|to)\s*(?P<s>[0-9]{1,2})\s+steps",
    re.IGNORECASE,
)

_TERMINATION_TEXT = re.compile(
    r"terminat|normaliz|normalis|strongly\s+normal|weakly\s+normal|no\s+infinite"
    r"|every\s+chain\s+(?:is\s+)?finite|finitely\s+many\s+steps|well-founded"
    r"|reductions?\s+(?:occur|happen)\s+only\s+at\s+the\s+root",
    re.IGNORECASE,
)


def _claim_bound(text: str) -> int | None:
    match = _BOUND_TEXT.search(text)
    if match is None:
        return None
    for group in ("n", "m"):
        value = match.group(group)
        if value:
            if value.isdigit():
                return int(value)
            return _WORD_BOUNDS.get(value.lower())
    first, second = match.group("r"), match.group("s")
    if first and second:
        return max(int(first), int(second))
    return None


def _root_rules(instance: _Instance) -> tuple[dict[str, Any], ...]:
    rules: list[dict[str, Any]] = []
    for rule in instance.rules:
        item: dict[str, Any] = {"name": rule.name, "lhs": rule.lhs, "rhs": rule.rhs}
        if rule.guard is not None:
            item["guard"] = {"predicate": rule.guard[0], "variables": list(rule.guard[1])}
        rules.append(item)
    return tuple(rules)


def root_only_decision(instance: Any, claim: Any) -> dict[str, Any]:
    """Decide a root-relation claim for the Test 01 kernel."""

    try:
        frozen = _instance(instance)
    except _Unsupported as error:
        return {"verdict": "UNSUPPORTED", "reason": str(error)}
    if frozen.key not in {"test01-ko7", "test01-fruit"}:
        return {"verdict": "UNSUPPORTED", "reason": "instance_out_of_scope"}
    if not isinstance(claim, dict):
        return {"verdict": "UNSUPPORTED", "reason": "claim_malformed"}
    kind = _norm(claim.get("kind"))
    if kind == "bounded_chain_length":
        bound = claim.get("bound")
        if isinstance(bound, bool) or not isinstance(bound, int):
            bound = _claim_bound(str(claim.get("quote") or claim.get("definition") or ""))
        if bound is None or bound < 0:
            return {"verdict": "UNSUPPORTED", "reason": "claimed_bound_unreadable"}
        payload: dict[str, Any] = {
            "relation": "Step",
            "principle": "every root step yields a proper subterm or a root-normal term",
            "definition": f"the maximum length of any root reduction chain is at most {bound}",
        }
    elif kind in {"root_only_argument", "root_control_proof"}:
        nested = claim.get("payload")
        if isinstance(nested, dict) and nested:
            payload = dict(nested)
        else:
            quote = str(claim.get("quote") or "")
            definition = str(claim.get("definition") or "")
            bound = _claim_bound(quote) or _claim_bound(definition)
            if bound is not None:
                payload = {
                    "relation": "Step",
                    "principle": "every root step yields a proper subterm or a root-normal term",
                    "definition": (
                        f"the maximum length of any root reduction chain is at most {bound}"
                    ),
                }
            elif _TERMINATION_TEXT.search(quote) or _TERMINATION_TEXT.search(definition):
                payload = {
                    "relation": "Step",
                    "principle": "every root step yields a proper subterm or a root-normal term",
                }
            else:
                return {"verdict": "UNSUPPORTED", "reason": "root_only_quote_untyped"}
    else:
        return {"verdict": "UNSUPPORTED", "reason": f"claim_kind_out_of_scope[{kind or 'empty'}]"}
    try:
        from .checkers import _root_control_field_type, root_control_decision
    except ImportError as error:
        return {"verdict": "UNSUPPORTED", "reason": f"checker_unavailable[{error}]"}
    rules = _root_rules(frozen)
    symbols = set(frozen.symbols)
    decision = root_control_decision(rules, symbols)
    if decision.get("status") != "ok":
        return {"verdict": "UNSUPPORTED", "reason": str(decision.get("reason"))}
    reading = check_payload(payload, rules, symbols, decision, _root_control_field_type)
    verdict = str(reading.get("verdict"))
    certificate = {
        "certificate_type": "root-control-source-obligations/v1",
        "decision_source": "contract_rules_and_all_source_readings",
        "input_independent": False,
        "source_objects": {"representative": {"kind": "root_control_proof", "payload": payload}},
        "reading_decisions": {"representative": reading},
        "rule_table": decision.get("table"),
    }
    result: dict[str, Any] = {
        "verdict": verdict,
        "detail": str(reading.get("detail") or ""),
        "certificate": certificate,
    }
    if "witness" in reading:
        witness = reading["witness"]
        result["witness"] = witness
        if witness.get("type") == "projection_rule_arbitrarily_long_root_chains":
            result["counterexample"] = (
                f"root chains longer than {witness.get('claimed_bound')} exist: "
                + " -> ".join(witness.get("sample_chain") or [])
            )
    if verdict == "PASS":
        result["theorem"] = "root_control_rule_table_holds"
        result["basis"] = (
            "every root rule yields a proper subterm or a root-normal term, so the "
            "literal root relation is well-founded"
        )
    return result
