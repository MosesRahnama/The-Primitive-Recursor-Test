"""Exact, contract-generic mathematical decisions used by TGC v3.

This module deliberately consumes only typed canonical payloads plus the contract's
signature/rule table.  It never reads response prose and never guesses omitted data.

Two asymmetric soundness rules are central:

* a partial path precedence denotes the existential set of total extensions; the
  finite extension search is exhaustive;
* a polynomial construction may PASS by a symbolic proof on an over-approximation
  of the generated carrier, but REFUTED requires an explicit valuation represented
  by ground terms of the declared signature.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from itertools import combinations, permutations, product
from pathlib import Path
from typing import Any, Iterable

from .natural_power import (
    NaturalExpr,
    natural_power_eval,
    natural_power_from_typed,
    natural_power_substitute,
    natural_power_variables,
)

Term = tuple[str, tuple["Term", ...]]
Monomial = tuple[tuple[str, int], ...]
Polynomial = dict[Monomial, int]


def parse_term(text: str) -> Term:
    text = text.strip()
    if not text:
        raise ValueError("empty term")
    if "(" not in text:
        if not text.replace("_", "").isalnum():
            raise ValueError(f"bad term token {text!r}")
        return (text, ())
    head, rest = text.split("(", 1)
    head = head.strip()
    if not head or not rest.endswith(")"):
        raise ValueError(f"unbalanced term {text!r}")
    body = rest[:-1]
    pieces: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"unbalanced term {text!r}")
        if char == "," and depth == 0:
            pieces.append("".join(current))
            current = []
        else:
            current.append(char)
    if depth != 0:
        raise ValueError(f"unbalanced term {text!r}")
    if current or body:
        pieces.append("".join(current))
    return (head, tuple(parse_term(piece) for piece in pieces if piece.strip()))


def render_term(term: Term) -> str:
    head, args = term
    if not args:
        return head
    return f"{head}({','.join(render_term(arg) for arg in args)})"


def _symbol_occurrences(term: Term, symbol: str) -> list[Term]:
    """Return every subterm rooted at ``symbol``, in preorder."""

    head, arguments = term
    output = [term] if head == symbol else []
    for argument in arguments:
        output.extend(_symbol_occurrences(argument, symbol))
    return output


def _proper_subterm_paths(term: Term, wanted: Term) -> list[list[int]]:
    """All one-based paths at which ``wanted`` is a proper subterm."""

    output: list[list[int]] = []
    for index, argument in enumerate(term[1], start=1):
        if argument == wanted:
            output.append([index])
        output.extend(
            [[index, *path] for path in _proper_subterm_paths(argument, wanted)]
        )
    return output


def _removed_heads_on_path(term: Term, path: list[int]) -> list[str]:
    """Heads removed when descending from ``term`` to the subterm at ``path``."""

    current = term
    heads: list[str] = []
    for one_based in path:
        heads.append(current[0])
        if one_based < 1 or one_based > len(current[1]):
            return []
        current = current[1][one_based - 1]
    return heads


def call_measure_dependency_pair_decision(
    mathematical_core: dict[str, Any],
    checker_object: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
    registered_measures: set[str],
) -> dict[str, Any]:
    """Certify the narrow recursive-call proper-subterm fragment.

    This is intentionally not a termination proof for the source TRS.  It
    checks only the response's typed call-level object: one stated argument of
    the contract's unique self-recursive symbol strictly descends to a proper
    subterm at every recursive call.  Transport back to full contextual SN is
    handled separately by a verified archived authority.

    The source kind remains ``call_measure``.  The named ``measure`` controls
    the strictness test: size/depth use proper-subterm descent, while a
    constructor count must remove that constructor on the witness path.
    Omission has the contract-wide default ``size``.  Unknown
    fields, a checker/core mismatch, a missing argument, an unregistered
    measure, mutual/self-recursive ambiguity, and any non-subterm call all fail
    closed instead of falling through to the historical pilot checker.
    """

    if mathematical_core.get("kind") != "call_measure":
        return {"status": "not_applicable"}
    core_payload = mathematical_core.get("payload")
    checker_payload = checker_object.get("payload")
    if not isinstance(checker_payload, dict):
        return {"status": "unsupported", "reason": "call_measure_payload_missing"}
    if checker_payload.get("scope") != "dependency_pair":
        return {"status": "not_applicable"}
    if not isinstance(core_payload, dict):
        return {"status": "unsupported", "reason": "call_measure_payload_missing"}
    if core_payload != checker_payload:
        return {
            "status": "unsupported",
            "reason": "call_measure_core_checker_payload_mismatch",
        }
    allowed_fields = {"scope", "argument", "measure", "measure_mode"}
    extra_fields = sorted(set(checker_payload) - allowed_fields)
    if extra_fields:
        return {
            "status": "unsupported",
            "reason": f"call_measure_dependency_pair_extra_fields[{extra_fields}]",
        }
    argument = checker_payload.get("argument")
    if not isinstance(argument, int) or isinstance(argument, bool) or argument < 1:
        return {
            "status": "unsupported",
            "reason": "call_measure_dependency_pair_argument_missing_or_invalid",
        }
    measure_was_defaulted = "measure" not in checker_payload
    measure = checker_payload.get("measure", "size")
    if not isinstance(measure, str) or measure not in registered_measures:
        return {
            "status": "unsupported",
            "reason": f"call_measure_dependency_pair_measure_unregistered[{measure!r}]",
        }
    if measure_was_defaulted and "size" not in registered_measures:
        return {
            "status": "unsupported",
            "reason": "call_measure_dependency_pair_default_size_unregistered",
        }
    counted_symbol: str | None = None
    if measure not in {"size", "depth"}:
        if measure.endswith("_count"):
            candidate = measure[: -len("_count")]
            if candidate in signature:
                counted_symbol = candidate
        if counted_symbol is None:
            return {
                "status": "unsupported",
                "reason": (
                    "call_measure_dependency_pair_measure_semantics_unregistered"
                    f"[{measure}]"
                ),
            }

    mode = checker_payload.get("measure_mode", "total")
    if (not isinstance(mode, str) or mode not in {"total", "leading_chain"}
            or ("measure_mode" in checker_payload and counted_symbol is None)
            or (mode == "leading_chain" and len(signature[counted_symbol]) != 1)):
        return {"status": "unsupported", "reason": "call_measure_mode_unregistered"}

    parsed_rules: list[tuple[dict[str, Any], Term, Term]] = []
    try:
        for rule in rules:
            lhs = parse_term(str(rule["lhs"]))
            rhs = parse_term(str(rule["rhs"]))
            if lhs[0] not in signature or len(lhs[1]) != len(signature[lhs[0]]):
                return {
                    "status": "unsupported",
                    "reason": f"contract_lhs_shape_invalid[{rule.get('name')}]",
                }
            parsed_rules.append((rule, lhs, rhs))
    except (KeyError, TypeError, ValueError) as error:
        return {
            "status": "unsupported",
            "reason": f"contract_rule_parse_failed[{type(error).__name__}:{error}]",
        }

    self_recursive_symbols = sorted(
        {
            lhs[0]
            for _, lhs, rhs in parsed_rules
            if _symbol_occurrences(rhs, lhs[0])
        }
    )
    if len(self_recursive_symbols) != 1:
        return {
            "status": "unsupported",
            "reason": (
                "call_measure_recursive_symbol_ambiguous"
                f"[{self_recursive_symbols}]"
            ),
        }
    recursive_symbol = self_recursive_symbols[0]
    arity = len(signature.get(recursive_symbol, []))
    if argument > arity:
        return {
            "status": "unsupported",
            "reason": (
                "call_measure_dependency_pair_argument_out_of_range"
                f"[{recursive_symbol}:{argument}>{arity}]"
            ),
        }

    table: list[dict[str, Any]] = []
    recursive_call_total = 0
    every_call_descends = True
    for rule, lhs, rhs in parsed_rules:
        if lhs[0] != recursive_symbol:
            continue
        calls = _symbol_occurrences(rhs, recursive_symbol)
        call_rows: list[dict[str, Any]] = []
        for call in calls:
            recursive_call_total += 1
            if len(call[1]) != arity:
                return {
                    "status": "unsupported",
                    "reason": f"recursive_call_arity_mismatch[{rule.get('name')}]",
                }
            lhs_argument = lhs[1][argument - 1]
            call_argument = call[1][argument - 1]
            paths = _proper_subterm_paths(lhs_argument, call_argument)
            strict_paths = (
                paths
                if counted_symbol is None
                else [
                    path
                    for path in paths
                    if counted_symbol in _removed_heads_on_path(lhs_argument, path)
                ]
            )
            if mode == "leading_chain":
                strict_paths = [path for path in strict_paths
                                if all(head == counted_symbol for head in
                                       _removed_heads_on_path(lhs_argument, path))]
            descends = bool(strict_paths)
            every_call_descends = every_call_descends and descends
            call_rows.append(
                {
                    "call": render_term(call),
                    "lhs_argument": render_term(lhs_argument),
                    "call_argument": render_term(call_argument),
                    "proper_subterm": bool(paths),
                    "proper_subterm_paths_one_based": paths,
                    "measure_strict": descends,
                    "measure_strict_paths_one_based": strict_paths,
                }
            )
        table.append(
            {
                "rule": str(rule.get("name") or ""),
                "lhs": str(rule["lhs"]),
                "rhs": str(rule["rhs"]),
                "recursive_call_count": len(calls),
                "calls": call_rows,
            }
        )
    if recursive_call_total == 0:
        return {
            "status": "unsupported",
            "reason": "call_measure_no_recursive_calls",
        }
    if not every_call_descends:
        identical = next((
            {"rule": row["rule"], **call}
            for row in table for call in row["calls"]
            if call["lhs_argument"] == call["call_argument"]
        ), None)
        if identical is not None:
            return {
                "status": "ok", "holds": False,
                "reason": "recursive_argument_identical_before_and_after",
                "decision_family": "dependency_pair_argument_identity_refutation",
                "recursive_symbol": recursive_symbol, "argument": argument,
                "measure": measure, "rule_table": table,
                "witness": {"type": "identical_recursive_argument", **identical},
            }
        return {
            "status": "unsupported",
            "reason": (
                "call_measure_named_count_not_proved_strict"
                if counted_symbol is not None
                else "call_measure_argument_not_proved_proper_subterm"
            ),
            "decision_family": "dependency_pair_argument_proper_subterm",
            "recursive_symbol": recursive_symbol,
            "argument": argument,
            "measure": measure,
            "counted_symbol": counted_symbol,
            "measure_was_defaulted": measure_was_defaulted,
            "recursive_call_total": recursive_call_total,
            "rule_table": table,
        }
    return {
        "status": "ok",
        "holds": True,
        "reason": "every_recursive_call_argument_is_a_strict_proper_subterm",
        "decision_family": "dependency_pair_argument_proper_subterm",
        "recursive_symbol": recursive_symbol,
        "argument": argument,
        "measure": measure,
        "counted_symbol": counted_symbol,
        "measure_mode": mode,
        "measure_was_defaulted": measure_was_defaulted,
        "strict_proper_subterm_descent": True,
        "recursive_call_total": recursive_call_total,
        "rule_table": table,
    }


def _is_variable(term: Term, signature: set[str]) -> bool:
    return not term[1] and term[0] not in signature


def _transitive_closure(edges: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    closure = set(edges)
    changed = True
    while changed:
        changed = False
        additions = {
            (left, right)
            for left, middle in closure
            for middle_2, right in closure
            if middle == middle_2 and left != right and (left, right) not in closure
        }
        if additions:
            closure.update(additions)
            changed = True
    return closure


def _multiset_strict(
    left: tuple[Term, ...],
    right: tuple[Term, ...],
    greater: Any,
    equivalent: Any = None,
) -> bool:
    """Decide the finite multiset extension of a strict term relation.

    Equal elements are cancelled modulo ``equivalent`` (syntactic equality by
    default). For a strict order compatible with that equivalence, cancelling
    every common element decides the Dershowitz-Manna extension exactly.
    """

    same = equivalent or (lambda first, second: first == second)
    left_remaining = list(left)
    right_remaining: list[Term] = []
    for item in right:
        for index, candidate in enumerate(left_remaining):
            if same(candidate, item):
                del left_remaining[index]
                break
        else:
            right_remaining.append(item)
    if not left_remaining:
        return False
    return all(
        any(greater(candidate, target) for candidate in left_remaining)
        for target in right_remaining
    )


def _permutative_equivalent(left: Term, right: Term, signature: set[str]) -> bool:
    """Term equality modulo permuting the arguments of multiset-status symbols."""

    if left == right:
        return True
    if _is_variable(left, signature) or _is_variable(right, signature):
        return False
    left_head, left_args = left
    right_head, right_args = right
    if left_head != right_head or len(left_args) != len(right_args):
        return False
    remaining = list(right_args)
    for argument in left_args:
        for index, candidate in enumerate(remaining):
            if _permutative_equivalent(argument, candidate, signature):
                del remaining[index]
                break
        else:
            return False
    return True


def _symbol_arities(rules: tuple[dict[str, Any], ...], signature: set[str]) -> dict[str, int]:
    arities: dict[str, int] = {}

    def visit(term: Term) -> None:
        head, arguments = term
        if head in signature:
            arities.setdefault(head, len(arguments))
        for argument in arguments:
            visit(argument)

    for rule in rules:
        visit(parse_term(str(rule["lhs"])))
        visit(parse_term(str(rule["rhs"])))
    return arities


def _lpo_rule_table(
    precedence: set[tuple[str, str]],
    rules: tuple[dict[str, Any], ...],
    signature: set[str],
    argument_order: dict[str, list[int]] | None = None,
    status_mode: str = "lex",
) -> list[dict[str, Any]]:
    """Orient rules under LPO (lex) or RPO (multiset) status.

    ``argument_order`` maps a symbol to its stated argument comparison order;
    every other symbol compares left to right. Multiset status compares terms
    modulo argument permutation.
    """

    orders = dict(argument_order or {})
    permutative = status_mode == "multiset"

    def equivalent(left: Term, right: Term) -> bool:
        if permutative:
            return _permutative_equivalent(left, right, signature)
        return left == right

    @lru_cache(maxsize=None)
    def gt(left: Term, right: Term) -> bool:
        if _is_variable(left, signature) or equivalent(left, right):
            return False
        left_head, left_args = left
        right_head, right_args = right

        # Subterm property, recursively: an immediate subterm may itself dominate
        # the target.  This also handles variables occurring in the left term.
        if any(equivalent(argument, right) or gt(argument, right) for argument in left_args):
            return True
        if _is_variable(right, signature):
            return False

        # Every argument of the right term must be smaller than the whole left.
        if not all(gt(left, argument) for argument in right_args):
            return False
        if (left_head, right_head) in precedence:
            return True
        if left_head != right_head or len(left_args) != len(right_args):
            return False
        if permutative:
            return _multiset_strict(left_args, right_args, gt, equivalent)
        # Lexicographic status. Equality is required before the first strict
        # component; the all-right-arguments side condition above is the
        # standard LPO embedding condition.
        indices = list(range(len(left_args)))
        stated = orders.get(left_head)
        if stated:
            selected = [index - 1 for index in stated]
            indices = selected + [index for index in indices if index not in selected]
        for index in indices:
            left_arg, right_arg = left_args[index], right_args[index]
            if equivalent(left_arg, right_arg):
                continue
            return gt(left_arg, right_arg)
        return False

    table: list[dict[str, Any]] = []
    for rule in rules:
        lhs = parse_term(str(rule["lhs"]))
        rhs = parse_term(str(rule["rhs"]))
        table.append(
            {
                "rule": str(rule.get("name") or ""),
                "lhs": str(rule["lhs"]),
                "rhs": str(rule["rhs"]),
                "oriented": gt(lhs, rhs),
            }
        )
    return table


def path_order_decision(
    mathematical_core: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
    checker_object: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide supported LPO/RPO status fragments source-faithfully.

    The displayed precedence is never completed unless the response explicitly
    licenses completion. ``exact_partial`` therefore means exactly the stated
    strict relation plus transitive closure; ``exists_total_extension`` and
    ``forall_total_extensions`` quantify over the finite set of total extensions.

    The completion quantifier is a READING of the response, not a mathematical
    object, so the canonicalizer deliberately keeps it out of the mathematical
    core: two passes that transcribe one precedence but disagree about whether
    completion is licensed must still form ONE mathematical claim.  The decision
    therefore takes the quantifier from the consensus CHECKER payload (the
    channel that does carry it) and falls back to the core only for callers
    that inline both in one payload.
    """

    kind = mathematical_core.get("kind")
    if kind not in {"lpo", "rpo"}:
        return {"status": "not_applicable"}
    payload = mathematical_core.get("payload") or {}
    checker_payload = (checker_object or {}).get("payload") or {}
    status = payload.get("status") or {"mode": "unspecified"}
    status_mode = status.get("mode", "unspecified")
    argument_order = status.get("argument_order")
    if status_mode == "unparseable":
        return {"status": "unsupported", "reason": "path_status_unparseable"}
    supported_modes = {"lex", "unspecified"}
    if kind == "rpo":
        supported_modes.add("multiset")
    if status_mode not in supported_modes:
        if kind == "lpo" and status_mode == "multiset":
            return {
                "status": "unsupported",
                "reason": "lpo_multiset_status_not_implemented",
            }
        return {
            "status": "unsupported",
            "reason": f"{kind}_status_not_implemented[{status_mode}]",
        }
    if (
        argument_order is not None
        and (
            not isinstance(argument_order, list)
            or not argument_order
            or any(type(index) is not int or index < 1 for index in argument_order)
            or len(set(argument_order)) != len(argument_order)
        )
    ):
        return {
            "status": "unsupported",
            "reason": f"path_argument_order_malformed[{argument_order}]",
        }
    # A stated argument order binds to the one symbol whose arity admits it.
    # The identity prefix [1], [1, 2], ... is ordinary left-to-right lex for
    # every symbol. No order is silently dropped: an order no symbol admits,
    # or one several symbols admit, is outside the supported fragment.
    argument_orders: dict[str, list[int]] = {}
    if argument_order is not None and argument_order != list(
        range(1, len(argument_order) + 1)
    ):
        if status_mode == "multiset":
            return {
                "status": "unsupported",
                "reason": "path_argument_order_with_multiset_status",
            }
        arities = _symbol_arities(rules, signature_symbols)
        needed = max(argument_order)
        candidates = sorted(
            symbol for symbol, arity in arities.items() if arity >= max(needed, 2)
        )
        if not candidates:
            return {
                "status": "unsupported",
                "reason": f"path_argument_order_inapplicable[{argument_order}]",
            }
        if len(candidates) > 1:
            return {
                "status": "unsupported",
                "reason": (
                    "path_argument_order_symbol_ambiguous"
                    f"[{argument_order}:{','.join(candidates)}]"
                ),
            }
        argument_orders[candidates[0]] = list(argument_order)

    quantifier = payload.get("precedence_quantifier")
    if quantifier is None:
        quantifier = checker_payload.get("precedence_quantifier")
    if quantifier not in {
        "exact_partial",
        "exists_total_extension",
        "forall_total_extensions",
        "explicit_total",
    }:
        return {
            "status": "unsupported",
            "reason": f"precedence_quantifier_unsupported[{quantifier}]",
        }

    precedence = payload.get("precedence") or {}
    if precedence.get("status") != "ok":
        return {
            "status": "unsupported",
            "reason": f"precedence_{precedence.get('reason', 'unparseable')}",
        }
    direct_items = precedence.get("direct_relations") or []
    direct: set[tuple[str, str]] = set()
    for item in direct_items:
        if not isinstance(item, dict):
            return {"status": "unsupported", "reason": "malformed_precedence_item"}
        higher, lower = item.get("higher"), item.get("lower")
        if higher not in signature_symbols or lower not in signature_symbols:
            return {"status": "unsupported", "reason": "precedence_unknown_symbol"}
        if higher == lower:
            return {"status": "unsupported", "reason": "precedence_irreflexive_violation"}
        direct.add((str(higher), str(lower)))

    closure = _transitive_closure(direct)
    if any((symbol, symbol) in closure for symbol in signature_symbols):
        return {"status": "unsupported", "reason": "precedence_cycle"}
    stated_table = _lpo_rule_table(
        closure,
        rules,
        signature_symbols,
        argument_orders,
        status_mode,
    )
    stated_orients = all(row["oriented"] for row in stated_table)
    symbols = tuple(sorted(signature_symbols))
    relation_is_total = all(
        left == right
        or (left, right) in closure
        or (right, left) in closure
        for left in symbols
        for right in symbols
    )
    common = {
        "quantifier": quantifier,
        "relation_is_total": relation_is_total,
        "stated_relation_orients": stated_orients,
        "stated_rule_table": stated_table,
        "direct_relations": [
            {"higher": higher, "lower": lower}
            for higher, lower in sorted(direct)
        ],
        "argument_order": argument_order,
        "argument_order_binding": argument_orders,
    }

    if quantifier == "exact_partial":
        return {
            "status": "ok",
            "holds": stated_orients,
            "semantics": "exact_stated_partial_precedence",
            "total_extensions": None,
            "orienting_extensions": None,
            "first_witness_order": None,
            **common,
        }

    if quantifier == "explicit_total":
        if not relation_is_total:
            return {
                "status": "unsupported",
                "reason": "declared_total_precedence_is_incomplete",
                **common,
            }
        return {
            "status": "ok",
            "holds": stated_orients,
            "semantics": "explicit_total_precedence",
            "total_extensions": 1,
            "orienting_extensions": int(stated_orients),
            "first_witness_order": None,
            **common,
        }

    extending = 0
    orienting = 0
    first_witness: tuple[str, ...] | None = None
    failure_histogram: dict[str, int] = {}
    for order in permutations(symbols):
        total = {
            (order[i], order[j])
            for i in range(len(order))
            for j in range(i + 1, len(order))
        }
        if not direct <= total:
            continue
        extending += 1
        table = _lpo_rule_table(
            total,
            rules,
            signature_symbols,
            argument_orders,
            status_mode,
        )
        failing = [row["rule"] for row in table if not row["oriented"]]
        if not failing:
            orienting += 1
            if first_witness is None:
                first_witness = order
        else:
            for name in failing:
                failure_histogram[name] = failure_histogram.get(name, 0) + 1
    if extending == 0:
        return {"status": "unsupported", "reason": "no_total_extension", **common}

    holds = (
        orienting > 0
        if quantifier == "exists_total_extension"
        else orienting == extending
    )
    return {
        "status": "ok",
        "holds": holds,
        "semantics": quantifier,
        "total_extensions": extending,
        "orienting_extensions": orienting,
        "first_witness_order": list(first_witness) if first_witness else None,
        "failure_histogram": dict(sorted(failure_histogram.items())),
        **common,
    }

