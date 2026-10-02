from __future__ import annotations

import ast
import operator
import re
from fractions import Fraction
from typing import Any, Mapping

from .model import Claim, Finding, Severity


def _exact_divide(left: Any, right: Any) -> Fraction:
    return Fraction(left) / Fraction(right)


BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _exact_divide,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class UnsafeExpression(ValueError):
    pass


MAX_EXPRESSION_CHARACTERS = 4096
MAX_AST_NODES = 512
MAX_NUMERIC_BITS = 1_000_000
MAX_DECIMAL_EXPONENT = 100_000
DECIMAL_LITERAL = re.compile(
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?\Z"
)


def _bounded(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        bits = value.bit_length()
    elif isinstance(value, Fraction):
        bits = max(value.numerator.bit_length(), value.denominator.bit_length())
    else:
        raise UnsafeExpression(f"unsupported computed value {type(value).__name__}")
    if bits > MAX_NUMERIC_BITS:
        raise UnsafeExpression("computed numeric value exceeds the resource bound")
    return value


def _render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        return f"{value.numerator}/{value.denominator}"
    raise UnsafeExpression(f"unsupported arithmetic contract value {value!r}")


def _normalize_bindings(bindings: Any) -> dict[str, int | Fraction | bool]:
    if not isinstance(bindings, Mapping):
        raise UnsafeExpression("bindings must be an object")
    normalized: dict[str, int | Fraction | bool] = {}
    for name, value in bindings.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise UnsafeExpression("binding names must be identifiers")
        normalized[name] = _number(value)
    return normalized


def canonical_arithmetic_proposition(
    expression: str,
    expected: Any,
    *,
    bindings: Mapping[str, Any] | None = None,
) -> str:
    if not isinstance(expression, str) or not expression.strip():
        raise UnsafeExpression("expression must be a nonempty string")
    if "#" in expression:
        raise UnsafeExpression("comments are forbidden in checked arithmetic expressions")
    try:
        expression_tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise UnsafeExpression("expression is not valid Python arithmetic syntax") from error
    normalized_bindings = _normalize_bindings(bindings or {})
    rendered_bindings = ", ".join(
        f"{name}={_render_scalar(normalized_bindings[name])}" for name in sorted(normalized_bindings)
    )
    rendered_expression = expression.strip()
    if isinstance(expression_tree.body, (ast.Compare, ast.BoolOp)):
        rendered_expression = f"({rendered_expression})"
    base = f"{rendered_expression} == {_render_scalar(expected)}"
    if rendered_bindings:
        base = f"under [{rendered_bindings}], {base}"
    return base


def _number(value: Any) -> int | Fraction | bool:
    if isinstance(value, bool):
        return _bounded(value)
    if isinstance(value, int):
        return _bounded(value)
    if isinstance(value, Fraction):
        return _bounded(value)
    if isinstance(value, float):
        raise UnsafeExpression("floating contract values are forbidden; use exact integers or Fraction values")
    raise UnsafeExpression(f"unsupported literal {value!r}")


def _exact_decimal_literal(source: str) -> Fraction:
    cleaned = source.replace("_", "")
    match = DECIMAL_LITERAL.fullmatch(cleaned)
    if match is None:
        raise UnsafeExpression("floating literal is not an exact decimal number")
    exponent_text = match.group(1)
    if exponent_text:
        digits = exponent_text.lstrip("+-")
        if len(digits) > 6 or abs(int(exponent_text)) > MAX_DECIMAL_EXPONENT:
            raise UnsafeExpression("decimal exponent exceeds the resource bound")
    try:
        return _bounded(Fraction(cleaned))
    except (ValueError, ZeroDivisionError) as error:
        raise UnsafeExpression("floating literal is not an exact decimal number") from error


def _typed_equal(left: Any, right: Any) -> bool:
    left_boolean = isinstance(left, bool)
    right_boolean = isinstance(right, bool)
    if left_boolean != right_boolean:
        raise UnsafeExpression("Boolean and numeric values cannot be compared for equality")
    return left == right


def safe_eval(expression: str, bindings: Mapping[str, Any] | None = None) -> Any:
    if not isinstance(expression, str) or len(expression) > MAX_EXPRESSION_CHARACTERS:
        raise UnsafeExpression("expression is not a string within the size bound")
    if "#" in expression:
        raise UnsafeExpression("comments are forbidden in checked arithmetic expressions")
    bindings = _normalize_bindings(bindings or {})
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise UnsafeExpression("expression exceeds the AST-node bound")

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, float):
                source = ast.get_source_segment(expression, node)
                if not source:
                    raise UnsafeExpression("floating literal has no exact source representation")
                return _exact_decimal_literal(source)
            return _number(node.value)
        if isinstance(node, ast.Name):
            if node.id not in bindings:
                raise UnsafeExpression(f"unbound name {node.id}")
            return _number(bindings[node.id])
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARYOPS:
            operand = visit(node.operand)
            if isinstance(operand, bool):
                raise UnsafeExpression("Boolean values cannot be coerced to numbers")
            return _bounded(UNARYOPS[type(node.op)](operand))
        if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(left, bool) or isinstance(right, bool):
                raise UnsafeExpression("Boolean values cannot be coerced to numbers")
            if isinstance(node.op, ast.Pow) and (not isinstance(right, int) or abs(right) > 1000):
                raise UnsafeExpression("exponent outside safety bound")
            if isinstance(node.op, ast.Pow) and isinstance(left, (int, Fraction)):
                left_bits = (
                    left.bit_length()
                    if isinstance(left, int)
                    else max(left.numerator.bit_length(), left.denominator.bit_length())
                )
                left_bits = max(left_bits, 1)
                if left_bits * max(abs(right), 1) > MAX_NUMERIC_BITS:
                    raise UnsafeExpression("power result exceeds the resource bound")
            return _bounded(BINOPS[type(node.op)](left, right))
        if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators):
            left = visit(node.left)
            for operation, comparator in zip(node.ops, node.comparators):
                if type(operation) not in CMPOPS:
                    raise UnsafeExpression(
                        f"unsupported comparison operator {type(operation).__name__}"
                    )
                right = visit(comparator)
                if isinstance(operation, ast.Eq):
                    comparison = _typed_equal(left, right)
                elif isinstance(operation, ast.NotEq):
                    comparison = not _typed_equal(left, right)
                else:
                    if isinstance(left, bool) or isinstance(right, bool):
                        raise UnsafeExpression("Boolean values cannot be ordered as numbers")
                    comparison = CMPOPS[type(operation)](left, right)
                if not comparison:
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [visit(value) for value in node.values]
            if not all(isinstance(value, bool) for value in values):
                raise UnsafeExpression("Boolean operators require Boolean operands")
            return all(values) if isinstance(node.op, ast.And) else any(values)
        raise UnsafeExpression(f"unsupported syntax {type(node).__name__}")

    return visit(tree)


