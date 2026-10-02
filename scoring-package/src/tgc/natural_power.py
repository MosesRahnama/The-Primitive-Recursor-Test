"""Closed syntax for nonnegative interpretations with natural powers.

The ordinary interpretation grammar is polynomial.  This module adds one
deliberately small extension: a power-free nonnegative expression may be raised
to either a bounded natural constant or to one declared parameter plus a
bounded nonnegative offset.  Nothing in this module guesses prose or accepts
general host-language expressions.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

NaturalExpr = dict[str, Any]

MAX_AST_NODES = 128
MAX_LITERAL = 1_000_000
MAX_CONSTANT_EXPONENT = 32
MAX_EVAL_BITS = 16_384

_TEX_EXPONENT = re.compile(
    r"\^\{\s*(?P<exponent>(?:[A-Za-z][A-Za-z0-9_]*\s*\+\s*\d+)|"
    r"(?:\d+\s*\+\s*[A-Za-z][A-Za-z0-9_]*)|"
    r"(?:[A-Za-z][A-Za-z0-9_]*)|(?:\d+))\s*\}"
)


def _key(expr: NaturalExpr) -> str:
    return json.dumps(expr, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _const(value: int) -> NaturalExpr:
    return {"op": "const", "value": value}


def _canonical_variadic(op: str, arguments: list[NaturalExpr]) -> NaturalExpr:
    flat: list[NaturalExpr] = []
    for argument in arguments:
        if argument.get("op") == op:
            flat.extend(argument["args"])
        else:
            flat.append(argument)

    constants = [item["value"] for item in flat if item.get("op") == "const"]
    nonconstants = [item for item in flat if item.get("op") != "const"]
    if op == "add":
        constant = sum(constants)
        if constant:
            nonconstants.append(_const(constant))
        if not nonconstants:
            return _const(0)
    else:
        if any(value == 0 for value in constants):
            return _const(0)
        constant = 1
        for value in constants:
            constant *= value
        if constant != 1 or not nonconstants:
            nonconstants.append(_const(constant))
    ordered = sorted(nonconstants, key=_key)
    if len(ordered) == 1:
        return ordered[0]
    return {"op": op, "args": ordered}


def _normalize_power_spelling(expression: str) -> str:
    normalized = _TEX_EXPONENT.sub(lambda match: f"**({match.group('exponent')})", expression)
    # A single caret is mathematical exponent notation here, never Python XOR.
    return re.sub(r"(?<!\*)\^(?!\*)", "**", normalized)


def _parse_exponent(node: ast.AST, allowed_variables: set[str]) -> dict[str, Any] | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and 0 <= node.value <= MAX_CONSTANT_EXPONENT
    ):
        return {"constant": node.value}
    if isinstance(node, ast.Name) and node.id in allowed_variables:
        return {"variable": node.id, "offset": 0}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        pairs = ((node.left, node.right), (node.right, node.left))
        for variable_node, constant_node in pairs:
            if (
                isinstance(variable_node, ast.Name)
                and variable_node.id in allowed_variables
                and isinstance(constant_node, ast.Constant)
                and isinstance(constant_node.value, int)
                and not isinstance(constant_node.value, bool)
                and 0 <= constant_node.value <= MAX_CONSTANT_EXPONENT
            ):
                return {"variable": variable_node.id, "offset": constant_node.value}
    return None


def parse_natural_power(
    expression: str, allowed_variables: set[str]
) -> NaturalExpr | None:
    """Parse the closed +/*/natural-power fragment, or fail closed.

    At least one power must occur; ordinary polynomials stay on the established
    polynomial path.  Bases are power-free and exponents are constants or one
    declared parameter plus a nonnegative constant.
    """

    if not isinstance(expression, str) or re.search(r"\d_", expression):
        return None
    try:
        tree = ast.parse(_normalize_power_spelling(expression), mode="eval")
    except (SyntaxError, ValueError, TypeError):
        return None
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        return None
    saw_power = False

    def visit(node: ast.AST, *, below_power: bool = False) -> NaturalExpr | None:
        nonlocal saw_power
        if isinstance(node, ast.Expression):
            return visit(node.body, below_power=below_power)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
            and 0 <= node.value <= MAX_LITERAL
        ):
            return _const(node.value)
        if isinstance(node, ast.Name) and node.id in allowed_variables:
            return {"op": "var", "name": node.id}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
            left = visit(node.left, below_power=below_power)
            right = visit(node.right, below_power=below_power)
            if left is None or right is None:
                return None
            return _canonical_variadic(
                "add" if isinstance(node.op, ast.Add) else "mul", [left, right]
            )
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and not below_power:
            base = visit(node.left, below_power=True)
            exponent = _parse_exponent(node.right, allowed_variables)
            if base is None or exponent is None:
                return None
            saw_power = True
            return {"op": "pow", "base": base, "exponent": exponent}
        return None

    parsed = visit(tree)
    return parsed if parsed is not None and saw_power else None


def rename_natural_power(expr: NaturalExpr, mapping: dict[str, str]) -> NaturalExpr:
    op = expr.get("op")
    if op == "const":
        return dict(expr)
    if op == "var":
        return {"op": "var", "name": mapping.get(expr["name"], expr["name"])}
    if op in {"add", "mul"}:
        return _canonical_variadic(
            op, [rename_natural_power(item, mapping) for item in expr["args"]]
        )
    if op == "pow":
        exponent = dict(expr["exponent"])
        if "variable" in exponent:
            exponent["variable"] = mapping.get(exponent["variable"], exponent["variable"])
        return {
            "op": "pow",
            "base": rename_natural_power(expr["base"], mapping),
            "exponent": exponent,
        }
    raise ValueError("invalid natural-power node")


def natural_power_variables(expr: NaturalExpr) -> set[str]:
    op = expr.get("op")
    if op == "const":
        return set()
    if op == "var":
        return {str(expr["name"])}
    if op in {"add", "mul"}:
        return set().union(*(natural_power_variables(item) for item in expr["args"]))
    if op == "pow":
        variables = natural_power_variables(expr["base"])
        exponent = expr["exponent"]
        if "variable" in exponent:
            variables.add(str(exponent["variable"]))
        return variables
    raise ValueError("invalid natural-power node")


def natural_power_expression(expr: NaturalExpr) -> str:
    op = expr.get("op")
    if op == "const":
        return str(expr["value"])
    if op == "var":
        return str(expr["name"])
    if op in {"add", "mul"}:
        separator = "+" if op == "add" else "*"
        return "(" + separator.join(natural_power_expression(item) for item in expr["args"]) + ")"
    if op == "pow":
        exponent = expr["exponent"]
        exponent_text = (
            str(exponent["constant"])
            if "constant" in exponent
            else str(exponent["variable"])
            + (f"+{exponent['offset']}" if exponent.get("offset") else "")
        )
        return f"({natural_power_expression(expr['base'])})^({exponent_text})"
    raise ValueError("invalid natural-power node")


def natural_power_from_typed(value: Any) -> NaturalExpr | None:
    """Validate a canonical natural-power AST without accepting extra fields."""

    if not isinstance(value, dict):
        return None
    op = value.get("op")
    if op == "const" and set(value) == {"op", "value"}:
        literal = value.get("value")
        if isinstance(literal, int) and not isinstance(literal, bool) and 0 <= literal <= MAX_LITERAL:
            return _const(literal)
        return None
    if op == "var" and set(value) == {"op", "name"} and isinstance(value.get("name"), str):
        return {"op": "var", "name": value["name"]}
    if op in {"add", "mul"} and set(value) == {"op", "args"}:
        args = value.get("args")
        if not isinstance(args, list) or len(args) < 2 or len(args) > MAX_AST_NODES:
            return None
        parsed = [natural_power_from_typed(item) for item in args]
        if any(item is None for item in parsed):
            return None
        return _canonical_variadic(op, [item for item in parsed if item is not None])
    if op == "pow" and set(value) == {"op", "base", "exponent"}:
        base = natural_power_from_typed(value.get("base"))
        exponent = value.get("exponent")
        if base is None or not isinstance(exponent, dict):
            return None
        if set(exponent) == {"constant"}:
            constant = exponent.get("constant")
            if not isinstance(constant, int) or isinstance(constant, bool) or not 0 <= constant <= MAX_CONSTANT_EXPONENT:
                return None
            typed_exponent = {"constant": constant}
        elif set(exponent) == {"variable", "offset"}:
            variable, offset = exponent.get("variable"), exponent.get("offset")
            if not isinstance(variable, str) or not variable:
                return None
            if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= MAX_CONSTANT_EXPONENT:
                return None
            typed_exponent = {"variable": variable, "offset": offset}
        else:
            return None
        if any(item.get("op") == "pow" for item in _walk(base)):
            return None
        return {"op": "pow", "base": base, "exponent": typed_exponent}
    return None


def _walk(expr: NaturalExpr):
    yield expr
    if expr.get("op") in {"add", "mul"}:
        for item in expr["args"]:
            yield from _walk(item)
    elif expr.get("op") == "pow":
        yield from _walk(expr["base"])


def _bounded_value(value: int) -> int:
    if value < 0 or value.bit_length() > MAX_EVAL_BITS:
        raise OverflowError("natural-power evaluation exceeds resource cap")
    return value


def natural_power_eval(expr: NaturalExpr, point: dict[str, int]) -> int:
    op = expr["op"]
    if op == "const":
        return int(expr["value"])
    if op == "var":
        return int(point[expr["name"]])
    if op == "add":
        return _bounded_value(
            sum(natural_power_eval(item, point) for item in expr["args"])
        )
    if op == "mul":
        result = 1
        for item in expr["args"]:
            result = _bounded_value(result * natural_power_eval(item, point))
        return result
    exponent = expr["exponent"]
    power = (
        int(exponent["constant"])
        if "constant" in exponent
        else int(point[exponent["variable"]]) + int(exponent["offset"])
    )
    base = natural_power_eval(expr["base"], point)
    if base >= 2 and power * base.bit_length() > MAX_EVAL_BITS:
        raise OverflowError("natural-power evaluation exceeds resource cap")
    return _bounded_value(base**power)


def _as_affine_exponent(expr: NaturalExpr) -> dict[str, Any] | None:
    if expr.get("op") == "const" and expr["value"] <= MAX_CONSTANT_EXPONENT:
        return {"constant": expr["value"]}
    if expr.get("op") == "var":
        return {"variable": expr["name"], "offset": 0}
    if expr.get("op") != "add":
        return None
    variables = [item for item in expr["args"] if item.get("op") == "var"]
    constants = [item["value"] for item in expr["args"] if item.get("op") == "const"]
    if len(variables) != 1 or len(variables) + len(constants) != len(expr["args"]):
        return None
    offset = sum(constants)
    if offset > MAX_CONSTANT_EXPONENT:
        return None
    return {"variable": variables[0]["name"], "offset": offset}


def natural_power_substitute(
    expr: NaturalExpr, mapping: dict[str, NaturalExpr]
) -> NaturalExpr:
    op = expr["op"]
    if op == "const":
        return dict(expr)
    if op == "var":
        return mapping.get(expr["name"], expr)
    if op in {"add", "mul"}:
        return _canonical_variadic(
            op, [natural_power_substitute(item, mapping) for item in expr["args"]]
        )
    base = natural_power_substitute(expr["base"], mapping)
    exponent = expr["exponent"]
    if "constant" in exponent:
        substituted_exponent = dict(exponent)
    else:
        replacement = mapping.get(
            exponent["variable"], {"op": "var", "name": exponent["variable"]}
        )
        substituted_exponent = _as_affine_exponent(replacement)
        if substituted_exponent is None:
            raise ValueError("power exponent substitution left the affine grammar")
        if "constant" in substituted_exponent:
            substituted_exponent["constant"] += exponent["offset"]
            if substituted_exponent["constant"] > MAX_CONSTANT_EXPONENT:
                raise ValueError("power exponent offset exceeds cap")
        else:
            substituted_exponent["offset"] += exponent["offset"]
            if substituted_exponent["offset"] > MAX_CONSTANT_EXPONENT:
                raise ValueError("power exponent offset exceeds cap")
    return {"op": "pow", "base": base, "exponent": substituted_exponent}
