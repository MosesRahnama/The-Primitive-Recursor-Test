"""Read every written form of a polynomial interpretation into one map.

A blind reader copies a response's interpretation verbatim, so the written form
carries layout (bullets, LaTeX alignment, backticks, bold), a value wrapper
(``I``, ``w``, ``mu``, norm bars), a symbol spelling from the prompt surface
(``banana`` for ``recDelta``), and argument names chosen by the response.  This
module removes that presentation dress and returns, for each declared signature
symbol, the argument names as written and the expression as written.

The module decides no mathematics.  It never invents a missing symbol, never
renames a variable itself, and never chooses between two contradictory reads of
one symbol: the consumer either sees one definition per declared symbol or it
sees an incomplete map, and an incomplete map stays undecided.  Turning an
expression into a polynomial stays with :mod:`tgc.canonical`.

Argument names are returned in written order.  The canonicalizer maps them to
the contract's parameter names by position, so ``G(y, v)`` and ``G(a, b)``
produce the same typed definition.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .canonical import fold_presentation, fold_subscript_digits
from .registry import fold_glyph_tokens

# Value wrappers observed on responses: the response writes the interpretation
# value of a parameter as ``I(t)``, ``w(t)``, ``mu(t)``, ``φ(t)``.  A wrapper is
# only stripped when it directly wraps a DECLARED symbol or a declared
# parameter, so an unknown call still fails the closed grammar downstream.
DEFAULT_WRAPPERS = (
    "I",
    "W",
    "M",
    "size",
    "f",
    "w",
    "mu",
    "μ",
    "phi",
    "φ",
    "interp",
    "interpret",
    "weight",
    "measure",
    "value",
    "val",
    "eval",
)

_OPERATOR = re.compile(r":=|\u21a6|\u2192|(?<![<>=!:])=(?!=)")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_SEARCH_WINDOW = 240
_SEPARATOR_CHARS = frozenset(" \t\r\n&]})⟧‖|,:;.\\!?")
_DELIMITER_CHARS = frozenset("([{|‖⟦")

_PROSE_REFERENCE = (
    r"[A-Za-zφμ][A-Za-z0-9_]*"
    r"(?:(?:\s*\([^()]*\))|(?:\s+[A-Za-z0-9_]+){0,4}?)"
)
_PROSE_INTERPRET = re.compile(
    r"\binterpret(?:s|ed|ing)?\s+"
    rf"(?P<lhs>{_PROSE_REFERENCE})"
    r"\s+as\s+",
    re.IGNORECASE,
)
_PROSE_LET = re.compile(
    r"\blet\s+the\s+(?:weight|value|interpretation|measure|size|image)\s+of\s+"
    rf"(?P<lhs>{_PROSE_REFERENCE})"
    r"\s+(?:be|is)\s+",
    re.IGNORECASE,
)


def normalize_written_text(
    text: str, glyph_folds: tuple[tuple[str, str], ...] = ()
) -> str:
    """Fold presentation dress of a written interpretation passage.

    LaTeX commands, markdown code and bold, subscript digits, glyph renames,
    and alignment markers are presentation only.  Operators and numbers are
    untouched.
    """

    value = text.replace("\r\n", "\n").replace("\r", "\n")
    for source, target in (
        ("\\llbracket", "⟦"),
        ("\\rrbracket", "⟧"),
        ("\\lVert", "‖"),
        ("\\rVert", "‖"),
        ("\\lvert", "|"),
        ("\\rvert", "|"),
        ("[\\![", "⟦"),
        ("]\\!]", "⟧"),
    ):
        value = value.replace(source, target)
    # Emphasis stripping is OFF so `2**3` keeps its value; bold is removed only
    # when it wraps a complete run of text.
    value = fold_presentation(value, markdown_emphasis=False)
    value = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"\1", value, flags=re.DOTALL)
    value = value.replace("$", "").replace("`", "")
    value = re.sub(r"\\(?:begin|end)\{[^{}]*\}", "\n", value)
    value = value.replace("\\\\", "\n")
    value = value.replace("\\mapsto", "↦").replace("\\to", "→")
    value = value.replace("&", " ")
    value = fold_subscript_digits(value)
    value = value.replace("\\Delta", "Δ").replace("\\delta", "delta")
    value = fold_glyph_tokens(value, glyph_folds)
    return value


def _rewrite_prose(value: str) -> str:
    """Rewrite the two prose assignment forms into ``=`` statements."""

    value = _PROSE_INTERPRET.sub(r"\g<lhs> = ", value)
    value = _PROSE_LET.sub(r"\g<lhs> = ", value)
    value = re.sub(r"\bplus\b", "+", value, flags=re.IGNORECASE)
    value = re.sub(r"\btimes\b", "*", value, flags=re.IGNORECASE)
    value = re.sub(r"\bmultiplied\s+by\b", "*", value, flags=re.IGNORECASE)
    return value


def _matching_paren(value: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(value)):
        char = value[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _parameters_after(
    value: str, index: int, symbols: set[str]
) -> tuple[list[str], int]:
    """Argument names written after a symbol, and the reference end offset."""

    size = len(value)
    cursor = index
    # A bracket or norm may close around the symbol before its argument list
    # (`[F](x, y, n)`, `|S|(t)`), so step over that closer first.
    while True:
        while cursor < size and value[cursor] in " \t":
            cursor += 1
        if cursor < size and value[cursor] in ")]}⟧‖|":
            cursor += 1
            continue
        break
    if cursor < size and value[cursor] == "(":
        close = _matching_paren(value, cursor)
        if close is None:
            return [], index
        inner = fold_subscript_digits(value[cursor + 1 : close])
        names = [token for token in _WORD.findall(inner)]
        return names, close + 1
    names: list[str] = []
    while cursor < size:
        if value[cursor] in " \t":
            cursor += 1
            continue
        match = _WORD.match(value, cursor)
        if match is None:
            break
        token = match.group(0)
        if token in symbols:
            break
        names.append(token)
        cursor = match.end()
        if len(names) >= 8:
            break
    return names, cursor


def _only_separators(value: str, start: int, end: int) -> bool:
    return all(char in _SEPARATOR_CHARS for char in value[start:end])


def _reference_start(value: str, symbol_start: int, wrappers: frozenset[str]) -> int:
    """Extend a symbol token start left over the notation that wraps it.

    Only notation DIRECTLY attached to the symbol is consumed.  A symmetric
    norm bar is attached when it touches the symbol, so ``‖plum‖`` keeps its
    opening bar while the CLOSING bar of the previous expression, separated by
    a newline, is left with that expression.
    """

    index = symbol_start
    while index > 0:
        char = value[index - 1]
        if char in _DELIMITER_CHARS:
            index -= 1
            continue
        if char in " \t\r\n":
            cursor = index
            while cursor > 0 and value[cursor - 1] in " \t\r\n":
                cursor -= 1
            match = re.search(r"([A-Za-zφμ]+)$", value[:cursor])
            if match is not None and match.group(1) in wrappers:
                index = cursor
                continue
            break
        match = re.search(r"([A-Za-zφμ]+)$", value[:index])
        if match is not None and match.group(1) in wrappers:
            index = match.start()
            continue
        break
    return index


def _find_reference(
    value: str, operator_start: int, symbols: set[str], wrappers: frozenset[str]
) -> tuple[int, str, list[str]] | None:
    window_start = max(0, operator_start - _SEARCH_WINDOW)
    window = value[window_start:operator_start]
    symbol: str | None = None
    symbol_start = 0
    symbol_end = 0
    for match in reversed(list(_WORD.finditer(window))):
        token = match.group(0)
        if token in symbols:
            symbol = token
            symbol_start = window_start + match.start()
            symbol_end = window_start + match.end()
            break
    if symbol is None:
        return None
    parameters, reference_end = _parameters_after(value, symbol_end, symbols)
    if not _only_separators(value, reference_end, operator_start):
        return None
    start = _reference_start(value, symbol_start, wrappers)
    return start, symbol, parameters


def _unmatched_close(value: str, close: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{", "⟧": "⟦"}
    if close in pairs:
        return value.count(close) > value.count(pairs[close])
    return False


def _clean_expression(value: str) -> str:
    """Trim separators and dangling delimiters around an expression."""

    text = value.strip().strip("&").strip()
    text = text.lstrip("&,:;. ")
    while text:
        last = text[-1]
        # A markdown bullet list flattens to "...expr\n- next symbol = ...".  The
        # reference scan ends one definition at the start of the next symbol, so the
        # bullet marker that introduced it is left dangling on the previous
        # expression.  No well-formed arithmetic expression ends in an operator, so
        # dropping it never removes written mathematics.
        if last in ",;.*&:\\-":
            text = text[:-1].rstrip()
            continue
        if last in ")]}⟧" and _unmatched_close(text, last):
            text = text[:-1].rstrip()
            continue
        if last in "|‖" and text.count(last) % 2 == 1:
            text = text[:-1].rstrip()
            continue
        break
    return text


def parse_written_interpretations(
    text: str,
    *,
    symbols: Iterable[str] = (),
    glyph_folds: tuple[tuple[str, str], ...] = (),
    wrapper_names: Iterable[str] = (),
) -> dict[str, dict[str, Any]]:
    """Return the written definition of every declared symbol, or an empty map.

    Each value carries ``parameters`` (argument names in written order),
    ``expression`` (the right side as written), and ``raw_reference`` (the left
    side as written).  When one symbol is written twice the later definition
    wins, which matches the pre-existing reader behavior.  A symbol the passage
    never defines is absent, and the consumer keeps the result undecided.
    """

    if not isinstance(text, str) or not text.strip():
        return {}
    declared = {str(symbol) for symbol in symbols}
    if not declared:
        return {}
    wrappers = frozenset(DEFAULT_WRAPPERS) | frozenset(str(name) for name in wrapper_names)
    value = _rewrite_prose(normalize_written_text(text, glyph_folds))

    references: list[tuple[int, int, str, list[str]]] = []
    for match in _OPERATOR.finditer(value):
        found = _find_reference(value, match.start(), declared, wrappers)
        if found is None:
            continue
        reference_start, symbol, parameters = found
        references.append((match.end(), reference_start, symbol, parameters))

    out: dict[str, dict[str, Any]] = {}
    for position, (operator_end, _, symbol, parameters) in enumerate(references):
        end = references[position + 1][1] if position + 1 < len(references) else len(value)
        expression = _clean_expression(value[operator_end:end])
        if not expression:
            continue
        out[symbol] = {
            "parameters": list(parameters),
            "expression": expression,
            "raw_reference": value[references[position][1] : operator_end].strip(),
        }
    return out