def _clean(poly: Polynomial) -> Polynomial:
    return {monomial: coefficient for monomial, coefficient in poly.items() if coefficient}


def poly_const(value: int) -> Polynomial:
    return {(): int(value)} if value else {}


def poly_var(name: str) -> Polynomial:
    return {((name, 1),): 1}


def poly_add(left: Polynomial, right: Polynomial) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in right.items():
        result[monomial] = result.get(monomial, 0) + coefficient
    return _clean(result)


def poly_scale(poly: Polynomial, factor: int) -> Polynomial:
    return _clean({monomial: coefficient * factor for monomial, coefficient in poly.items()})


def poly_sub(left: Polynomial, right: Polynomial) -> Polynomial:
    return poly_add(left, poly_scale(right, -1))


def poly_mul(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            powers = dict(left_monomial)
            for variable, exponent in right_monomial:
                powers[variable] = powers.get(variable, 0) + exponent
            monomial = tuple(sorted(powers.items()))
            result[monomial] = (
                result.get(monomial, 0) + left_coefficient * right_coefficient
            )
    return _clean(result)


def poly_pow(poly: Polynomial, exponent: int) -> Polynomial:
    if exponent < 0:
        raise ValueError("negative polynomial exponent")
    result = poly_const(1)
    base = poly
    power = exponent
    while power:
        if power & 1:
            result = poly_mul(result, base)
        base = poly_mul(base, base)
        power >>= 1
    return result


def poly_vars(poly: Polynomial) -> set[str]:
    return {variable for monomial in poly for variable, _ in monomial}


def poly_substitute(poly: Polynomial, mapping: dict[str, Polynomial]) -> Polynomial:
    result: Polynomial = {}
    for monomial, coefficient in poly.items():
        term = poly_const(coefficient)
        for variable, exponent in monomial:
            term = poly_mul(
                term,
                poly_pow(mapping.get(variable, poly_var(variable)), exponent),
            )
        result = poly_add(result, term)
    return result


def poly_eval(poly: Polynomial, point: dict[str, int]) -> int:
    total = 0
    for monomial, coefficient in poly.items():
        value = coefficient
        for variable, exponent in monomial:
            value *= int(point.get(variable, 0)) ** exponent
        total += value
    return total


def poly_from_typed(value: dict[str, Any]) -> Polynomial | None:
    terms = value.get("terms")
    if not isinstance(terms, list):
        return None
    result: Polynomial = {}
    for term in terms:
        if not isinstance(term, dict):
            return None
        coefficient = term.get("coefficient")
        powers = term.get("powers")
        if not isinstance(coefficient, int) or coefficient < 0 or not isinstance(powers, list):
            return None
        monomial_parts: list[tuple[str, int]] = []
        for power in powers:
            if not isinstance(power, dict):
                return None
            variable, exponent = power.get("variable"), power.get("exponent")
            if not isinstance(variable, str) or not variable:
                return None
            if not isinstance(exponent, int) or exponent < 1:
                return None
            monomial_parts.append((variable, exponent))
        monomial = tuple(sorted(monomial_parts))
        result[monomial] = result.get(monomial, 0) + coefficient
    return _clean(result)


def _coefficient_dominates(poly: Polynomial, margin: int, lower: int) -> bool:
    shifted = poly_substitute(
        poly,
        {
            variable: poly_add(poly_var(variable), poly_const(lower))
            for variable in poly_vars(poly)
        },
    )
    required = poly_sub(shifted, poly_const(margin))
    return all(coefficient >= 0 for coefficient in required.values())


def _typed_interpretation(
    mathematical_core: dict[str, Any],
    signature: dict[str, list[str]],
) -> tuple[dict[str, tuple[tuple[str, ...], Polynomial]], str | None]:
    payload = mathematical_core.get("payload") or {}
    definitions = payload.get("definitions")
    if not isinstance(definitions, list):
        return {}, "typed_definitions_missing"
    interpretation: dict[str, tuple[tuple[str, ...], Polynomial]] = {}
    for definition in definitions:
        if not isinstance(definition, dict) or definition.get("status") != "ok":
            return {}, "definition_unparseable"
        symbol = definition.get("symbol")
        parameters = definition.get("canonical_parameters")
        polynomial = poly_from_typed(definition.get("polynomial") or {})
        if symbol not in signature or not isinstance(parameters, list) or polynomial is None:
            return {}, "definition_shape_invalid"
        expected = tuple(signature[str(symbol)])
        if tuple(parameters) != expected:
            return {}, f"definition_parameters_mismatch[{symbol}]"
        if symbol in interpretation:
            return {}, f"duplicate_definition[{symbol}]"
        if not poly_vars(polynomial) <= set(expected):
            return {}, f"definition_unknown_variable[{symbol}]"
        interpretation[str(symbol)] = (expected, polynomial)
    missing = sorted(set(signature) - set(interpretation))
    extra = sorted(set(interpretation) - set(signature))
    if missing or extra:
        return {}, f"definition_signature_mismatch[missing={missing},extra={extra}]"
    return interpretation, None


def _apply_interpretation(
    symbol: str,
    arguments: tuple[Polynomial, ...],
    interpretation: dict[str, tuple[tuple[str, ...], Polynomial]],
) -> Polynomial:
    parameters, polynomial = interpretation[symbol]
    if len(parameters) != len(arguments):
        raise ValueError(f"arity mismatch for {symbol}")
    return poly_substitute(polynomial, dict(zip(parameters, arguments)))


def _interpret_term(
    term: Term,
    interpretation: dict[str, tuple[tuple[str, ...], Polynomial]],
    signature_symbols: set[str],
) -> Polynomial:
    head, args = term
    if not args and head not in signature_symbols:
        return poly_var(head)
    if head not in interpretation:
        raise KeyError(head)
    return _apply_interpretation(
        head,
        tuple(_interpret_term(arg, interpretation, signature_symbols) for arg in args),
        interpretation,
    )


def _short_ground(symbol: str, arguments: tuple[str, ...], limit: int = 240) -> str:
    value = symbol if not arguments else f"{symbol}({','.join(arguments)})"
    return value if len(value) <= limit else value[: limit - 3] + "..."


def generated_minimum(
    interpretation: dict[str, tuple[tuple[str, ...], Polynomial]],
) -> tuple[int, str] | None:
    """Exact minimum value of the one-sorted ground subalgebra.

    Nonnegative polynomials are monotone.  Starting at the least constant image
    and repeatedly evaluating every operation at the current least value reaches
    the least fixed point.  Each decrease is represented by a ground term, while
    the fixed-point inequality proves every ground term has value at least it.
    """

    constants: list[tuple[int, str]] = []
    for symbol, (parameters, polynomial) in interpretation.items():
        if not parameters:
            constants.append((poly_eval(polynomial, {}), symbol))
    if not constants:
        return None
    minimum, witness = min(constants, key=lambda item: (item[0], item[1]))
    while True:
        best = (minimum, witness)
        for symbol, (parameters, polynomial) in sorted(interpretation.items()):
            if not parameters:
                continue
            value = poly_eval(polynomial, {parameter: minimum for parameter in parameters})
            if value < best[0]:
                best = (
                    value,
                    _short_ground(symbol, tuple(witness for _ in parameters)),
                )
        if best[0] >= minimum:
            return minimum, witness
        minimum, witness = best


@dataclass(frozen=True)
class ReachableSample:
    values: tuple[int, ...]
    witnesses: dict[int, str]
    cap: int
    truncated: bool
    exact: bool


def reachable_ground_sample(
    interpretation: dict[str, tuple[tuple[str, ...], Polynomial]],
    *,
    cap: int = 32,
) -> ReachableSample:
    witnesses: dict[int, str] = {}
    for symbol, (parameters, polynomial) in sorted(interpretation.items()):
        if not parameters:
            value = poly_eval(polynomial, {})
            if value <= cap:
                witnesses.setdefault(value, symbol)
    if not witnesses:
        return ReachableSample((), {}, cap, True, False)
    truncated = False
    # At most cap+1 distinct nonnegative values can enter the sample.  A full
    # closure round that adds nothing is therefore a deterministic fixed point.
    for _ in range(cap + 2):
        before = len(witnesses)
        current = tuple(sorted(witnesses))
        additions: dict[int, str] = {}
        for symbol, (parameters, polynomial) in sorted(interpretation.items()):
            arity = len(parameters)
            if not arity:
                continue
            for values in product(current, repeat=arity):
                point = dict(zip(parameters, values))
                output = poly_eval(polynomial, point)
                if output > cap:
                    truncated = True
                    continue
                if output not in witnesses and output not in additions:
                    arguments = tuple(witnesses[value] for value in values)
                    additions[output] = _short_ground(symbol, arguments)
        witnesses.update(additions)
        if len(witnesses) == before:
            return ReachableSample(
                tuple(sorted(witnesses)),
                dict(sorted(witnesses.items())),
                cap,
                truncated,
                not truncated,
            )
    return ReachableSample(
        tuple(sorted(witnesses)),
        dict(sorted(witnesses.items())),
        cap,
        True,
        False,
    )


def _monotonicity_witness(
    parameters: tuple[str, ...],
    polynomial: Polynomial,
    argument_index: int,
    sample: ReachableSample,
) -> dict[str, Any] | None:
    values = sample.values
    if len(values) < 2:
        return None
    for base in product(values, repeat=len(parameters)):
        current = base[argument_index]
        larger = next((value for value in values if value > current), None)
        if larger is None:
            continue
        bumped = list(base)
        bumped[argument_index] = larger
        before = poly_eval(polynomial, dict(zip(parameters, base)))
        after = poly_eval(polynomial, dict(zip(parameters, bumped)))
        if after <= before:
            return {
                "arguments_before": list(base),
                "arguments_after": bumped,
                "ground_terms_before": [sample.witnesses[value] for value in base],
                "ground_terms_after": [sample.witnesses[value] for value in bumped],
                "value_before": before,
                "value_after": after,
            }
    return None


def _declared_domain_monotonicity_witness(
    parameters: tuple[str, ...],
    polynomial: Polynomial,
    argument_index: int,
    lower: int,
) -> dict[str, Any] | None:
    """Exhibit failure at the carrier boundary, without a ground-term fiction.

    Polynomial-interpretation variables range over the source-declared scalar
    carrier.  A valuation in that carrier refutes strict monotonicity even when
    no closed constructor term happens to denote the same number.  For the
    nonnegative polynomial grammar, the all-lower valuation is the exact point
    at which a coefficient multiplied by another zero-valued argument loses
    strictness.
    """

    before_arguments = [lower] * len(parameters)
    after_arguments = list(before_arguments)
    after_arguments[argument_index] += 1
    before = poly_eval(polynomial, dict(zip(parameters, before_arguments)))
    after = poly_eval(polynomial, dict(zip(parameters, after_arguments)))
    if after > before:
        return None
    return {
        "valuation_scope": "source_declared_scalar_carrier",
        "declared_lower_bound": lower,
        "arguments_before": before_arguments,
        "arguments_after": after_arguments,
        "value_before": before,
        "value_after": after,
    }


def interpretation_collapse_witness(
    definitions: list[Any],
    lower: int,
) -> dict[str, Any] | None:
    """Return a witness when a written operation fails strict monotonicity.

    The Schema A collapse rule is that failure: a load-bearing argument whose
    value stays equal or falls at the carrier lower bound, including a
    coefficient of the duplicated payload that is zero at the zero constructor.  A constant
    in the written map that sits below the declared lower bound is part of the
    reachable image, so the check uses the smaller of those two points.  The
    helper reads only definitions whose typed polynomial parsed, so a fragment
    can refute.
    """

    if not isinstance(definitions, list) or not isinstance(lower, int):
        return None
    rows: list[tuple[str, tuple[str, ...], Polynomial]] = []
    constant_values: list[int] = []
    for definition in definitions:
        if not isinstance(definition, dict) or definition.get("status") != "ok":
            continue
        parameters = definition.get("canonical_parameters")
        if not isinstance(parameters, list):
            continue
        names = tuple(str(item) for item in parameters)
        polynomial = poly_from_typed(definition.get("polynomial") or {})
        if polynomial is None:
            continue
        symbol = str(definition.get("symbol") or "")
        rows.append((symbol, names, polynomial))
        if not names:
            constant_values.append(poly_eval(polynomial, {}))
    if constant_values:
        lower = min(lower, min(constant_values))
    for symbol, names, polynomial in sorted(rows, key=lambda item: item[0]):
        for index, parameter in enumerate(names):
            witness = _declared_domain_monotonicity_witness(
                names, polynomial, index, lower
            )
            if witness is None:
                continue
            return {
                "type": "collapse_at_carrier_lower_bound",
                "symbol": symbol,
                "argument": index + 1,
                "parameter": parameter,
                **witness,
            }
    return None


def _rule_witness(
    difference: Polynomial,
    sample: ReachableSample,
) -> dict[str, Any] | None:
    variables = tuple(sorted(poly_vars(difference)))
    assignments = product(sample.values, repeat=len(variables)) if variables else [()]
    for values in assignments:
        point = dict(zip(variables, values))
        margin = poly_eval(difference, point)
        if margin < 1:
            return {
                "valuation": point,
                "ground_substitution": {
                    variable: sample.witnesses[value]
                    for variable, value in zip(variables, values)
                },
                "lhs_minus_rhs": margin,
            }
    return None


NaturalInterpretation = dict[str, tuple[tuple[str, ...], NaturalExpr]]
MAX_NATURAL_POWER_POLY_TERMS = 4096
MAX_NATURAL_POWER_PRODUCTS = 250_000
INTERPRETATION_DOMAIN_LOWER_BOUNDS = {"N": 0, "N_ge_1": 1, "N_ge_2": 2}


def _natural_power_certifier_build() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    files = {
        name: sha256((root / name).read_bytes()).hexdigest()
        for name in ("native_math.py", "natural_power.py")
    }
    core = {
        "engine": "tgc-closed-natural-power-certifier",
        "version": "1.0.0",
        "files": files,
    }
    serialized = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "build_sha256": sha256(serialized).hexdigest()}