def validate_arithmetic_claim(claim: Claim) -> tuple[list[Finding], bool]:
    expression = claim.payload.get("expression", "")
    if not isinstance(expression, str) or not expression.strip():
        return [Finding("ARITHMETIC_INPUT_INVALID", Severity.HARD, "Missing expression.", claim.claim_id)], False
    expected_value = claim.payload.get("expected", True)
    bindings_value = claim.payload.get("bindings", {})
    try:
        normalized_expected = _number(expected_value)
        normalized_bindings = _normalize_bindings(bindings_value)
        canonical = canonical_arithmetic_proposition(
            expression,
            expected_value,
            bindings=bindings_value,
        )
    except UnsafeExpression as error:
        return [Finding("ARITHMETIC_INPUT_INVALID", Severity.HARD, str(error), claim.claim_id)], False
    if " ".join(claim.proposition.split()) != " ".join(canonical.split()):
        return [
            Finding(
                "ARITHMETIC_PROPOSITION_MISMATCH",
                Severity.HARD,
                "The released proposition is not the canonical statement checked by the arithmetic verifier.",
                claim.claim_id,
                {"canonical_proposition": canonical},
            )
        ], False
    try:
        actual = safe_eval(expression, normalized_bindings)
        base_truth = _typed_equal(actual, normalized_expected)
    except (SyntaxError, ArithmeticError, RecursionError, UnsafeExpression) as error:
        return [Finding("ARITHMETIC_INPUT_INVALID", Severity.HARD, str(error), claim.claim_id)], False
    claim_truth = base_truth if claim.polarity else not base_truth
    if not claim_truth:
        return [
            Finding(
                "ARITHMETIC_CLAIM_FALSE",
                Severity.HARD,
                "Checked arithmetic does not satisfy the claim's declared polarity.",
                claim.claim_id,
                {
                    "expression": expression,
                    "actual": str(actual),
                    "expected": str(normalized_expected),
                    "polarity": claim.polarity,
                    "bindings": {name: _render_scalar(value) for name, value in normalized_bindings.items()},
                },
            )
        ], False
    return [], True


PLAIN_EQUALITY = re.compile(
    r"(?<![A-Za-z0-9_])(?P<left>[()0-9+*/.\-\s]{3,}?)\s*=\s*(?P<right>-?\d+(?:\.\d+)?)"
)


def scan_plain_equalities(text: str) -> list[dict[str, Any]]:
    """Find objectively false plain-text arithmetic equalities.

    This intentionally ignores LaTeX and symbolic variables. It is a high-precision,
    low-coverage verifier, not a natural-language truth classifier.
    """
    findings: list[dict[str, Any]] = []
    normalized = text.replace("×", "*").replace("÷", "/")
    for match in PLAIN_EQUALITY.finditer(normalized):
        left = match.group("left").strip()
        right = match.group("right")
        try:
            actual = safe_eval(left)
            expected = safe_eval(right)
        except (SyntaxError, ArithmeticError, UnsafeExpression):
            continue
        if actual != expected:
            findings.append(
                {
                    "span": [match.start(), match.end()],
                    "text": match.group(0),
                    "left_value": str(actual),
                    "right_value": str(expected),
                }
            )
    return findings