def _natural_const(value: int) -> NaturalExpr:
    return {"op": "const", "value": value}


def _natural_var(name: str) -> NaturalExpr:
    return {"op": "var", "name": name}


def _natural_variadic(op: str, arguments: list[NaturalExpr]) -> NaturalExpr:
    if not arguments:
        return _natural_const(0 if op == "add" else 1)
    if len(arguments) == 1:
        return arguments[0]
    return {"op": op, "args": arguments}


def _natural_from_polynomial(polynomial: Polynomial) -> NaturalExpr:
    terms: list[NaturalExpr] = []
    for monomial, coefficient in sorted(polynomial.items()):
        factors: list[NaturalExpr] = []
        if coefficient != 1 or not monomial:
            factors.append(_natural_const(coefficient))
        for variable, exponent in monomial:
            factors.extend(_natural_var(variable) for _ in range(exponent))
        terms.append(_natural_variadic("mul", factors))
    return _natural_variadic("add", terms)


def _typed_natural_interpretation(
    mathematical_core: dict[str, Any],
    signature: dict[str, list[str]],
) -> tuple[NaturalInterpretation, str | None]:
    definitions = ((mathematical_core.get("payload") or {}).get("definitions"))
    if not isinstance(definitions, list):
        return {}, "typed_definitions_missing"
    interpretation: NaturalInterpretation = {}
    for definition in definitions:
        if not isinstance(definition, dict) or definition.get("status") != "ok":
            return {}, "definition_unparseable"
        symbol = definition.get("symbol")
        parameters = definition.get("canonical_parameters")
        if symbol not in signature or not isinstance(parameters, list):
            return {}, "definition_shape_invalid"
        expected = tuple(signature[str(symbol)])
        if tuple(parameters) != expected:
            return {}, f"definition_parameters_mismatch[{symbol}]"
        if symbol in interpretation:
            return {}, f"duplicate_definition[{symbol}]"
        if "natural_power" in definition:
            expression = natural_power_from_typed(definition.get("natural_power"))
        else:
            polynomial = poly_from_typed(definition.get("polynomial") or {})
            expression = None if polynomial is None else _natural_from_polynomial(polynomial)
        if expression is None:
            return {}, f"definition_shape_invalid[{symbol}]"
        if not natural_power_variables(expression) <= set(expected):
            return {}, f"definition_unknown_variable[{symbol}]"
        interpretation[str(symbol)] = (expected, expression)
    missing = sorted(set(signature) - set(interpretation))
    extra = sorted(set(interpretation) - set(signature))
    if missing or extra:
        return {}, f"definition_signature_mismatch[missing={missing},extra={extra}]"
    return interpretation, None


def _natural_apply(
    symbol: str,
    arguments: tuple[NaturalExpr, ...],
    interpretation: NaturalInterpretation,
) -> NaturalExpr:
    parameters, expression = interpretation[symbol]
    if len(parameters) != len(arguments):
        raise ValueError(f"arity mismatch for {symbol}")
    return natural_power_substitute(expression, dict(zip(parameters, arguments)))


def _natural_interpret_term(
    term: Term,
    interpretation: NaturalInterpretation,
    signature_symbols: set[str],
) -> NaturalExpr:
    head, args = term
    if not args and head not in signature_symbols:
        return _natural_var(head)
    if head not in interpretation:
        raise KeyError(head)
    return _natural_apply(
        head,
        tuple(
            _natural_interpret_term(arg, interpretation, signature_symbols)
            for arg in args
        ),
        interpretation,
    )


def _natural_lower(expr: NaturalExpr, lower: int) -> int:
    return natural_power_eval(
        expr, {variable: lower for variable in natural_power_variables(expr)}
    )


def _natural_nondecreasing(expr: NaturalExpr, lower: int) -> bool:
    op = expr["op"]
    if op in {"const", "var"}:
        return True
    if op in {"add", "mul"}:
        return all(_natural_nondecreasing(item, lower) for item in expr["args"])
    exponent = expr["exponent"]
    return _natural_nondecreasing(expr["base"], lower) and (
        "constant" in exponent or _natural_lower(expr["base"], lower) >= 1
    )


def _natural_strict_in(expr: NaturalExpr, parameter: str, lower: int) -> bool:
    op = expr["op"]
    if op == "const":
        return False
    if op == "var":
        return expr["name"] == parameter
    if op == "add":
        return any(_natural_strict_in(item, parameter, lower) for item in expr["args"])
    if op == "mul":
        for index, item in enumerate(expr["args"]):
            if _natural_strict_in(item, parameter, lower) and all(
                _natural_lower(other, lower) >= 1
                for other_index, other in enumerate(expr["args"])
                if other_index != index
            ):
                return True
        return False
    exponent = expr["exponent"]
    exponent_lower = (
        int(exponent["constant"])
        if "constant" in exponent
        else lower + int(exponent["offset"])
    )
    base_lower = _natural_lower(expr["base"], lower)
    strict_through_base = (
        exponent_lower >= 1
        and _natural_strict_in(expr["base"], parameter, lower)
    )
    strict_through_exponent = (
        exponent.get("variable") == parameter and base_lower >= 2
    )
    return strict_through_base or strict_through_exponent


def _natural_generated_minimum(
    interpretation: NaturalInterpretation,
) -> tuple[tuple[int, str] | None, str | None]:
    constants: list[tuple[int, str]] = []
    try:
        for symbol, (parameters, expression) in interpretation.items():
            if not parameters:
                constants.append((natural_power_eval(expression, {}), symbol))
    except OverflowError:
        return None, "natural_power_evaluation_resource_cap"
    if not constants:
        return None, "ground_carrier_has_no_constant"
    minimum, witness = min(constants, key=lambda item: (item[0], item[1]))
    while True:
        try:
            if any(
                not _natural_nondecreasing(expression, minimum)
                for parameters, expression in interpretation.values()
                if parameters
            ):
                return None, "natural_power_not_monotone_at_generated_lower_bound"
        except OverflowError:
            return None, "natural_power_evaluation_resource_cap"
        best = (minimum, witness)
        for symbol, (parameters, expression) in sorted(interpretation.items()):
            if not parameters:
                continue
            try:
                value = natural_power_eval(
                    expression, {parameter: minimum for parameter in parameters}
                )
            except OverflowError:
                return None, "natural_power_evaluation_resource_cap"
            if value < best[0]:
                best = (
                    value,
                    _short_ground(symbol, tuple(witness for _ in parameters)),
                )
        if best[0] >= minimum:
            return (minimum, witness), None
        minimum, witness = best


def _natural_reachable_sample(
    interpretation: NaturalInterpretation, *, cap: int
) -> ReachableSample:
    witnesses: dict[int, str] = {}
    for symbol, (parameters, expression) in sorted(interpretation.items()):
        if not parameters:
            value = natural_power_eval(expression, {})
            if value <= cap:
                witnesses.setdefault(value, symbol)
    if not witnesses:
        return ReachableSample((), {}, cap, True, False)
    truncated = False
    for _ in range(cap + 2):
        before = len(witnesses)
        current = tuple(sorted(witnesses))
        additions: dict[int, str] = {}
        for symbol, (parameters, expression) in sorted(interpretation.items()):
            if not parameters:
                continue
            for values in product(current, repeat=len(parameters)):
                try:
                    output = natural_power_eval(
                        expression, dict(zip(parameters, values))
                    )
                except OverflowError:
                    truncated = True
                    continue
                if output > cap:
                    truncated = True
                    continue
                if output not in witnesses and output not in additions:
                    arguments = tuple(witnesses[value] for value in values)
                    additions[output] = _short_ground(symbol, arguments)
        witnesses.update(additions)
        if len(witnesses) == before:
            return ReachableSample(
                tuple(sorted(witnesses)),
                dict(sorted(witnesses.items())),
                cap,
                truncated,
                not truncated,
            )
    return ReachableSample(
        tuple(sorted(witnesses)), dict(sorted(witnesses.items())), cap, True, False
    )


def _natural_monotonicity_witness(
    parameters: tuple[str, ...],
    expression: NaturalExpr,
    argument_index: int,
    sample: ReachableSample,
) -> dict[str, Any] | None:
    if len(sample.values) < 2:
        return None
    for base in product(sample.values, repeat=len(parameters)):
        current = base[argument_index]
        larger = next((value for value in sample.values if value > current), None)
        if larger is None:
            continue
        bumped = list(base)
        bumped[argument_index] = larger
        before = natural_power_eval(expression, dict(zip(parameters, base)))
        after = natural_power_eval(expression, dict(zip(parameters, bumped)))
        if after <= before:
            return {
                "arguments_before": list(base),
                "arguments_after": bumped,
                "ground_terms_before": [sample.witnesses[value] for value in base],
                "ground_terms_after": [sample.witnesses[value] for value in bumped],
                "value_before": before,
                "value_after": after,
            }
    return None


def _coefficient_dominates_with_lowers(
    polynomial: Polynomial, margin: int, lowers: dict[str, int]
) -> bool:
    if len(polynomial) > MAX_NATURAL_POWER_POLY_TERMS:
        raise ValueError("natural-power polynomial term cap exceeded")
    shifted = _bounded_poly_substitute(
        polynomial,
        {
            variable: poly_add(poly_var(variable), poly_const(lowers[variable]))
            for variable in poly_vars(polynomial)
        },
    )
    required = poly_sub(shifted, poly_const(margin))
    return all(coefficient >= 0 for coefficient in required.values())


def _bounded_poly_add(left: Polynomial, right: Polynomial) -> Polynomial:
    result = poly_add(left, right)
    if len(result) > MAX_NATURAL_POWER_POLY_TERMS:
        raise ValueError("natural-power polynomial term cap exceeded")
    return result


def _bounded_poly_mul(left: Polynomial, right: Polynomial) -> Polynomial:
    if len(left) * len(right) > MAX_NATURAL_POWER_PRODUCTS:
        raise ValueError("natural-power polynomial product cap exceeded")
    result = poly_mul(left, right)
    if len(result) > MAX_NATURAL_POWER_POLY_TERMS:
        raise ValueError("natural-power polynomial term cap exceeded")
    return result


def _bounded_poly_pow(polynomial: Polynomial, exponent: int) -> Polynomial:
    result = poly_const(1)
    base = polynomial
    power = exponent
    while power:
        if power & 1:
            result = _bounded_poly_mul(result, base)
        power >>= 1
        if power:
            base = _bounded_poly_mul(base, base)
    return result


def _bounded_poly_substitute(
    polynomial: Polynomial, mapping: dict[str, Polynomial]
) -> Polynomial:
    result: Polynomial = {}
    for monomial, coefficient in polynomial.items():
        term = poly_const(coefficient)
        for variable, exponent in monomial:
            term = _bounded_poly_mul(
                term,
                _bounded_poly_pow(mapping.get(variable, poly_var(variable)), exponent),
            )
        result = _bounded_poly_add(result, term)
    return result


def _natural_to_polynomial(
    expr: NaturalExpr,
    *,
    lower: int,
    atom_names: dict[str, str],
    atom_lowers: dict[str, int],
    used_names: set[str],
) -> Polynomial:
    op = expr["op"]
    if op == "const":
        return poly_const(expr["value"])
    if op == "var":
        return poly_var(expr["name"])
    if op == "add":
        result = poly_const(0)
        for item in expr["args"]:
            result = _bounded_poly_add(
                result,
                _natural_to_polynomial(
                    item,
                    lower=lower,
                    atom_names=atom_names,
                    atom_lowers=atom_lowers,
                    used_names=used_names,
                ),
            )
        return result
    if op == "mul":
        result = poly_const(1)
        for item in expr["args"]:
            result = _bounded_poly_mul(
                result,
                _natural_to_polynomial(
                    item,
                    lower=lower,
                    atom_names=atom_names,
                    atom_lowers=atom_lowers,
                    used_names=used_names,
                ),
            )
        return result

    base = _natural_to_polynomial(
        expr["base"],
        lower=lower,
        atom_names=atom_names,
        atom_lowers=atom_lowers,
        used_names=used_names,
    )
    exponent = expr["exponent"]
    if "constant" in exponent:
        return _bounded_poly_pow(base, int(exponent["constant"]))
    atom_key = json.dumps(
        {"base": expr["base"], "variable": exponent["variable"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    atom = atom_names.get(atom_key)
    if atom is None:
        index = len(atom_names)
        atom = f"__tgc_npow_{index}"
        while atom in used_names:
            index += 1
            atom = f"__tgc_npow_{index}"
        atom_names[atom_key] = atom
        used_names.add(atom)
        base_lower = _natural_lower(expr["base"], lower)
        if base_lower < 1:
            raise ValueError("variable exponent has base below one")
        if base_lower >= 2 and lower * base_lower.bit_length() > 16_384:
            raise ValueError("natural-power atom lower bound exceeds resource cap")
        atom_lowers[atom] = base_lower**lower
    return _bounded_poly_mul(
        poly_var(atom), _bounded_poly_pow(base, int(exponent.get("offset", 0)))
    )


def _natural_rule_witness(
    lhs: NaturalExpr,
    rhs: NaturalExpr,
    sample: ReachableSample,
) -> dict[str, Any] | None:
    variables = tuple(sorted(natural_power_variables(lhs) | natural_power_variables(rhs)))
    assignments = product(sample.values, repeat=len(variables)) if variables else [()]
    for values in assignments:
        point = dict(zip(variables, values))
        lhs_value = natural_power_eval(lhs, point)
        rhs_value = natural_power_eval(rhs, point)
        if lhs_value - rhs_value < 1:
            return {
                "valuation": point,
                "ground_substitution": {
                    variable: sample.witnesses[value]
                    for variable, value in zip(variables, values)
                },
                "lhs_minus_rhs": lhs_value - rhs_value,
            }
    return None


def natural_power_interpretation_decision(
    mathematical_core: dict[str, Any],
    checker_object: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
    *,
    reachability_cap: int = 32,
) -> dict[str, Any]:
    """Sound decision for the closed natural-power interpretation fragment."""

    interpretation, issue = _typed_natural_interpretation(mathematical_core, signature)
    if issue:
        return {"status": "unsupported", "reason": issue}
    declared_domain = str(((checker_object.get("payload") or {}).get("domain")) or "N")
    proof_lower = INTERPRETATION_DOMAIN_LOWER_BOUNDS.get(declared_domain)
    if proof_lower is None:
        return {"status": "unsupported", "reason": "declared_domain_unsupported"}
    generated, issue = _natural_generated_minimum(interpretation)
    if generated is None:
        return {"status": "unsupported", "reason": issue}
    generated_lower, lower_witness = generated
    sample = _natural_reachable_sample(interpretation, cap=reachability_cap)
    common: dict[str, Any] = {
        "decision_family": "closed_natural_power",
        "decision_engine": _natural_power_certifier_build(),
        "declared_domain": declared_domain,
        "interpretation_domain_lower_bound": proof_lower,
        "generated_carrier_lower_bound": generated_lower,
        "generated_lower_witness": lower_witness,
        "reachable_sample": list(sample.values),
        "reachable_witnesses": {str(k): v for k, v in sample.witnesses.items()},
        "reachability_cap": sample.cap,
        "reachable_sample_truncated": sample.truncated,
        "reachable_sample_exact": sample.exact,
    }
    if generated_lower < proof_lower:
        return {
            "status": "ok",
            "holds": False,
            "reason": "declared_carrier_not_closed_on_reachable_ground_term",
            "witness": {
                "ground_term": lower_witness,
                "interpretation_value": generated_lower,
            },
            **common,
        }
    if not sample.values:
        return {"status": "unsupported", "reason": "reachable_sample_empty", **common}

    try:
        domain_closed = all(
            _natural_nondecreasing(expression, proof_lower)
            and _natural_lower(expression, proof_lower) >= proof_lower
            for parameters, expression in interpretation.values()
        )
    except OverflowError:
        domain_closed = False
    monotonicity_table: list[dict[str, Any]] = []
    unresolved = not domain_closed
    for symbol, (parameters, expression) in sorted(interpretation.items()):
        for index, parameter in enumerate(parameters):
            proved = domain_closed and _natural_strict_in(
                expression, parameter, proof_lower
            )
            witness = None if proved else _natural_monotonicity_witness(
                parameters, expression, index, sample
            )
            row: dict[str, Any] = {
                "symbol": symbol,
                "argument": index + 1,
                "parameter": parameter,
                "structural_natural_power_proof_above_declared_domain_lower_bound": proved,
            }
            if witness is not None:
                row["status"] = "refuted_on_reachable_values"
                row["witness"] = witness
                common.setdefault(
                    "monotonicity_counterexample",
                    {
                        "type": "reachable_monotonicity_counterexample",
                        "symbol": symbol,
                        "argument": index + 1,
                        "parameter": parameter,
                        **witness,
                    },
                )
            elif proved:
                row["status"] = "proved"
            elif sample.exact:
                row["status"] = "exhaustively_verified_on_finite_generated_carrier"
            else:
                row["status"] = "unresolved_no_reachable_counterexample_within_cap"
                unresolved = True
            monotonicity_table.append(row)

    rule_table: list[dict[str, Any]] = []
    signature_symbols = set(signature)
    for rule in rules:
        try:
            lhs = _natural_interpret_term(
                parse_term(str(rule["lhs"])), interpretation, signature_symbols
            )
            rhs = _natural_interpret_term(
                parse_term(str(rule["rhs"])), interpretation, signature_symbols
            )
        except (ValueError, KeyError) as exc:
            return {
                "status": "unsupported",
                "reason": f"rule_interpretation_failed[{rule.get('name')}:{exc}]",
                "monotonicity_table": monotonicity_table,
                **common,
            }
        rule_variables = natural_power_variables(lhs) | natural_power_variables(rhs)
        atom_names: dict[str, str] = {}
        atom_lowers: dict[str, int] = {}
        used_names = set(rule_variables)
        proof_issue: str | None = None
        try:
            lhs_poly = _natural_to_polynomial(
                lhs,
                lower=proof_lower,
                atom_names=atom_names,
                atom_lowers=atom_lowers,
                used_names=used_names,
            )
            rhs_poly = _natural_to_polynomial(
                rhs,
                lower=proof_lower,
                atom_names=atom_names,
                atom_lowers=atom_lowers,
                used_names=used_names,
            )
            difference = poly_sub(lhs_poly, rhs_poly)
            variable_lowers = {variable: proof_lower for variable in rule_variables}
            variable_lowers.update(atom_lowers)
            proved = _coefficient_dominates_with_lowers(
                difference, 1, variable_lowers
            )
        except ValueError as exc:
            proof_issue = str(exc)
            proved = False
        witness = None if proved else _natural_rule_witness(lhs, rhs, sample)
        row: dict[str, Any] = {
            "rule": str(rule.get("name") or ""),
            "coefficient_proof_with_power_atoms": proved,
            "power_atom_lower_bounds": dict(sorted(atom_lowers.items())),
        }
        if proof_issue is not None:
            row["proof_issue"] = proof_issue
        if witness is not None:
            row["status"] = "refuted_on_reachable_values"
            row["witness"] = witness
            rule_table.append(row)
            return {
                "status": "ok",
                "holds": False,
                "reason": f"rule_non_decrease[{rule.get('name')}]",
                "witness": {
                    "type": "reachable_rule_counterexample",
                    "rule": str(rule.get("name") or ""),
                    **witness,
                },
                "monotonicity_table": monotonicity_table,
                "rule_table": rule_table,
                **common,
            }
        if proved:
            row["status"] = "proved"
        elif sample.exact:
            row["status"] = "exhaustively_verified_on_finite_generated_carrier"
        else:
            row["status"] = "unresolved_no_reachable_counterexample_within_cap"
            unresolved = True
        rule_table.append(row)

    monotonicity_counterexample = common.get("monotonicity_counterexample")
    if monotonicity_counterexample is not None:
        return {
            "status": "ok",
            "holds": False,
            "reason": (
                "strict_monotonicity_fails"
                f"[{monotonicity_counterexample['symbol']}:"
                f"{monotonicity_counterexample['parameter']}]"
            ),
            "witness": monotonicity_counterexample,
            "rules_hold": None if unresolved else True,
            "monotonicity_table": monotonicity_table,
            "rule_table": rule_table,
            **common,
        }
    return {
        "status": "ok",
        "holds": None if unresolved else True,
        "reason": (
            "symbolic_declared_carrier_or_finite_generated_certificate"
            if not unresolved
            else "sufficient_proof_failed_without_reachable_counterexample"
        ),
        "monotonicity_table": monotonicity_table,
        "rule_table": rule_table,
        **common,
    }


def polynomial_interpretation_decision(
    mathematical_core: dict[str, Any],
    checker_object: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
    *,
    reachability_cap: int = 32,
) -> dict[str, Any]:
    """Sound decision for typed nonnegative polynomial interpretations.

    PASS is proved coefficientwise after shifting every variable by the
    source-declared carrier lower bound. A failed sufficient test never implies REFUTED:
    refutation is issued only with a valuation whose values have explicit ground
    term representatives in the signature-generated subalgebra.
    """

    kind = mathematical_core.get("kind")
    if kind not in {"poly_interpretation", "additive_measure"}:
        return {"status": "not_applicable"}
    if (
        kind == "poly_interpretation"
        and (mathematical_core.get("payload") or {}).get("interpretation_scope")
        == "dependency_pair"
    ):
        return dependency_pair_polynomial_decision(
            mathematical_core, checker_object, rules, signature
        )
    definitions = ((mathematical_core.get("payload") or {}).get("definitions"))
    if isinstance(definitions, list) and any(
        isinstance(definition, dict) and "natural_power" in definition
        for definition in definitions
    ):
        return natural_power_interpretation_decision(
            mathematical_core,
            checker_object,
            rules,
            signature,
            reachability_cap=reachability_cap,
        )
    interpretation, issue = _typed_interpretation(mathematical_core, signature)
    if issue:
        return {"status": "unsupported", "reason": issue}
    payload = checker_object.get("payload") or {}
    declared_domain = str(payload.get("domain") or "N")
    proof_lower = INTERPRETATION_DOMAIN_LOWER_BOUNDS.get(declared_domain)
    if proof_lower is None:
        return {"status": "unsupported", "reason": "declared_domain_unsupported"}
    generated = generated_minimum(interpretation)
    if generated is None:
        return {"status": "unsupported", "reason": "ground_carrier_has_no_constant"}
    generated_lower, lower_witness = generated
    sample = reachable_ground_sample(interpretation, cap=reachability_cap)
    common: dict[str, Any] = {
        "declared_domain": declared_domain,
        "interpretation_domain_lower_bound": proof_lower,
        "generated_carrier_lower_bound": generated_lower,
        "generated_lower_witness": lower_witness,
        "reachable_sample": list(sample.values),
        "reachable_witnesses": {str(k): v for k, v in sample.witnesses.items()},
        "reachability_cap": sample.cap,
        "reachable_sample_truncated": sample.truncated,
        "reachable_sample_exact": sample.exact,
    }
    if generated_lower < proof_lower:
        return {
            "status": "ok",
            "holds": False,
            "reason": "declared_carrier_not_closed_on_reachable_ground_term",
            "witness": {
                "ground_term": lower_witness,
                "interpretation_value": generated_lower,
            },
            **common,
        }
    if not sample.values:
        return {"status": "unsupported", "reason": "reachable_sample_empty", **common}

    domain_closed = all(
        poly_eval(
            polynomial, {parameter: proof_lower for parameter in parameters}
        )
        >= proof_lower
        for parameters, polynomial in interpretation.values()
    )
    monotonicity_table: list[dict[str, Any]] = []
    unresolved = not domain_closed
    for symbol, (parameters, polynomial) in sorted(interpretation.items()):
        for index, parameter in enumerate(parameters):
            bumped = poly_substitute(
                polynomial,
                {parameter: poly_add(poly_var(parameter), poly_const(1))},
            )
            difference = poly_sub(bumped, polynomial)
            proved = domain_closed and _coefficient_dominates(
                difference, 1, proof_lower
            )
            carrier_witness = (
                None
                if proved
                else _declared_domain_monotonicity_witness(
                    parameters, polynomial, index, proof_lower
                )
            )
            witness = carrier_witness or (
                None
                if proved
                else _monotonicity_witness(parameters, polynomial, index, sample)
            )
            row: dict[str, Any] = {
                "symbol": symbol,
                "argument": index + 1,
                "parameter": parameter,
                "coefficient_proof_above_declared_domain_lower_bound": proved,
            }
            if witness is not None:
                # A monotonicity counterexample kills the CONTEXT-CLOSURE
                # licence, not the per-rule root decrease: the rule table is
                # still checked below, so a root-only claim over a
                # deliberately argument-dropping interpretation (measured
                # 2026-08-07: W(pear a b) = W(b) + 1, claimed for top-level
                # reduction only) is decided on what it actually claims. The
                # consumer stays target-sensitive; full-contextual claims are
                # refuted by this witness exactly as before.
                row["status"] = (
                    "refuted_on_declared_carrier"
                    if carrier_witness is not None
                    else "refuted_on_reachable_values"
                )
                row["witness"] = witness
                monotonicity_table.append(row)
                if "monotonicity_counterexample" not in common:
                    common["monotonicity_counterexample"] = {
                        "type": "reachable_monotonicity_counterexample",
                        "symbol": symbol,
                        "argument": index + 1,
                        "parameter": parameter,
                        **witness,
                    }
                continue
            if proved:
                row["status"] = "proved"
            elif sample.exact:
                row["status"] = "exhaustively_verified_on_finite_generated_carrier"
            else:
                row["status"] = "unresolved_no_reachable_counterexample_within_cap"
                unresolved = True
            monotonicity_table.append(row)

    rule_table: list[dict[str, Any]] = []
    signature_symbols = set(signature)
    for rule in rules:
        try:
            lhs = _interpret_term(
                parse_term(str(rule["lhs"])), interpretation, signature_symbols
            )
            rhs = _interpret_term(
                parse_term(str(rule["rhs"])), interpretation, signature_symbols
            )
        except (ValueError, KeyError) as exc:
            return {
                "status": "unsupported",
                "reason": f"rule_interpretation_failed[{rule.get('name')}:{exc}]",
                "monotonicity_table": monotonicity_table,
                **common,
            }
        difference = poly_sub(lhs, rhs)
        proved = domain_closed and _coefficient_dominates(
            difference, 1, proof_lower
        )
        witness = None if proved else _rule_witness(difference, sample)
        row = {
            "rule": str(rule.get("name") or ""),
            "coefficient_proof_above_declared_domain_lower_bound": proved,
        }
        if witness is not None:
            row["status"] = "refuted_on_reachable_values"
            row["witness"] = witness
            rule_table.append(row)
            return {
                "status": "ok",
                "holds": False,
                "reason": f"rule_non_decrease[{rule.get('name')}]",
                "witness": {
                    "type": "reachable_rule_counterexample",
                    "rule": str(rule.get("name") or ""),
                    **witness,
                },
                "monotonicity_table": monotonicity_table,
                "rule_table": rule_table,
                **common,
            }
        if proved:
            row["status"] = "proved"
        elif sample.exact:
            row["status"] = "exhaustively_verified_on_finite_generated_carrier"
        else:
            row["status"] = "unresolved_no_reachable_counterexample_within_cap"
            unresolved = True
        rule_table.append(row)

    monotonicity_counterexample = common.get("monotonicity_counterexample")
    if monotonicity_counterexample is not None:
        witness_info = monotonicity_counterexample
        return {
            "status": "ok",
            "holds": False,
            "reason": (
                "strict_monotonicity_fails"
                f"[{witness_info['symbol']}:{witness_info['parameter']}]"
            ),
            "witness": witness_info,
            # The rule table was still verified: True when every rule's strict
            # decrease is proved (or exhaustively verified), None when the
            # sufficient test failed without a counterexample. A rule
            # counterexample returns through its own branch above, so False
            # never reaches here.
            "rules_hold": None if unresolved else True,
            "monotonicity_table": monotonicity_table,
            "rule_table": rule_table,
            **common,
        }
    return {
        "status": "ok",
        "holds": None if unresolved else True,
        "reason": (
            "symbolic_declared_carrier_or_finite_generated_certificate"
            if not unresolved
            else "sufficient_proof_failed_without_reachable_counterexample"
        ),
        "monotonicity_table": monotonicity_table,
        "rule_table": rule_table,
        **common,
    }


def _unmark_dependency_symbol(symbol: str) -> str:
    import re

    return re.sub(r"(?:\^\{?\\?sharp\}?|[#♯])$", "", symbol)


def _is_dependency_pair_variable(term: Term, signature: dict[str, list[str]]) -> bool:
    head, arguments = term
    return not arguments and _unmark_dependency_symbol(head) not in signature


def _dependency_pair_key(lhs: Term, rhs: Term, signature: dict[str, list[str]]) -> Any:
    """Identify a pair by its base symbols and variable pattern.

    Marking is notation: the root of each side is the tuple symbol by
    position, and inner symbols denote the original function symbols.
    """

    variables: dict[str, int] = {}

    def key(term: Term) -> Any:
        head, arguments = term
        if _is_dependency_pair_variable(term, signature):
            if head not in variables:
                variables[head] = len(variables)
            return "var", variables[head]
        base = _unmark_dependency_symbol(head)
        if len(arguments) != len(signature[base]):
            raise ValueError(f"dependency_pair_unknown_symbol_or_arity[{head}]")
        return base, tuple(key(argument) for argument in arguments)

    return key(lhs), key(rhs)


def _check_dependency_pair_symbols(term: Term, signature: dict[str, list[str]]) -> None:
    head, arguments = term
    if _is_dependency_pair_variable(term, signature):
        return
    base = _unmark_dependency_symbol(head)
    if base not in signature or len(arguments) != len(signature[base]):
        raise ValueError(f"dependency_pair_unknown_symbol_or_arity[{head}]")
    for argument in arguments:
        _check_dependency_pair_symbols(argument, signature)


def _unmark_term(term: Term) -> Term:
    head, arguments = term
    return _unmark_dependency_symbol(head), tuple(_unmark_term(argument) for argument in arguments)


def _is_proper_subterm(inner: Term, outer: Term) -> bool:
    return any(argument == inner or _is_proper_subterm(inner, argument) for argument in outer[1])


def _derived_dependency_pairs(
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
) -> list[tuple[Term, Term, bool]]:
    """Return every dependency pair with a flag marking the optional ones.

    A pair whose right side is a proper subterm of the rule's left side may be
    omitted under the refined Arts-Giesl definition; every other pair is
    required.
    """

    defined = {parse_term(str(rule["lhs"]))[0] for rule in rules}
    pairs: list[tuple[Term, Term, bool]] = []

    def calls(term: Term) -> list[Term]:
        output = [term] if term[0] in defined else []
        for argument in term[1]:
            output.extend(calls(argument))
        return output

    for rule in rules:
        lhs, rhs = parse_term(str(rule["lhs"])), parse_term(str(rule["rhs"]))
        for call in calls(rhs):
            optional = _is_proper_subterm(call, lhs)
            pairs.append(((lhs[0] + "#", lhs[1]), (call[0] + "#", call[1]), optional))
    return pairs


def _walk_terms(term: Term) -> list[Term]:
    output = [term]
    for argument in term[1]:
        output.extend(_walk_terms(argument))
    return output


def resolve_usable_rule_items(
    items: list[Any],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    """Map stated usable-rule items to contract rule names.

    An item may be a rule name, a defined symbol (all of its rules), or a rule
    written as ``lhs -> rhs``. Unresolved items are returned, never guessed.
    """

    import re

    by_name = {str(rule.get("name") or ""): rule for rule in rules}
    by_symbol: dict[str, list[str]] = {}
    keyed: dict[Any, str] = {}
    for rule in rules:
        name = str(rule.get("name") or "")
        lhs, rhs = parse_term(str(rule["lhs"])), parse_term(str(rule["rhs"]))
        by_symbol.setdefault(lhs[0], []).append(name)
        keyed[_dependency_pair_key(lhs, rhs, signature)] = name
    resolved: list[str] = []
    unresolved: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            unresolved.append(repr(item))
            continue
        text = item.strip()
        names: list[str] = []
        if text in by_name:
            names = [text]
        elif _unmark_dependency_symbol(text) in by_symbol:
            names = by_symbol[_unmark_dependency_symbol(text)]
        else:
            sides = re.split(r"\s*(?:->|→|\\rightarrow|\\to)\s*", text)
            if len(sides) == 2:
                try:
                    lhs, rhs = parse_term(sides[0]), parse_term(sides[1])
                    _check_dependency_pair_symbols(lhs, signature)
                    _check_dependency_pair_symbols(rhs, signature)
                    name = keyed.get(
                        _dependency_pair_key(_unmark_term(lhs), _unmark_term(rhs), signature)
                    )
                except (ValueError, KeyError):
                    name = None
                if name:
                    names = [name]
        if not names:
            unresolved.append(text)
            continue
        for name in names:
            if name not in resolved:
                resolved.append(name)
    return resolved, unresolved


def _usable_rule_names(
    pair_right_sides: list[Term],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
) -> list[str]:
    """Usable rules of the pair right sides, closed over rule right sides."""

    rules_by_symbol: dict[str, list[tuple[str, Term]]] = {}
    for rule in rules:
        lhs, rhs = parse_term(str(rule["lhs"])), parse_term(str(rule["rhs"]))
        rules_by_symbol.setdefault(lhs[0], []).append((str(rule.get("name") or ""), rhs))
    usable: list[str] = []
    expanded: set[str] = set()

    def visit(term: Term) -> None:
        if _is_dependency_pair_variable(term, signature):
            return
        head, arguments = term
        for argument in arguments:
            visit(argument)
        base = _unmark_dependency_symbol(head)
        if base in rules_by_symbol and base not in expanded:
            expanded.add(base)
            for name, rhs in rules_by_symbol[base]:
                if name not in usable:
                    usable.append(name)
                visit(rhs)

    for rhs in pair_right_sides:
        for argument in rhs[1]:
            visit(argument)
    return sorted(usable)


def dependency_pair_polynomial_decision(
    mathematical_core: dict[str, Any],
    checker_object: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature: dict[str, list[str]],
) -> dict[str, Any]:
    """Check an explicit polynomial reduction pair on marked DP symbols.

    Soundness conditions, each checked on the stated object:
    the stated pairs are the dependency pairs of the contract rules (marking
    is notation); the stated usable rules contain every usable rule, closed
    over rule right sides, and each stated usable rule weakly decreases; every
    pair strictly decreases; the interpretation has nonnegative coefficients
    and maps the declared carrier into itself. A polynomial order with
    nonnegative coefficients is C_epsilon-compatible, which the usable-rule
    criterion for full termination requires.
    """

    core_payload = mathematical_core.get("payload") or {}
    checker_payload = checker_object.get("payload") or {}
    pairs = core_payload.get("dependency_pairs")
    usable_items = core_payload.get("usable_rules")
    if pairs != checker_payload.get("dependency_pairs") or usable_items != checker_payload.get("usable_rules"):
        return {"status": "unsupported", "reason": "dependency_pair_core_checker_mismatch"}
    if not isinstance(pairs, list) or not pairs or not isinstance(usable_items, list):
        return {"status": "unsupported", "reason": "dependency_pair_premises_missing"}
    try:
        parsed_pairs: list[tuple[Term, Term]] = []
        for pair in pairs:
            if not isinstance(pair, dict) or set(pair) != {"lhs", "rhs"}:
                raise ValueError("dependency_pair_shape")
            lhs, rhs = parse_term(str(pair["lhs"])), parse_term(str(pair["rhs"]))
            _check_dependency_pair_symbols(lhs, signature)
            _check_dependency_pair_symbols(rhs, signature)
            if _is_dependency_pair_variable(lhs, signature) or _is_dependency_pair_variable(rhs, signature):
                raise ValueError("dependency_pair_side_is_a_variable")
            parsed_pairs.append((lhs, rhs))
        declared_keys = {_dependency_pair_key(lhs, rhs, signature) for lhs, rhs in parsed_pairs}
        derived = _derived_dependency_pairs(rules, signature)
        derived_keys = {_dependency_pair_key(lhs, rhs, signature) for lhs, rhs, _ in derived}
        required_keys = {
            _dependency_pair_key(lhs, rhs, signature)
            for lhs, rhs, optional in derived
            if not optional
        }
    except (KeyError, TypeError, ValueError) as error:
        return {"status": "unsupported", "reason": str(error)}
    missing_pairs = required_keys - declared_keys
    extra_pairs = declared_keys - derived_keys
    if missing_pairs or extra_pairs:
        return {
            "status": "ok",
            "holds": False,
            "reason": "dependency_pair_set_mismatch",
            "declared_pair_count": len(declared_keys),
            "derived_pair_count": len(derived_keys),
            "missing_pair_count": len(missing_pairs),
            "extra_pair_count": len(extra_pairs),
        }

    inner_marked = sorted({
        node[0]
        for lhs, rhs in parsed_pairs
        for side in (lhs, rhs)
        for argument in side[1]
        for node in _walk_terms(argument)
        if not _is_dependency_pair_variable(node, signature)
        and node[0] != _unmark_dependency_symbol(node[0])
    })
    computed_usable = _usable_rule_names([rhs for _lhs, rhs in parsed_pairs], rules, signature)
    try:
        declared_usable, unresolved_usable = resolve_usable_rule_items(usable_items, rules, signature)
    except (KeyError, ValueError) as error:
        return {"status": "unsupported", "reason": f"usable_rule_items_unparseable[{error}]"}
    if unresolved_usable:
        return {
            "status": "unsupported",
            "reason": "usable_rule_item_unresolved",
            "unresolved_usable_rules": unresolved_usable,
        }
    missing_usable = sorted(set(computed_usable) - set(declared_usable))
    if missing_usable:
        return {
            "status": "ok",
            "holds": False,
            "reason": "usable_rule_premise_mismatch",
            "declared_usable_rules": sorted(declared_usable),
            "derived_usable_rules": computed_usable,
            "missing_usable_rules": missing_usable,
            "inner_marked_symbols_read_as_base": inner_marked,
        }

    rules_by_name = {str(rule.get("name") or ""): rule for rule in rules}
    usable_terms = [
        (name, parse_term(str(rules_by_name[name]["lhs"])), parse_term(str(rules_by_name[name]["rhs"])))
        for name in sorted(declared_usable)
    ]
    required: dict[str, list[str]] = {}

    def need(term: Term, *, root: bool) -> None:
        if _is_dependency_pair_variable(term, signature):
            return
        head, arguments = term
        base = _unmark_dependency_symbol(head)
        symbol = head if root else base
        required.setdefault(symbol, list(signature[base]))
        for argument in arguments:
            need(argument, root=False)

    for lhs, rhs in parsed_pairs:
        need(lhs, root=True)
        need(rhs, root=True)
    for _name, lhs, rhs in usable_terms:
        need(lhs, root=False)
        need(rhs, root=False)

    definitions = core_payload.get("definitions")
    if not isinstance(definitions, list):
        return {"status": "unsupported", "reason": "typed_definitions_missing"}
    stated_signature: dict[str, list[str]] = {}
    for definition in definitions:
        symbol = definition.get("symbol") if isinstance(definition, dict) else None
        if not isinstance(symbol, str) or _unmark_dependency_symbol(symbol) not in signature:
            return {"status": "unsupported", "reason": "definition_shape_invalid"}
        stated_signature[symbol] = list(signature[_unmark_dependency_symbol(symbol)])
    interpretation, issue = _typed_interpretation(mathematical_core, stated_signature)
    if issue:
        return {"status": "unsupported", "reason": issue}
    missing_definitions = sorted(set(required) - set(interpretation))
    if missing_definitions:
        return {
            "status": "unsupported",
            "reason": f"dependency_pair_definition_missing[{','.join(missing_definitions)}]",
            "inner_marked_symbols_read_as_base": inner_marked,
        }
    for symbol in inner_marked:
        base = _unmark_dependency_symbol(symbol)
        if symbol in interpretation and interpretation[symbol] != interpretation[base]:
            return {
                "status": "unsupported",
                "reason": f"inner_marked_symbol_interpretation_conflict[{symbol}]",
            }

    declared_domain = str(checker_payload.get("domain") or "N")
    lower = INTERPRETATION_DOMAIN_LOWER_BOUNDS.get(declared_domain)
    if lower is None:
        return {"status": "unsupported", "reason": "declared_domain_unsupported"}
    if any(coefficient < 0 for _symbol, (_parameters, polynomial) in interpretation.items() for coefficient in polynomial.values()):
        return {"status": "unsupported", "reason": "negative_polynomial_coefficient"}
    monotonicity_table = [
        {"symbol": symbol, "argument": index + 1, "status": "proved_weakly_monotone"}
        for symbol, (parameters, _polynomial) in sorted(interpretation.items())
        if symbol in required
        for index, _parameter in enumerate(parameters)
    ]
    closure_table: list[dict[str, Any]] = []
    for symbol in sorted(required):
        parameters, polynomial = interpretation[symbol]
        value = poly_eval(polynomial, {parameter: lower for parameter in parameters})
        closed = value >= lower
        closure_table.append({"symbol": symbol, "minimum_on_carrier": value, "closed": closed})
        if closed:
            continue
        if not parameters:
            return {
                "status": "ok",
                "holds": False,
                "reason": "declared_carrier_not_closed_on_ground_constant",
                "witness": {"ground_term": symbol, "interpretation_value": value, "declared_lower_bound": lower},
                "declared_domain": declared_domain,
                "closure_table": closure_table,
            }
        return {
            "status": "unsupported",
            "reason": f"declared_domain_closure_not_proved[{symbol}]",
            "declared_domain": declared_domain,
            "closure_table": closure_table,
        }

    evaluation = {**interpretation}

    def value(term: Term, *, root: bool) -> Polynomial:
        if _is_dependency_pair_variable(term, signature):
            return poly_var(term[0])
        head, arguments = term
        symbol = head if root else _unmark_dependency_symbol(head)
        return _apply_interpretation(
            symbol,
            tuple(value(argument, root=False) for argument in arguments),
            evaluation,
        )

    pair_table: list[dict[str, Any]] = []
    for index, (lhs_term, rhs_term) in enumerate(parsed_pairs, 1):
        try:
            difference = poly_sub(value(lhs_term, root=True), value(rhs_term, root=True))
        except (KeyError, ValueError) as error:
            return {"status": "unsupported", "reason": f"dependency_pair_interpretation_failed[{error}]"}
        proved = _coefficient_dominates(difference, 1, lower)
        pair_table.append({
            "pair": index,
            "lhs": render_term(lhs_term),
            "rhs": render_term(rhs_term),
            "strict_coefficient_proof": proved,
        })
        if not proved:
            return {
                "status": "unsupported",
                "reason": "dependency_pair_strict_descent_not_proved",
                "pair_table": pair_table,
                "monotonicity_table": monotonicity_table,
            }
    usable_rule_table: list[dict[str, Any]] = []
    for name, lhs_term, rhs_term in usable_terms:
        try:
            difference = poly_sub(value(lhs_term, root=False), value(rhs_term, root=False))
        except (KeyError, ValueError) as error:
            return {"status": "unsupported", "reason": f"usable_rule_interpretation_failed[{error}]"}
        proved = _coefficient_dominates(difference, 0, lower)
        usable_rule_table.append({"rule": name, "weak_coefficient_proof": proved})
        if not proved:
            return {
                "status": "unsupported",
                "reason": f"usable_rule_weak_decrease_not_proved[{name}]",
                "pair_table": pair_table,
                "usable_rule_table": usable_rule_table,
            }
    return {
        "status": "ok",
        "holds": True,
        "reason": (
            "dependency_pairs_strict_and_usable_rules_weakly_decreasing"
            if usable_terms
            else "dependency_pairs_strict_and_usable_rules_empty"
        ),
        "decision_family": "dependency_pair_polynomial_reduction_pair",
        "declared_domain": declared_domain,
        "pair_table": pair_table,
        "usable_rule_table": usable_rule_table,
        "derived_usable_rules": computed_usable,
        "declared_usable_rules": sorted(declared_usable),
        "inner_marked_symbols_read_as_base": inner_marked,
        "closure_table": closure_table,
        "monotonicity_table": monotonicity_table,
        "c_epsilon_compatibility": "nonnegative_polynomial_order",
    }


# A monotonicity row counts as machine-checked strict monotonicity only in
# these two states.  ``unresolved_no_reachable_counterexample_within_cap`` is a
# failed sufficient test, never a proof, and never licenses context closure.
VERIFIED_MONOTONICITY_STATUSES = frozenset(
    {
        "proved",
        "exhaustively_verified_on_finite_generated_carrier",
    }
)


def interpretation_monotonicity_verified(decision: dict[str, Any]) -> bool:
    """True iff the decision machine-checked STRICT monotonicity in EVERY
    argument position of EVERY interpreted symbol.

    :func:`polynomial_interpretation_decision` emits one monotonicity row per
    ``(symbol, argument)`` pair of a signature-complete interpretation and
    returns at the first refuted position, so an all-verified table is exactly
    the context-closure premise: every one-hole context is strictly increasing,
    therefore a strict decrease on a redex propagates through every context.
    The check reads the decision structure rather than the construction kind,
    so no monotonicity is ever asserted that the checker did not compute.
    """

    if decision.get("status") != "ok" or decision.get("holds") is not True:
        return False
    table = decision.get("monotonicity_table")
    if not isinstance(table, list) or not table:
        return False
    return all(
        isinstance(row, dict)
        and row.get("status") in VERIFIED_MONOTONICITY_STATUSES
        for row in table
    )
