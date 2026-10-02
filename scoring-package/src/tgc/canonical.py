from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .common import canonical_sha256
from .config import InstanceContract
from .natural_power import (
    natural_power_expression,
    parse_natural_power,
    rename_natural_power,
)
from .registry import fold_glyph_tokens, fold_symbol_reference

Monomial = tuple[tuple[str, int], ...]
Polynomial = dict[Monomial, int]


@dataclass(frozen=True)
class CanonicalizationResult:
    # V2-compatible aliases: ``core``/``identity`` remain the assertion core,
    # while v3 consensus groups on mathematical_identity and votes assertion
    # metadata separately.
    core: dict[str, Any]
    identity: str
    mathematical_core: dict[str, Any]
    mathematical_identity: str
    assertion_core: dict[str, Any]
    assertion_identity: str
    transcription_core: dict[str, Any]
    transcription_identity: str
    annotation_payload: dict[str, Any]
    checker_core: dict[str, Any]
    checker_identity: str
    checker_payload: dict[str, Any]
    receipts: list[dict[str, Any]]
    supported: bool
    issues: list[dict[str, str]]


def _poly_add(left: Polynomial, right: Polynomial) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in right.items():
        result[monomial] = result.get(monomial, 0) + coefficient
        if result[monomial] == 0:
            del result[monomial]
    return result


def _poly_mul(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            powers = dict(left_monomial)
            for variable, exponent in right_monomial:
                powers[variable] = powers.get(variable, 0) + exponent
            monomial = tuple(sorted(powers.items()))
            result[monomial] = result.get(monomial, 0) + left_coefficient * right_coefficient
    return {key: value for key, value in result.items() if value != 0}


def parse_polynomial(expr: str, allowed_variables: set[str] | None = None) -> Polynomial | None:
    """Parse exactly the nonnegative integer +/*/parentheses fragment.

    Host-language conveniences such as booleans, numeric underscores, unary plus,
    subtraction, powers, calls, attributes, and comparisons are rejected.
    """
    # Python reads `1_000` as 1000, so an underscore INSIDE a numeric literal
    # must stay rejected. A digit is never the first character of an
    # identifier, so "digit immediately followed by underscore" isolates
    # exactly that case and leaves subscripted parameter names (`t_1`, `t_2`,
    # measured 2026-07-29) usable; undeclared names still fail the
    # allowed_variables check below.
    if re.search(r"\d_", expr):
        return None
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError, TypeError):
        return None

    def visit(node: ast.AST) -> Polynomial | None:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
            and node.value >= 0
        ):
            return {(): node.value} if node.value else {}
        if isinstance(node, ast.Name):
            if allowed_variables is not None and node.id not in allowed_variables:
                return None
            return {((node.id, 1),): 1}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
            left = visit(node.left)
            right = visit(node.right)
            if left is None or right is None:
                return None
            return _poly_add(left, right) if isinstance(node.op, ast.Add) else _poly_mul(left, right)
        return None

    return visit(tree)


def _rename_polynomial(parsed: Polynomial, mapping: dict[str, str]) -> Polynomial:
    renamed: Polynomial = {}
    for monomial, coefficient in parsed.items():
        powers: dict[str, int] = {}
        for variable, exponent in monomial:
            target = mapping.get(variable, variable)
            powers[target] = powers.get(target, 0) + exponent
        key = tuple(sorted(powers.items()))
        renamed[key] = renamed.get(key, 0) + coefficient
    return {key: value for key, value in renamed.items() if value != 0}


def _polynomial_terms(parsed: Polynomial) -> list[dict[str, Any]]:
    return [
        {
            "coefficient": coefficient,
            "powers": [
                {"variable": variable, "exponent": exponent}
                for variable, exponent in monomial
            ],
        }
        for monomial, coefficient in sorted(parsed.items())
    ]


def polynomial_expression(parsed: Polynomial) -> str:
    if not parsed:
        return "0"
    pieces: list[str] = []
    for monomial, coefficient in sorted(parsed.items()):
        factors = [str(coefficient)]
        for variable, exponent in monomial:
            factors.extend([variable] * exponent)
        pieces.append("*".join(factors))
    return "+".join(pieces)


def canonical_polynomial(expr: str, allowed_variables: set[str] | None = None) -> dict[str, Any]:
    parsed = parse_polynomial(expr, allowed_variables)
    if parsed is None:
        return {"status": "unparseable", "raw": expr}
    return {"status": "ok", "terms": _polynomial_terms(parsed)}


def _fold_glyphs(text: str, folds: tuple[tuple[str, str], ...]) -> str:
    return fold_glyph_tokens(text, folds)


def _has_symbol(text: str, symbols: set[str]) -> bool:
    return any(re.search(r"\b" + re.escape(symbol) + r"\b", text) for symbol in symbols)


_SIMPLE_SYMBOL = r"[A-Za-z][A-Za-z0-9]*"
_PRECEDENCE_CHAIN = re.compile(rf"{_SIMPLE_SYMBOL}(?:\s*>\s*{_SIMPLE_SYMBOL})+")
_PRECEDENCE_HIGHER = re.compile(
    rf"(?:give\s+|set\s+)?(?P<left>{_SIMPLE_SYMBOL})\s+"
    rf"(?:is\s+|has\s+)?(?:a\s+)?(?:higher|greater)(?:\s+precedence)?\s+than\s+"
    rf"(?P<rights>{_SIMPLE_SYMBOL}(?:\s+and\s+{_SIMPLE_SYMBOL})*)"
    rf"(?:\s+with\b.*)?",
    re.IGNORECASE,
)
_PRECEDENCE_ABOVE = re.compile(
    rf"(?P<left>{_SIMPLE_SYMBOL})\s+(?:is\s+)?(?:precedence\s+)?above\s+"
    rf"(?P<rights>{_SIMPLE_SYMBOL}(?:\s+and\s+{_SIMPLE_SYMBOL})*)",
    re.IGNORECASE,
)
_PRECEDENCE_MINIMAL = re.compile(
    rf"(?:take\s+|set\s+)?(?P<symbol>{_SIMPLE_SYMBOL})\s+as\s+(?:the\s+)?"
    rf"minimal(?:\s+symbol)?",
    re.IGNORECASE,
)
# Relation vocabulary that must never sit inside a droppable annotation.
_PRECEDENCE_RELATION_WORD = re.compile(
    r"\b(?:above|higher|lower|minimal|maximal|precedence|than|greater|less)\b",
    re.IGNORECASE,
)


def _precedence_clause_accepted(text: str) -> bool:
    """True when a fragment already fullmatches a supported precedence form."""

    return any(
        pattern.fullmatch(text)
        for pattern in (
            _PRECEDENCE_CHAIN,
            _PRECEDENCE_HIGHER,
            _PRECEDENCE_ABOVE,
            _PRECEDENCE_MINIMAL,
        )
    )


def _drop_precedence_annotation(
    text: str, signature_symbols: set[str]
) -> str | None:
    """Drop a trailing parenthetical ANNOTATION from a precedence clause.

    Measured on the 3-pass OOS round (2026-07-29): a response wrote
    ``recDelta above app (for R_rec_succ)``, naming the rule that motivates the
    edge. The parenthetical is a note about WHY the edge is stated, not part of
    the relation, and it defeated the closed parser's fullmatch.

    Bounded and fail-closed: the parenthetical must be the last thing in the
    clause, must be balanced and non-nested, must mention no declared signature
    symbol, and must contain no relation operator or relation word. A clause is
    only rewritten when the remainder then fullmatches a supported form, so a
    fragment the parser already handled, ignored, or rejected is untouched.
    """

    match = re.search(r"\s*\(([^()]*)\)\s*$", text)
    if not match:
        return None
    inner = match.group(1)
    if not inner.strip():
        return None
    if ">" in inner or _has_symbol(inner, signature_symbols):
        return None
    if _PRECEDENCE_RELATION_WORD.search(inner):
        return None
    remainder = text[: match.start()].strip().strip(".:")
    if not remainder or not _precedence_clause_accepted(remainder):
        return None
    return remainder


def precedence_is_total(
    parsed: dict[str, Any], signature_symbols: set[str]
) -> bool:
    """True when a parsed precedence orders EVERY pair of declared symbols."""

    if parsed.get("status") != "ok":
        return False
    closure = {
        (item.get("higher"), item.get("lower"))
        for item in parsed.get("closure") or []
    }
    symbols = sorted(signature_symbols)
    return all(
        left == right
        or (left, right) in closure
        or (right, left) in closure
        for left in symbols
        for right in symbols
    )


_PRESENTATION_WRAPPER_RE = re.compile(
    r"\\(?:texttt|textsf|textrm|textbf|textit|text|mathsf|mathrm|mathtt|mathbf"
    r"|mathit|operatorname)\{([^{}]*)\}"
)
_PRESENTATION_CHARS = {
    " ": " ",  # non-breaking space
    " ": " ",
    " ": " ",  # narrow no-break space
    " ": " ",  # thin space
    "–": "-",  # en dash
    "—": "-",  # em dash
    "‒": "-",  # figure dash
    "‐": "-",  # hyphen
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "′": "'",  # prime
}
_LATEX_SPACING = ("\\qquad", "\\quad", "\\thinspace", "\\,", "\\;", "\\:", "\\!")
_LATEX_MATH_DELIMITERS = ("\\(", "\\)", "\\[", "\\]", "$")


def fold_presentation(text: str, *, markdown_emphasis: bool = True) -> str:
    """One presentation-normalization layer for every closed parser.

    Three parsers each grew their own ad-hoc token list, and every gap between
    them cost a live row: `$...$` broke the interpretation adapter while the
    precedence parser stripped it; `\\(...\\)` broke both the interpretation
    adapter and the checker-string normalizer; Unicode subscripts broke the
    polynomial parser because `t₁` is Unicode category No and therefore not a
    legal Python identifier. Each was a baseline-CORRECT answer refused over
    typography. A single fold makes the token set uniform by construction, so a
    gap can no longer exist in one parser but not another.

    Presentation only: LaTeX math delimiters, spacing commands, and layout
    wrappers; markdown code/emphasis; Unicode spaces, dashes, quotes, and
    subscript digits. Nothing here changes a mathematical operator, a symbol
    name after folding, or a numeric value.

    ``markdown_emphasis`` MUST be False for polynomial expressions: stripping
    ``**`` there would turn ``2**3`` (8) into ``23``, silently changing a value.
    Superscript digits are deliberately NOT folded for the same reason — a
    superscript is an exponent, which is mathematical content, not typography.
    """

    value = text
    for delimiter in _LATEX_MATH_DELIMITERS:
        value = value.replace(delimiter, " " if delimiter.startswith("\\") else "")
    for command in _LATEX_SPACING:
        value = value.replace(command, " ")
    value = value.replace("\\left", "").replace("\\right", "")
    previous = None
    while previous != value:
        previous = value
        value = _PRESENTATION_WRAPPER_RE.sub(r"\1", value)
    value = value.replace("`", "")
    if markdown_emphasis:
        value = value.replace("**", "").replace("__", "")
    for source, target in _PRESENTATION_CHARS.items():
        value = value.replace(source, target)
    # Unicode subscript digits are handled by `fold_subscript_digits`, NOT here:
    # a subscripted parameter must be folded in the declared parameter list and
    # in the expression together, or the two stop matching. That pairing is the
    # dedicated step's job and it publishes its own receipt.
    return value


def parse_precedence(
    text: str,
    *,
    signature_symbols: set[str],
    glyph_folds: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    """Parse a stated precedence into a typed relation graph, fail-closed.

    Accepted syntax is intentionally closed but presentation tolerant: explicit
    chains/lists, markdown bullets, ``higher precedence than``/``above`` prose,
    and an explicitly stated minimal symbol. Term-comparison explanations are
    not mistaken for precedence edges. Unknown tokens in a *bare precedence
    chain* invalidate the whole object, so the parser never bridges across a
    deleted symbol.
    """
    raw = text
    value = _fold_glyphs(text, glyph_folds)
    value = value.replace("$", "").replace("≻", ">").replace("\\succ", ">")
    value = value.replace("`", "")
    # LaTeX inline/display math delimiters carry no relation content. `$` is
    # stripped above; `\(...\)` and `\[...\]` were not, so a precedence written
    # `\(F > G\)` failed the closed parser while the identical `F > G` parsed.
    # Measured 2026-07-30 on a Schema A row whose baseline is CORRECT.
    for _delimiter in ("\\(", "\\)", "\\[", "\\]"):
        value = value.replace(_delimiter, " ")
    # LaTeX-escaped braces are the same glyph as bare braces. A brace group in
    # a chain ("eqW > recΔ > {integrate, merge, delta, app} > void") is a TIER
    # whose members share the same position; the group-chain branch below
    # consumes it. Measured 2026-08-02 on a baseline-correct RPO refused
    # solely because the closed parser rejected the braces.
    value = value.replace("\\{", "{").replace("\\}", "}")
    for command in ("\\qquad", "\\quad", "\\,", "\\;"):
        value = value.replace(command, " ")
    # Layout-only symbol wrappers are safe to remove from a symbol reference.
    # `texttt` must precede `text` in the alternation: the trailing `\{` anchor
    # already prevents `text` from eating the prefix of `\texttt{...}`, but the
    # explicit order documents that a longer command name wins. Measured on the
    # 3-pass OOS round (2026-07-29): a whole precedence chain written
    # `\texttt{recDelta} \;>\; \texttt{app} > ...` failed the closed parser as
    # `malformed_relation_clause` purely because `\texttt` was missing here.
    wrapper = re.compile(
        r"\\(?:texttt|text|mathsf|mathrm|mathtt|mathbf|mathit|operatorname)"
        r"\{([^{}]*)\}"
    )
    previous = None
    while previous != value:
        previous = value
        value = wrapper.sub(r"\1", value)
    value = value.replace("\\Delta", "Δ").replace("\\delta", "delta")
    value = _fold_glyphs(value, glyph_folds)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"(?:>)_\{(?:[^{}]|\{[^{}]*\})*\}", ">", value)
    value = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+\s*[.)]\s*)", "", value)
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"[ \t\f\v]+", " ", value).strip()

    # Numbered lists are accepted only when the response states their direction.
    if ">" not in value and not re.search(
        r"\babove\b|\bhigher\b|\bminimal\b", value, flags=re.IGNORECASE
    ):
        items = re.findall(r"\d+\s*[.)]\s*([A-Za-z][A-Za-z0-9]*)", text)
        low = value.lower()
        descending_markers = (
            "largest to smallest",
            "highest to lowest",
            "descending",
            "largest first",
            "highest first",
        )
        ascending_markers = (
            "smallest to largest",
            "lowest to highest",
            "ascending",
            "smallest first",
            "lowest first",
        )
        descending = any(marker in low for marker in descending_markers)
        ascending = any(marker in low for marker in ascending_markers)
        if len(items) >= 2 and descending != ascending:
            if any(item not in signature_symbols for item in items):
                return {
                    "status": "unparseable",
                    "raw": raw,
                    "reason": "numbered_list_unknown_symbol",
                }
            sequence = items if descending else list(reversed(items))
            value = ">".join(sequence)
        elif items:
            return {
                "status": "unparseable",
                "raw": raw,
                "reason": "numbered_list_direction_missing",
            }

    direct_edges: set[tuple[str, str]] = set()
    previous_head: str | None = None
    relation_syntax_seen = False

    def add_edges(left: str, rights: list[str], reason: str) -> dict[str, Any] | None:
        nonlocal previous_head, relation_syntax_seen
        relation_syntax_seen = True
        unknown = [item for item in [left, *rights] if item not in signature_symbols]
        if unknown:
            return {
                "status": "unparseable",
                "raw": raw,
                "reason": reason,
                "unknown_symbols": sorted(set(unknown)),
            }
        for right in rights:
            direct_edges.add((left, right))
        previous_head = left
        return None

    # Semicolon/newline/comma are presentation separators in the supported
    # grammar. ``and`` remains available inside a prose right-hand list.
    # Separators INSIDE parentheses/brackets never split: a term such as
    # recDelta(b,s,delta(n)) in an explanatory comparison must stay one
    # fragment, or its argument variables leak out as bare tokens and inherit
    # the precedence head (live-round defect, deep-verify probe C6).
    def _split_outside_parens(text: str) -> list[str]:
        parts: list[str] = []
        buffer: list[str] = []
        depth = 0
        for char in text:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            if char in ";,\n" and depth == 0:
                parts.append("".join(buffer))
                buffer = []
            else:
                buffer.append(char)
        parts.append("".join(buffer))
        return [part.strip() for part in parts if part.strip()]

    fragments = []
    for clause in _split_outside_parens(value):
        # Oxford conjunctions join clauses, not symbol names. Strip only before
        # a complete relation, so an unknown or incomplete edge still fails.
        if re.fullmatch(r"and\s+[A-Za-z][A-Za-z0-9]*(?:\s*>\s*[A-Za-z][A-Za-z0-9]*)+\.?", clause):
            clause = re.sub(r"^and\s+", "", clause)
        # Split conjunctions of complete symbolic relations, never a prose
        # right-hand list ("F higher than G and S") or a term's arguments.
        parts = re.split(r"\s+and\s+", clause, flags=re.IGNORECASE)
        symbolic = r"[A-Za-z][A-Za-z0-9]*(?:\s*>\s*[A-Za-z][A-Za-z0-9]*)+"
        if len(parts) > 1 and all(
            re.fullmatch(symbolic, part.strip().rstrip(".")) for part in parts
        ):
            fragments.extend(parts)
        else:
            fragments.append(clause)
    simple_symbol = r"[A-Za-z][A-Za-z0-9]*"
    notation_steps: list[dict[str, str]] = []
    for fragment in fragments:
        fragment = re.sub(r"^\s*(?:then\s+)?", "", fragment, flags=re.IGNORECASE)
        cleaned = fragment.strip().strip(".:")
        if not cleaned:
            continue
        if cleaned.lower() == "then":
            continue
        if not _precedence_clause_accepted(cleaned):
            without_annotation = _drop_precedence_annotation(
                cleaned, signature_symbols
            )
            if without_annotation is not None:
                notation_steps.append(
                    {
                        "operation": "precedence-annotation-drop",
                        "input": cleaned,
                        "output": without_annotation,
                    }
                )
                cleaned = without_annotation

        # Chain with brace-grouped tiers: `a > {b, c} > d` states that every
        # member of one tier is above every member of the next. NO edges are
        # added WITHIN a tier — the braces state co-position, and the safe
        # reading of an unstated internal relation is incomparable-as-stated
        # (a response licensing completions carries that in its quantifier).
        group_token = rf"(?:{simple_symbol}|\{{[^{{}}>]+\}})"
        if "{" in cleaned and re.fullmatch(
            rf"{group_token}(?:\s*>\s*{group_token})+", cleaned
        ):
            tiers: list[list[str]] = []
            for token in re.split(r">", cleaned):
                token = token.strip()
                if token.startswith("{") and token.endswith("}"):
                    members = [
                        member
                        for member in re.split(r"[,\s]+", token[1:-1])
                        if member
                    ]
                else:
                    members = [token]
                if not members or any(
                    not re.fullmatch(simple_symbol, member) for member in members
                ):
                    return {
                        "status": "unparseable",
                        "raw": raw,
                        "reason": "malformed_group_tier",
                    }
                tiers.append(members)
            unknown = sorted(
                {
                    member
                    for tier in tiers
                    for member in tier
                    if member not in signature_symbols
                }
            )
            if unknown:
                return {
                    "status": "unparseable",
                    "raw": raw,
                    "reason": "relation_unknown_symbol",
                    "unknown_symbols": unknown,
                }
            relation_syntax_seen = True
            for upper, lower in zip(tiers, tiers[1:]):
                for left in upper:
                    for right in lower:
                        direct_edges.add((left, right))
            previous_head = tiers[0][0]
            continue

        # Exact chain/list: every token must be a declared signature symbol.
        if re.fullmatch(rf"{simple_symbol}(?:\s*>\s*{simple_symbol})+", cleaned):
            tokens = [token.strip() for token in cleaned.split(">")]
            error = add_edges(tokens[0], tokens[1:], "relation_unknown_symbol")
            if error:
                return error
            # A>B>C is a chain, not A>{B,C}; repair the direct edge shape.
            direct_edges.difference_update((tokens[0], item) for item in tokens[2:])
            for left, right in zip(tokens, tokens[1:]):
                direct_edges.add((left, right))
            continue

        prose = re.fullmatch(
            rf"(?:give\s+|set\s+)?(?P<left>{simple_symbol})\s+"
            rf"(?:is\s+|has\s+)?(?:a\s+)?(?:higher|greater)(?:\s+precedence)?\s+than\s+"
            rf"(?P<rights>{simple_symbol}(?:\s+and\s+{simple_symbol})*)"
            rf"(?:\s+with\b.*)?",
            cleaned,
            flags=re.IGNORECASE,
        ) or re.fullmatch(
            rf"(?P<left>{simple_symbol})\s+(?:is\s+)?(?:precedence\s+)?above\s+"
            rf"(?P<rights>{simple_symbol}(?:\s+and\s+{simple_symbol})*)",
            cleaned,
            flags=re.IGNORECASE,
        ) or re.fullmatch(
            rf"(?P<left>{simple_symbol})\s+dominates?\s+"
            rf"(?P<rights>{simple_symbol}(?:\s+and\s+{simple_symbol})*)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if prose:
            rights = [
                item
                for item in re.split(
                    r"\s*(?:,|and)\s*",
                    prose.group("rights"),
                    flags=re.IGNORECASE,
                )
                if item
            ]
            error = add_edges(prose.group("left"), rights, "prose_pair_unknown_symbol")
            if error:
                return error
            continue

        minimal = re.fullmatch(
            rf"(?:take\s+|set\s+)?(?P<symbol>{simple_symbol})\s+as\s+(?:the\s+)?minimal(?:\s+symbol)?",
            cleaned,
            flags=re.IGNORECASE,
        )
        if minimal:
            symbol = minimal.group("symbol")
            relation_syntax_seen = True
            if symbol not in signature_symbols:
                return {
                    "status": "unparseable",
                    "raw": raw,
                    "reason": "minimal_unknown_symbol",
                    "unknown_symbols": [symbol],
                }
            for other in signature_symbols:
                if other != symbol:
                    direct_edges.add((other, symbol))
            previous_head = None
            continue

        # ``F > G, S``: a bare symbol inherits the last explicit head.
        if re.fullmatch(simple_symbol, cleaned):
            if previous_head is not None:
                error = add_edges(previous_head, [cleaned], "bare_token_unknown_symbol")
                if error:
                    return error
                continue
            if cleaned not in signature_symbols:
                # Symbol-free prose often contains a single ordinary word.
                continue

        if ">" in cleaned:
            chunks = [chunk.strip() for chunk in cleaned.split(">")]
            if all(re.fullmatch(simple_symbol, chunk) for chunk in chunks):
                # This is relation syntax, even if one token is unknown.
                error = add_edges(chunks[0], chunks[1:], "relation_unknown_symbol")
                if error:
                    return error
                continue
            # A term comparison (arguments, parentheses, or a stated proof
            # reason) is not a precedence declaration. It contributes no edge.
            term_cues = ("(", ")", " because ", " subterm ", " then ")
            if any(cue in f" {cleaned.lower()} " for cue in term_cues):
                continue
            return {
                "status": "unparseable",
                "raw": raw,
                "reason": "malformed_relation_clause",
            }

        if re.search(
            r"\bhigher(?:\s+precedence)?\b|\babove\b|\bminimal\b",
            cleaned,
            flags=re.IGNORECASE,
        ):
            return {
                "status": "unparseable",
                "raw": raw,
                "reason": "unrecognized_relation_prose",
            }
        # Remaining prose is explanatory. It is retained in source evidence but
        # is not allowed to invent or modify a relation edge.

    if not direct_edges:
        return {
            "status": "unparseable",
            "raw": raw,
            "reason": "no_signature_edge" if relation_syntax_seen else "no_relation_syntax",
        }

    closure = set(direct_edges)
    changed = True
    while changed:
        changed = False
        additions = {
            (left, right)
            for left, middle in closure
            for middle_2, right in closure
            if middle == middle_2 and (left, right) not in closure
        }
        if additions:
            closure.update(additions)
            changed = True
    if any(left == right for left, right in closure):
        return {"status": "unparseable", "raw": raw, "reason": "precedence_cycle"}
    parsed: dict[str, Any] = {
        "status": "ok",
        "direct_relations": [
            {"higher": left, "lower": right} for left, right in sorted(direct_edges)
        ],
        "closure": [
            {"higher": left, "lower": right} for left, right in sorted(closure)
        ],
    }
    if notation_steps:
        parsed["notation_steps"] = notation_steps
    return parsed

def _typed_order_mode(text: str) -> str:
    """Classify an explicitly stated order without substring guessing.

    The return value is a closed semantic tag.  In particular, negated lex,
    colexicographic, reverse, and componentwise orders are *not* forward lex.
    Callers may understand those tags while still declining to implement them.
    """

    low = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if re.search(
        r"\b(?:not|without)\b|\bnon\s+lex|\bnonlex|\bisn\s+t\b|\bis\s+not\b",
        low,
    ):
        return "negated"
    if re.search(r"\bcolex", low):
        return "colex"
    if re.search(
        r"\b(?:reverse|reversed|backward|backwards)\b|\bright\s+to\s+left\b",
        low,
    ):
        return "reverse"
    if re.search(r"\b(?:componentwise|product|pareto)\b", low):
        return "componentwise"

    has_lex = re.search(r"\blex(?:icographic(?:ally)?)?\b", low) is not None
    has_multiset = re.search(r"\bmultiset\b", low) is not None
    if has_lex and has_multiset:
        return "lex_of_multiset"
    if has_lex:
        return "lex"
    if has_multiset:
        return "multiset"
    if re.search(r"\bleft\s+to\s+right\b", low):
        return "lex"
    if re.search(
        r"(?:\bargument\s*)?(?:\d+|first|second|third|fourth)\s+"
        r"(?:argument\s+)?first\b",
        low,
    ):
        return "lex"
    if re.search(
        r"\b(?:prioriti[sz](?:e|es|ed|ing)|compare(?:s|d|ing)?|"
        r"decisive)\b.{0,32}\b(?:argument|coordinate)\s+"
        r"(?:\d+|first|second|third|fourth)\b"
        r"|\b(?:prioriti[sz](?:e|es|ed|ing)|compare(?:s|d|ing)?)\b.{0,20}"
        r"\b(?:\d+|first|second|third|fourth)\s+(?:argument|coordinate)\b"
        r"|\b(?:\d+|first|second|third|fourth)\s+"
        r"(?:argument|coordinate)\b.{0,20}\bdecisive\b",
        low,
    ):
        return "lex"
    if re.search(
        r"\bfirst two arguments?\b.{0,40}\bequal\b.{0,40}"
        r"\bthird argument\b.{0,40}\b(?:decreas|subterm)",
        low,
    ):
        return "lex"
    return "unparseable"


def canonical_status(text: str | None) -> dict[str, Any]:
    if text is None:
        return {"mode": "unspecified"}
    if not isinstance(text, str):
        return {"mode": "unparseable", "type": type(text).__name__}
    if not text.strip():
        return {"mode": "unspecified"}
    raw = text
    low = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    mode = _typed_order_mode(text)
    if mode == "unparseable":
        return {"mode": "unparseable", "raw": raw}
    order: list[int] | None = None
    ordinal_words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
    }
    token = r"(?:\d+|first|second|third|fourth)"

    def tokens_of(fragment: str) -> list[str]:
        return re.findall(rf"\b({token})\b", fragment)

    chain: list[str] = []
    # "3 \succ_{lex} 1 \succ_{lex} 2": digits only inside an explicit
    # succ-chain. Arity remarks such as "succ has arity 1" contribute nothing.
    succ_chain = re.search(
        r"(?<![a-z0-9])\d+(?:\s+succ(?:\s+lex)?\s+\d+)+(?![a-z0-9])", low
    )
    if succ_chain:
        chain = re.findall(r"\d+", succ_chain.group(0))
    if not chain:
        # "argument order 3, then 1, then 2": argument references joined by
        # "then". Numbers elsewhere in the sentence are never collected.
        then_chain = re.search(
            rf"\b{token}(?:\s+argument)?(?:\s+then\s+(?:the\s+)?(?:argument\s+)?"
            rf"{token}(?:\s+argument)?)+\b",
            low,
        )
        if then_chain and not re.search(
            r"\bfirst two arguments?\b.{0,40}\bequal\b", low
        ):
            chain = tokens_of(then_chain.group(0))
    explicit = re.findall(r"(?:argument\s*)?(\d+|first|second|third|fourth)\s+(?:argument\s+)?first", low)
    prioritized = re.findall(
        r"(?:prioriti[sz](?:e|es|ed|ing)|compare(?:s|d|ing)?)\s+(?:the\s+)?"
        r"(?:argument|coordinate)\s+(\d+|first|second|third|fourth)"
        r"|(?:prioriti[sz](?:e|es|ed|ing)|compare(?:s|d|ing)?)\s+(?:the\s+)?"
        r"(\d+|first|second|third|fourth)\s+(?:argument|coordinate)"
        r"|(?:the\s+)?(\d+|first|second|third|fourth)\s+"
        r"(?:argument|coordinate)\s+(?:is\s+)?decisive",
        low,
    )
    equal_prefix_then = re.search(
        r"\bfirst two arguments?\b.{0,40}\bequal\b.{0,40}"
        r"\b(third|3) argument\b.{0,40}\b(?:decreas|subterm)",
        low,
    )
    if equal_prefix_then:
        # Equal first two arguments with a decreasing third argument is the
        # description of ordinary left-to-right lexicographic comparison.
        order = [1]
    elif len(chain) >= 2:
        order = []
        for item in chain:
            value = int(item) if item.isdigit() else ordinal_words[item]
            if value not in order:
                order.append(value)
    elif explicit:
        order = []
        for item in explicit:
            value = int(item) if item.isdigit() else ordinal_words[item]
            if value not in order:
                order.append(value)
    elif prioritized:
        order = []
        for pair in prioritized:
            item = next(value for value in pair if value)
            value = int(item) if item.isdigit() else ordinal_words[item]
            if value not in order:
                order.append(value)
    elif re.search(r"\bleft\s+to\s+right\b", low):
        order = [1]
    result: dict[str, Any] = {"mode": mode}
    if order is not None:
        result["argument_order"] = order
    return result


# Measured on the 3-pass paired OOS round (2026-07-29): `w` (weight) is as
# common a spelling of the interpretation value as `I`, and blocked whole
# interpretations on its own.
_INTERPRETATION_WRAPPERS = (
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
)

# Unicode subscript digits are Unicode category `No`, so `t₁` is not a legal
# Python identifier and `ast.parse` rejects the whole expression before the
# closed polynomial grammar is ever consulted. They are pure notation for an
# indexed parameter name, so they fold to the ASCII digit. Superscripts are
# NOT folded: a superscript would mean an exponent, which is mathematics.
_SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def fold_subscript_digits(text: str) -> str:
    """ASCII-fold Unicode subscript digits inside identifiers."""

    return text.translate(_SUBSCRIPT_DIGITS)


def _matching_paren_index(value: str, open_index: int) -> int | None:
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


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in value:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def fold_pow_calls(value: str) -> str:
    """Rewrite ``pow(base, exponent)`` calls as ``(base)^(exponent)``.

    The closed natural-power grammar has no function-call node, so a response
    that spells exponentiation as ``pow`` reached a different AST from one that
    writes ``^``.  The fold binds to the literal name ``pow`` and splits its two
    arguments at the top-level comma only; every other call stays a call and
    still fails the closed grammar.
    """

    out: list[str] = []
    index = 0
    call = re.compile(r"\bpow\s*\(")
    while index < len(value):
        match = call.search(value, index)
        if match is None:
            out.append(value[index:])
            break
        out.append(value[index : match.start()])
        open_index = match.end() - 1
        close_index = _matching_paren_index(value, open_index)
        if close_index is None:
            out.append(value[match.start() :])
            break
        parts = _split_top_level(value[open_index + 1 : close_index])
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            out.append(f"({parts[0].strip()})^({parts[1].strip()})")
        else:
            out.append(value[match.start() : close_index + 1])
        index = close_index + 1
    return "".join(out)


def normalize_interpretation_expression(
    expression: str,
    parameters: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    """Normalize source-level interpretation notation into the closed grammar.

    This is deliberately a notation adapter, not a symbolic-algebra guesser.
    It unwraps only conventional interpretation-value notations observed in
    the blind rounds (``I(x)``, ``size(x)``, ``f(x)``, norm bars), semantic brackets,
    multiplication glyphs, and unambiguous implicit multiplication. Operators
    outside the nonnegative ``+``/``*`` fragment (for example ``^``) remain and
    are rejected by :func:`parse_polynomial`.
    """
    # One shared presentation layer, so a token handled by any parser is handled
    # by ALL of them. Emphasis stripping is OFF here: `2**3` must not become 23.
    value = fold_presentation(expression, markdown_emphasis=False)
    steps: list[dict[str, Any]] = []
    if value != expression:
        steps.append(
            {
                "operation": "presentation-fold",
                "input": expression,
                "output": value,
            }
        )

    def apply(operation: str, updated: str) -> None:
        nonlocal value
        if updated != value:
            steps.append(
                {
                    "operation": operation,
                    "input": value,
                    "output": updated,
                }
            )
            value = updated

    # First, so every parameter-keyed rewrite below sees the same spelling the
    # caller folded into the declared parameter list.
    apply("subscript-digit-fold", fold_subscript_digits(value))
    # LaTeX math delimiters carry no mathematical content and are stripped by
    # `parse_precedence` and `_normalize_checker_string` already; this adapter
    # was the one place that did not, so a pass that wrapped each expression in
    # `$...$` failed to canonicalize while a pass writing the SAME mathematics
    # bare succeeded. Measured 2026-07-30 on
    # `claude-opus-4.6__2026-03-26T06-55-01`: three passes transcribed an
    # identical, valid polynomial interpretation; only e03 used `$...$`, its
    # checker input diverged, consensus failed, and a baseline-CORRECT answer
    # was refused a verdict.
    apply("latex-math-delimiter-strip", value.replace("$", ""))
    apply(
        "multiplication-glyph-fold",
        value.replace("\\times", "*")
        .replace("\\cdot", "*")
        .replace("·", "*")
        .replace("×", "*"),
    )
    # A response may spell the natural power as a call.  The fold runs before
    # the parameter wrappers are unwrapped, so the two arguments keep their
    # spelling until the shared wrapper step below handles them.
    apply("pow-call-fold", fold_pow_calls(value))
    apply(
        "latex-layout-strip",
        value.replace("\\left", "").replace("\\right", ""),
    )
    # LaTeX spacing commands are pure layout between a coefficient and its
    # factor ("2\,w(t)"); `parse_precedence` already strips these and the
    # interpretation adapter must agree (measured 2026-07-29).
    spaced = value
    for command in ("\\qquad", "\\quad", "\\,", "\\;", "\\:", "\\!"):
        spaced = spaced.replace(command, " ")
    apply("latex-spacing-strip", spaced)
    for parameter in sorted(parameters, key=len, reverse=True):
        escaped = re.escape(parameter)
        updated = re.sub(rf"⟦\s*{escaped}\s*⟧", parameter, value)
        apply("semantic-bracket-unwrapping", updated)
        # SA live-round batch 2 (2026-07-27, measured forms):
        # LaTeX-macro semantic brackets and size/absolute-value bars around a
        # declared parameter are interpretation-value notation, not algebra.
        updated = re.sub(
            rf"\\llbracket\s*{escaped}\s*\\rrbracket", parameter, value
        )
        apply("semantic-bracket-macro-unwrapping", updated)
        updated = re.sub(rf"\|\s*{escaped}\s*\|", parameter, value)
        apply("size-bar-unwrapping", updated)
        updated = re.sub(rf"‖\s*{escaped}\s*‖", parameter, value)
        apply("unicode-norm-bar-unwrapping", updated)
        # TeX's scalable norm bars are the same source notation as `|t|`, not
        # an operator in the closed polynomial grammar. Bounded to one declared
        # parameter, so no norm expression or compound term is interpreted.
        updated = re.sub(
            rf"\\lVert\s*{escaped}\s*\\rVert", parameter, value
        )
        apply("latex-norm-bar-unwrapping", updated)
        # Measured 2026-07-29: plain square brackets around a DECLARED
        # parameter are the same interpretation-value notation as the semantic
        # bracket forms above. This grammar has no indexing or list syntax, and
        # the match is bounded to declared parameters, so it stays unambiguous.
        # Run to fixpoint: the inline TeX semantic bracket `[\![t]\!]` reaches
        # this point as nested `[ [t] ]` once the spacing strip has removed the
        # `\!` tokens (measured 2026-08-02 on a baseline-correct polynomial
        # refused solely for this notation), and one unwrap per pass left the
        # outer pair in place.
        updated = value
        for _ in range(4):
            unwrapped = re.sub(rf"\[\s*{escaped}\s*\]", parameter, updated)
            if unwrapped == updated:
                break
            updated = unwrapped
        apply("square-bracket-unwrapping", updated)
        for wrapper in _INTERPRETATION_WRAPPERS:
            # A preceding DIGIT is implicit multiplication ("2I(n)"), not a
            # longer identifier, so it must not block unwrapping; a preceding
            # letter/underscore still does (it would be a different name).
            updated = re.sub(
                rf"(?<![A-Za-z_])(?<![A-Za-z0-9_]\d){re.escape(wrapper)}"
                rf"\s*\(\s*{escaped}\s*\)",
                parameter,
                value,
            )
            apply(f"interpretation-wrapper[{wrapper}]", updated)

    # Closed, unambiguous implicit multiplication cases only.
    apply("implicit-mul-number-name", re.sub(r"(?<=\d)(?=[A-Za-z_])", "*", value))
    apply("implicit-mul-number-paren", re.sub(r"(?<=\d)(?=\()", "*", value))
    # A coefficient separated from its factor by whitespace only ("2 w(t)",
    # left by a LaTeX spacing command) is still juxtaposition, and a number can
    # never be juxtaposed with a factor for any other reason. Whitespace between
    # two NAMES stays untouched, so it keeps failing the closed grammar rather
    # than inventing a product.
    apply(
        "implicit-mul-number-space-name",
        re.sub(r"(?<=\d)\s+(?=[A-Za-z_])", "*", value),
    )
    apply(
        "implicit-mul-number-space-paren",
        re.sub(r"(?<=\d)\s+(?=\()", "*", value),
    )
    apply("implicit-mul-paren-paren", re.sub(r"(?<=\))(?=\()", "*", value))
    apply("implicit-mul-paren-name", re.sub(r"(?<=\))(?=[A-Za-z_])", "*", value))

    # SA live-round batch 2: variable-variable juxtaposition ("yz") when the
    # declared parameters are all single letters, so the decomposition into
    # declared parameters is UNIQUE. Any other unknown name is left alone and
    # fails the closed grammar downstream (fail-closed).
    single_letter = {p for p in parameters if len(p) == 1}
    if single_letter and all(len(p) == 1 for p in parameters):
        def _split_name(match: re.Match[str]) -> str:
            token = match.group(0)
            if token in parameters:
                return token
            if all(char in single_letter for char in token):
                return "*".join(token)
            return token

        apply(
            "implicit-mul-name-name",
            re.sub(r"[A-Za-z_][A-Za-z0-9_]*", _split_name, value),
        )
    apply("whitespace-normalization", re.sub(r"\s+", "", value))
    # Parse exponents after parameter wrappers, so both x² and ⟦x⟧² retain
    # the same power. The natural-power parser enforces exponent bounds.
    superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
    apply("unicode-natural-exponent", re.sub(
        r"(?<=[A-Za-z0-9_)])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)",
        lambda m: "^(" + m[1].translate(superscripts) + ")", value))
    return value, steps


def canonical_tuple_order(value: Any) -> dict[str, Any]:
    if value is None:
        return {"mode": "unspecified"}
    if not isinstance(value, str):
        return {"mode": "unparseable", "type": type(value).__name__}
    if not value.strip():
        return {"mode": "unparseable"}
    return {"mode": _typed_order_mode(value)}


def _path_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    precedence = payload.get("precedence") or {}
    status = payload.get("status") or {"mode": "unspecified"}
    if precedence.get("status") == "ok":
        typed_precedence: dict[str, Any] = {
            "status": "ok",
            "direct_relations": precedence.get("direct_relations", []),
        }
    else:
        # Raw prose is evidence/provenance, never a mathematical identity. Keep
        # the closed failure class so two genuinely different parser failures
        # do not automatically collapse across a session.
        typed_precedence = {
            "status": "unparseable",
            "reason": precedence.get("reason", "unknown"),
        }
        if precedence.get("unknown_symbols"):
            typed_precedence["unknown_symbols"] = precedence["unknown_symbols"]
    typed_status = {
        key: value
        for key, value in status.items()
        if key in {"mode", "argument_order"}
    }
    return {"precedence": typed_precedence, "status": typed_status}


def project_identity_payload(
    kind_definition: Any,
    canonical_payload: dict[str, Any],
    *,
    receipts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project full canonical transcription to checker-neutral math identity.

    The full payload is always retained. This function only chooses the stable,
    typed portion used to align independent transcriptions. Excluded fields are
    returned as nonidentity payload and remain visible to field/checker-input
    consensus; no information is discarded.
    """
    adapter = kind_definition.identity_adapter
    fields = tuple(kind_definition.identity_fields)
    if adapter == "kind_occurrence_v1":
        identity: dict[str, Any] = {}
    elif adapter == "lex_tuple_shape_v1":
        components = canonical_payload.get("components")
        identity = {
            "component_count": len(components) if isinstance(components, list) else None,
            "order": canonical_tuple_order(canonical_payload.get("order")),
        }
    elif adapter == "call_measure_scope_v1":
        # The aggregate ranges over every recursive-symbol OCCURRENCE, but the
        # argument measured at each occurrence remains mathematical content.
        # Dropping it conflates, for example, an arg-2 aggregate with the
        # canonical arg-3 descent and can change the checker verdict. Optional
        # per-occurrence refinements are likewise identity-bearing.
        identity = {
            field: deepcopy(canonical_payload[field])
            for field in fields
            if field in canonical_payload
        }
    elif adapter in {"selected_fields_v1", "interpretation_core_v1"}:
        identity = {
            field: deepcopy(canonical_payload[field])
            for field in fields
            if field in canonical_payload
        }
    elif adapter == "path_order_v1":
        identity = _path_identity_payload(canonical_payload)
    elif adapter == "full_payload_v1":
        identity = deepcopy(canonical_payload)
    else:
        raise ValueError(
            f"{kind_definition.kind}: unsupported identity adapter {adapter!r}"
        )
    nonidentity = {
        key: deepcopy(value)
        for key, value in canonical_payload.items()
        if key not in identity
    }
    # Adapter-generated identities (tuple shape/path order) do not share source
    # field names with the full payload; in that case preserve the entire source
    # payload as nonidentity provenance.
    if adapter in {"lex_tuple_shape_v1", "path_order_v1"}:
        nonidentity = deepcopy(canonical_payload)
    receipts.append(
        {
            "path": "/transcription",
            "operation": f"mathematical-identity-projection[{adapter}]",
            "status": "ok",
            "input": canonical_payload,
            "output": {
                "identity_payload": identity,
                "nonidentity_payload": nonidentity,
            },
        }
    )
    return identity, nonidentity


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def _canonicalize_value(
    value: Any,
    *,
    path: str,
    receipts: list[dict[str, Any]],
    normalize_strings: bool = True,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_value(
                child,
                path=f"{path}/{key}",
                receipts=receipts,
                normalize_strings=normalize_strings,
            )
            for key, child in sorted(value.items())
        }
    if isinstance(value, list):
        return [
            _canonicalize_value(
                child,
                path=f"{path}/{index}",
                receipts=receipts,
                normalize_strings=normalize_strings,
            )
            for index, child in enumerate(value)
        ]
    normalized = (
        _normalize_scalar(value)
        if normalize_strings
        else value
    )
    receipts.append(
        {
            "path": path,
            "operation": (
                "whitespace-normalization"
                if normalize_strings and normalized != value
                else "exact-source-value"
                if isinstance(value, str) and not normalize_strings
                else "identity"
            ),
            "status": "ok",
            "input": value,
            "output": normalized,
        }
    )
    return normalized


def _dependency_pair_signature(
    transcription: dict[str, Any],
    contract: InstanceContract,
    *,
    receipts: list[dict[str, Any]],
    issues: list[dict[str, str]],
) -> tuple[dict[str, list[str]], list[dict[str, str]], bool]:
    """Type the symbols explicitly present in stated dependency pairs and the
    symbols of the stated usable rules.

    Pair roots keep their written (marked or plain) spelling. Symbols of a
    stated usable rule enter with their contract spelling, because a usable
    rule is weakly oriented under the interpretation of original symbols.
    """

    from .native_math import parse_term, render_term, resolve_usable_rule_items

    pairs = transcription.get("dependency_pairs")
    if not isinstance(pairs, list) or not pairs:
        return {}, [], False
    signature: dict[str, list[str]] = {}
    canonical_pairs: list[dict[str, str]] = []
    supported = True

    def base_symbol(symbol: str) -> str:
        return re.sub(r"(?:\^\{?\\?sharp\}?|[#♯])$", "", symbol)

    def visit(term: Any) -> None:
        nonlocal supported
        head, arguments = term
        if not arguments:
            if head in contract.signature and not contract.signature[head]:
                signature.setdefault(head, [])
            return
        base = base_symbol(head)
        if base not in contract.signature or len(arguments) != len(contract.signature[base]):
            supported = False
            return
        prior = signature.setdefault(head, list(contract.signature[base]))
        if len(prior) != len(arguments):
            supported = False
        for argument in arguments:
            visit(argument)

    for index, pair in enumerate(pairs):
        path = f"/transcription/dependency_pairs/{index}"
        try:
            if not isinstance(pair, dict) or set(pair) != {"lhs", "rhs"}:
                raise ValueError("pair must contain exactly lhs and rhs")
            lhs = parse_term(fold_glyph_tokens(str(pair["lhs"]), contract.glyph_folds))
            rhs = parse_term(fold_glyph_tokens(str(pair["rhs"]), contract.glyph_folds))
            visit(lhs)
            visit(rhs)
            canonical_pair = {"lhs": render_term(lhs), "rhs": render_term(rhs)}
            canonical_pairs.append(canonical_pair)
            status = "ok"
        except (TypeError, ValueError) as error:
            supported = False
            canonical_pair = {"lhs": str(pair), "rhs": ""}
            status = "unparseable"
            issues.append({
                "code": "DEPENDENCY_PAIR_UNPARSEABLE",
                "path": path,
                "message": str(error),
            })
        receipts.append({
            "path": path,
            "operation": "dependency-pair-term-v1",
            "status": status,
            "input": pair,
            "output": canonical_pair,
        })
    usable_supported = True
    usable_items = transcription.get("usable_rules")
    if isinstance(usable_items, list) and usable_items:
        folded_items = [
            fold_glyph_tokens(str(item), contract.glyph_folds) if isinstance(item, str) else item
            for item in usable_items
        ]
        try:
            resolved, unresolved = resolve_usable_rule_items(
                folded_items, contract.rules, contract.signature
            )
        except (KeyError, TypeError, ValueError) as error:
            resolved, unresolved = [], [str(error)]
        rules_by_name = {str(rule.get("name") or ""): rule for rule in contract.rules}
        for name in resolved:
            for side in ("lhs", "rhs"):
                for node in _dependency_pair_nodes(parse_term(str(rules_by_name[name][side]))):
                    head, arguments = node
                    if head in contract.signature and len(arguments) == len(contract.signature[head]):
                        signature.setdefault(head, list(contract.signature[head]))
        receipts.append({
            "path": "/transcription/usable_rules",
            "operation": "usable-rule-resolution-v1",
            "status": "ok" if not unresolved else "unparseable",
            "input": usable_items,
            "output": {"resolved_rule_names": resolved, "unresolved_items": unresolved},
        })
        if unresolved:
            usable_supported = False
            issues.append({
                "code": "USABLE_RULE_UNRESOLVED",
                "path": "/transcription/usable_rules",
                "message": f"usable-rule items outside the contract rules: {unresolved}",
            })
    if not supported:
        issues.append({
            "code": "DEPENDENCY_PAIR_SYMBOL_SET",
            "path": "/transcription/dependency_pairs",
            "message": "dependency-pair symbols or arities are outside the contract signature",
        })
    return signature, canonical_pairs, supported and usable_supported


def _dependency_pair_nodes(term: Any) -> list[Any]:
    nodes = [term]
    for argument in term[1]:
        nodes.extend(_dependency_pair_nodes(argument))
    return nodes


def _canonicalize_definition_blocks(
    transcription: dict[str, Any],
    contract: InstanceContract,
    *,
    receipts: list[dict[str, Any]],
    issues: list[dict[str, str]],
    allow_revisions: bool = False,
    definition_signature: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Canonicalize source-order interpretation definitions.

    Frozen contracts preserve the original exactly-once semantics.  A contract
    whose definition-item schema explicitly declares ``revision`` may encode a
    later source block as ``replacement``.  Only the final effective definition
    enters mathematical/checker identity; the full source-order history remains
    nonidentity provenance.  No replacement marker is inferred.
    """
    definitions = transcription.get("definitions")
    target_signature = definition_signature or contract.signature
    if not isinstance(definitions, list):
        definitions = []

    revision_history: list[dict[str, Any]] = []
    effective_definitions: dict[str, dict[str, Any]] = {}
    effective_checker_map: dict[str, str] = {}
    structural_errors: list[dict[str, str]] = []
    seen_symbols: set[str] = set()

    for index, block in enumerate(definitions):
        path = f"/transcription/definitions/{index}"
        if not isinstance(block, dict):
            history = {
                "source_index": index,
                "revision": "initial",
                "status": "unparseable",
                "raw": block,
                "reason": "definition_block_type",
            }
            revision_history.append(history)
            structural_errors.append(
                {
                    "code": "DEFINITION_BLOCK_TYPE",
                    "path": path,
                    "message": "definition block must be an object",
                }
            )
            receipts.append(
                {
                    "path": path,
                    "operation": "polynomial-definition-alpha-v3",
                    "status": "unparseable",
                    "input": block,
                    "output": {"definition": history},
                }
            )
            continue

        raw_symbol = block.get("symbol")
        symbol = raw_symbol
        if isinstance(symbol, str):
            symbol = fold_symbol_reference(symbol, contract.glyph_folds)
        revision = block.get("revision", "initial")
        parameters = block.get("parameters")
        expression = block.get("expression")
        canonical_parameters = list(target_signature.get(str(symbol), []))
        mapping: dict[str, str] = {}
        parsed_poly: Polynomial | None = None
        parsed_power: dict[str, Any] | None = None
        normalized_expression: str | None = None
        notation_steps: list[dict[str, Any]] = []
        reason: str | None = None

        prior_seen = isinstance(symbol, str) and symbol in seen_symbols
        revision_semantics_ok = True
        if not isinstance(symbol, str) or symbol not in target_signature:
            reason = "unknown_signature_symbol"
            revision_semantics_ok = False
        elif revision not in {"initial", "replacement"}:
            reason = "revision_marker_invalid"
            revision_semantics_ok = False
        elif not allow_revisions and revision != "initial":
            reason = "revision_not_supported_by_contract"
            revision_semantics_ok = False
        elif prior_seen and revision != "replacement":
            reason = "duplicate_signature_symbol"
            revision_semantics_ok = False
        elif not prior_seen and revision == "replacement":
            reason = "replacement_without_prior_definition"
            revision_semantics_ok = False
        elif (
            not isinstance(parameters, list)
            or any(not isinstance(item, str) or not item for item in parameters)
            or len(parameters) != len(canonical_parameters)
            or len(set(parameters)) != len(parameters)
        ):
            reason = "parameter_arity_or_uniqueness"
        elif not isinstance(expression, str):
            reason = "expression_type"
        else:
            # `normalize_interpretation_expression` ASCII-folds Unicode
            # subscript digits in the expression, so the declared parameter
            # names must be folded the same way or the alpha-renaming keys stop
            # matching the parsed variables. Fails closed: if folding would
            # collide two distinct declared parameters ("t1" and "t₁"), the raw
            # names are kept and the expression stays outside the grammar.
            folded_parameters = [fold_subscript_digits(item) for item in parameters]
            if len(set(folded_parameters)) != len(folded_parameters):
                folded_parameters = list(parameters)
            mapping = dict(zip(folded_parameters, canonical_parameters))
            normalized_expression, notation_steps = normalize_interpretation_expression(
                expression, list(folded_parameters)
            )
            raw_poly = parse_polynomial(
                normalized_expression, set(folded_parameters)
            )
            if raw_poly is None:
                raw_power = parse_natural_power(
                    normalized_expression, set(folded_parameters)
                )
                if raw_power is None:
                    reason = "expression_outside_interpretation_grammar"
                else:
                    parsed_power = rename_natural_power(raw_power, mapping)
            else:
                parsed_poly = _rename_polynomial(raw_poly, mapping)

        if isinstance(symbol, str) and symbol in target_signature:
            seen_symbols.add(symbol)

        if parsed_poly is None and parsed_power is None:
            canonical = {
                "status": "unparseable",
                "symbol": symbol,
                "parameters": parameters,
                "expression": expression,
                "reason": reason,
            }
        elif parsed_poly is not None:
            canonical = {
                "status": "ok",
                "symbol": symbol,
                "canonical_parameters": canonical_parameters,
                "polynomial": {"terms": _polynomial_terms(parsed_poly)},
            }
        else:
            canonical = {
                "status": "ok",
                "symbol": symbol,
                "canonical_parameters": canonical_parameters,
                "natural_power": parsed_power,
            }

        history = {
            "source_index": index,
            "revision": revision,
            "raw_symbol": raw_symbol,
            "definition": canonical,
        }
        revision_history.append(history)
        receipts.append(
            {
                "path": path,
                "operation": "polynomial-definition-alpha-v3",
                "status": canonical["status"],
                "input": block,
                "output": {
                    "canonical_parameters": canonical_parameters,
                    "parameter_mapping": mapping,
                    "notation_steps": notation_steps,
                    "normalized_expression": normalized_expression,
                    "revision": revision,
                    "definition": canonical,
                },
            }
        )

        if not revision_semantics_ok:
            structural_errors.append(
                {
                    "code": "DEFINITION_REVISION_INVALID",
                    "path": path,
                    "message": str(reason),
                }
            )
            continue
        if isinstance(symbol, str) and symbol in target_signature:
            effective_definitions[symbol] = canonical
            if parsed_poly is None and parsed_power is None:
                effective_checker_map.pop(symbol, None)
            elif parsed_poly is not None:
                effective_checker_map[symbol] = polynomial_expression(parsed_poly)
            else:
                effective_checker_map[symbol] = natural_power_expression(parsed_power)

    supported = not structural_errors
    issues.extend(structural_errors)
    wanted = set(target_signature)
    observed = set(effective_definitions)
    if observed != wanted:
        supported = False
        issues.append(
            {
                "code": "DEFINITION_SYMBOL_SET",
                "path": "/transcription/definitions",
                "message": (
                    f"effective definitions require exactly {sorted(wanted)}; "
                    f"observed={sorted(observed)}"
                ),
            }
        )
    for symbol, definition in sorted(effective_definitions.items()):
        if definition.get("status") != "ok":
            supported = False
            issues.append(
                {
                    "code": "POLYNOMIAL_DEFINITION_UNSUPPORTED",
                    "path": "/transcription/definitions",
                    "message": f"effective definition {symbol!r}: {definition.get('reason')}",
                }
            )

    canonical_payload: dict[str, Any] = {
        "definitions": sorted(
            effective_definitions.values(),
            key=lambda item: (str(item.get("symbol")), canonical_sha256(item)),
        )
    }
    if allow_revisions:
        canonical_payload["revision_history"] = revision_history
    checker_payload: dict[str, Any] = {"map": effective_checker_map}
    for optional in ("domain", "named", "rule_scope", "comparison",
                     "interpretation_scope", "term_lower_bound",
                     "dependency_pairs", "usable_rules"):
        if optional in transcription:
            canonical_payload[optional] = transcription[optional]
            checker_payload[optional] = transcription[optional]
            receipts.append(
                {
                    "path": f"/transcription/{optional}",
                    "operation": "source-scalar-v3",
                    "status": "ok",
                    "input": transcription[optional],
                    "output": transcription[optional],
                }
            )
    return canonical_payload, checker_payload, supported


_COUNT_MACRO = re.compile(
    r"^\\?#_?\{?(?:\\text\{)?([A-Za-z][A-Za-z0-9]*)\}?\}?\s*\(\s*[A-Za-z]\w*\s*\)$"
)


def _normalize_checker_string(value: str) -> str:
    """Presentation-only normalization of free-text checker-input strings.

    Folds LaTeX math dollars, backticks, whitespace runs, trailing periods,
    a leading article, and the redundant 'strict ' qualifier on order names,
    then maps count macros (#_{eqW}(t), \\#_{\\text{eqW}}(t)) to count(eqW)
    and size bars (|t|) to size. Live three-pass rounds showed blind readers
    of the SAME construction diverging ONLY on these presentation tokens,
    which must never split a checker-input identity."""
    text = fold_presentation(value).strip()
    # Presentation tokens observed in blind-pass splits.  These operations are
    # deliberately narrower than Markdown stripping in general: emphasis
    # delimiters and a leading list ordinal carry no mathematical content, and
    # an indefinite article is removed only when it directly introduces a
    # named order phrase.  In particular, source expressions such as `a + b`
    # are left untouched.
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*(?:\(\d+\)|\d+[.)])\s*", "", text)
    # Measured 2026-07-29 on the 3-pass round: one pass copied a source bullet
    # marker and another did not ("- recDelta above app" vs "recDelta above
    # app"), and one copied the trailing colon that introduced a displayed
    # block. Both are list/layout punctuation with no mathematical content.
    text = re.sub(r"^\s*[-*•–—]\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".:;").strip()
    lowered = text.lower()
    if lowered.startswith("the "):
        text = text[4:]
    text = re.sub(
        r"(?i)^(?:a|an)\s+(?=(?:strict\s+)?(?:lexicographic|multiset|recursive|path)\b)",
        "",
        text,
    )
    text = re.sub(r"(?i)\bstrict\s+lexicographic", "lexicographic", text)
    match = _COUNT_MACRO.match(text)
    if match:
        return f"count({match.group(1)})"
    if re.match(r"^\|\s*[A-Za-z]\w*\s*\|$", text):
        return "size"
    return text


# A leading NAMING LABEL introduces a tuple component; it is not part of the
# measure. "d = total # of delta constructors" and "total # of delta
# constructors" are the same component, and the checker's own component parser
# already drops the label before reading the measure. Measured 2026-07-29: two
# blind readers of one displayed tuple split its whole checker identity on
# nothing but whether they copied the author's labels. Bounded to a short
# identifier with at most one short argument list, and REQUIRED to leave a
# non-empty remainder, so an equation that carries content on the left (a KBO
# weight assignment `w(void) = 1`) is never touched — this runs for `lex_tuple`
# components only.
_COMPONENT_LABEL = re.compile(r"^[A-Za-z][\w']{0,12}(?:\s*\([^()]{0,12}\))?\s*=\s*(?=\S)")


def _normalize_lex_component(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = _COMPONENT_LABEL.sub("", value).strip() or value
    count = re.fullmatch(
        r"(?:total\s+)?(?:number|count|#)\s+(?:of\s+)?([A-Za-z][A-Za-z0-9]*)"
        r"\s+(?:symbols?|constructors?|nodes?|occurrences?)"
        r"(?:\s+in\s+(?:(?:a|the)\s+)?(?:whole\s+|entire\s+)?term)?",
        value, re.IGNORECASE,
    )
    return f"count({count[1]})" if count else value


def _canonical_order_token(value: Any) -> Any:
    """Fold an order NAME to the parsed order it denotes, or leave it alone.

    "lexicographic", "lex order", "ordered lexicographically" and
    "lexicographic order on N x N" are four spellings of one order; the
    mathematical-identity projection already folds them to `{"mode": "lex"}`,
    so the checker channel must not keep splitting on the spelling. Fails
    closed: an order the parser cannot type is returned unchanged, and the
    token keeps the word `multiset` so downstream string guards still fire.
    """

    if not isinstance(value, str) or not value.strip():
        return value
    parsed = canonical_tuple_order(value)
    mode = parsed.get("mode")
    if mode not in {"lex", "multiset"}:
        return value
    argument_order = parsed.get("argument_order")
    if argument_order:
        return f"{mode}[{','.join(str(item) for item in argument_order)}]"
    return str(mode)


def _normalize_checker_payload(
    kind: str, payload: dict[str, Any]
) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_checker_string(value)
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        return value

    normalized = {key: normalize(value) for key, value in payload.items()}
    if kind == "lex_tuple":
        components = normalized.get("components")
        if isinstance(components, list):
            normalized["components"] = [
                _normalize_lex_component(item) for item in components
            ]
        if "order" in normalized:
            normalized["order"] = _canonical_order_token(normalized["order"])
    # Every stated call-measure field remains checker input. In particular, an
    # aggregate's occurrence set does not erase WHICH argument is measured at
    # each occurrence, and affine/leading-chain refinements must never fall
    # through as the older unrefined object.
    return normalized


def canonicalize_claim(claim: dict[str, Any], contract: InstanceContract) -> CanonicalizationResult:
    kind = claim["kind"]
    specificity = claim["specificity"]
    transcription = claim.get("transcription") or {}
    receipts: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    supported = True
    kind_definition = contract.definition(kind)
    adapter = kind_definition.transform_adapter

    if specificity not in {"concrete", "partial"}:
        checker_payload: dict[str, Any] = {}
        canonical_payload: dict[str, Any] = {}
        receipts.append(
            {
                "path": "/specificity",
                "operation": "specificity-route",
                "status": "not-concrete",
                "input": specificity,
                "output": specificity,
            }
        )
    elif adapter == "path_order_v3":
        raw_precedence = transcription.get("precedence")
        if not isinstance(raw_precedence, str) or not raw_precedence.strip():
            parsed_precedence = {"status": "unparseable", "raw": raw_precedence, "reason": "precedence_missing"}
        else:
            parsed_precedence = parse_precedence(
                raw_precedence,
                signature_symbols=contract.signature_symbols,
                glyph_folds=contract.glyph_folds,
            )
        parsed_status = canonical_status(transcription.get("status"))
        raw_quantifier = transcription.get("precedence_quantifier")
        path_properties = kind_definition.transcription_schema.get(
            "properties", {}
        )
        legacy_quantifier = (
            raw_quantifier is None
            and "precedence_quantifier" not in path_properties
        )
        allowed_quantifiers = {
            "exact_partial",
            "exists_total_extension",
            "forall_total_extensions",
            "explicit_total",
            "unclear",
        }
        parsed_quantifier = (
            "exact_partial"
            if legacy_quantifier
            else raw_quantifier
            if isinstance(raw_quantifier, str)
            and raw_quantifier in allowed_quantifiers
            else "unparseable"
        )
        if legacy_quantifier:
            receipts.append(
                {
                    "path": "/transcription/precedence_quantifier",
                    "operation": "legacy-path-order-literal-relation-v1",
                    "status": "applied",
                    "input": None,
                    "output": "exact_partial",
                }
            )
        # `explicit_total` and `exact_partial` name the SAME strict order when
        # the stated relation already orders every declared symbol: both mean
        # "use exactly what was written, complete nothing", and the decision
        # procedure returns the identical rule table and verdict for them
        # (`path_order_decision` only splits on `relation_is_total`, which holds
        # here). Two blind passes reading one displayed total chain split on
        # this label alone on the 3-pass OOS round; the labels are two spellings
        # of one reading, so they must not split a checker-input identity. The
        # fold is refused for a non-total relation, where `explicit_total` is a
        # DIFFERENT and mathematically wrong reading that must keep failing
        # closed as `declared_total_precedence_is_incomplete`.
        if parsed_quantifier == "explicit_total" and precedence_is_total(
            parsed_precedence, contract.signature_symbols
        ):
            receipts.append(
                {
                    "path": "/transcription/precedence_quantifier",
                    "operation": "precedence-quantifier-total-equivalence-v1",
                    "status": "applied",
                    "input": "explicit_total",
                    "output": "exact_partial",
                }
            )
            parsed_quantifier = "exact_partial"
        canonical_payload = {
            "precedence": parsed_precedence,
            "precedence_quantifier": parsed_quantifier,
            "status": parsed_status,
        }
        if parsed_precedence.get("status") == "ok":
            checker_precedence = ", ".join(
                f"{item['higher']} > {item['lower']}"
                for item in parsed_precedence["direct_relations"]
            )
        else:
            checker_precedence = raw_precedence or ""
        checker_payload = {
            "precedence": checker_precedence,
            "precedence_quantifier": parsed_quantifier,
        }
        if parsed_status.get("mode") != "unspecified":
            # Legacy adapters consume a compact status token. The complete
            # typed status remains in canonical_payload and the receipt.
            checker_payload["status"] = str(parsed_status.get("mode"))
            if parsed_status.get("argument_order") is not None:
                checker_payload["argument_order"] = parsed_status[
                    "argument_order"
                ]
        receipts.extend(
            [
                {
                    "path": "/transcription/precedence",
                    "operation": "precedence-graph-v3",
                    "status": parsed_precedence["status"],
                    "input": raw_precedence,
                    "output": parsed_precedence,
                },
                {
                    "path": "/transcription/precedence_quantifier",
                    "operation": "precedence-quantifier-v1",
                    "status": (
                        "ok" if parsed_quantifier != "unparseable" else "unparseable"
                    ),
                    "input": raw_quantifier,
                    "output": parsed_quantifier,
                },
                {
                    "path": "/transcription/status",
                    "operation": "path-status-v3",
                    "status": "ok" if parsed_status["mode"] != "unparseable" else "unparseable",
                    "input": transcription.get("status"),
                    "output": parsed_status,
                },
            ]
        )
        if (
            parsed_precedence["status"] != "ok"
            or parsed_status["mode"] == "unparseable"
            or parsed_quantifier == "unparseable"
        ):
            supported = False
            issues.append(
                {
                    "code": "CANONICALIZATION_UNSUPPORTED",
                    "path": "/transcription",
                    "message": "path-order transcription is outside the closed parser",
                }
            )
    elif (
        adapter == "polynomial_definitions_v3"
        and isinstance(transcription.get("definitions"), list)
    ):
        definition_item_properties = (
            kind_definition.transcription_schema.get("properties", {})
            .get("definitions", {})
            .get("items", {})
            .get("properties", {})
        )
        definition_signature = None
        canonical_pairs: list[dict[str, str]] | None = None
        pair_supported = True
        if transcription.get("interpretation_scope") == "dependency_pair":
            definition_signature, canonical_pairs, pair_supported = _dependency_pair_signature(
                transcription, contract, receipts=receipts, issues=issues
            )
        canonical_payload, checker_payload, adapter_supported = _canonicalize_definition_blocks(
            transcription,
            contract,
            receipts=receipts,
            issues=issues,
            allow_revisions="revision" in definition_item_properties,
            definition_signature=definition_signature,
        )
        if canonical_pairs is not None:
            canonical_payload["dependency_pairs"] = canonical_pairs
            checker_payload["dependency_pairs"] = canonical_pairs
        supported = supported and adapter_supported and pair_supported
    elif kind in {"poly_interpretation", "additive_measure"} and isinstance(transcription.get("map"), dict):
        canonical_map: dict[str, Any] = {}
        checker_map: dict[str, str] = {}
        for symbol, definition in sorted(transcription["map"].items()):
            canonical_parameters = list(contract.signature.get(symbol, []))
            if isinstance(definition, dict):
                raw_parameters = definition.get("parameters")
                expression = definition.get("expression")
                if (
                    not isinstance(raw_parameters, list)
                    or any(not isinstance(item, str) or not item for item in raw_parameters)
                    or len(raw_parameters) != len(canonical_parameters)
                    or len(set(raw_parameters)) != len(raw_parameters)
                    or not isinstance(expression, str)
                ):
                    parsed_poly = None
                    mapping: dict[str, str] = {}
                else:
                    mapping = dict(zip(raw_parameters, canonical_parameters))
                    raw_poly = parse_polynomial(expression, set(raw_parameters))
                    parsed_poly = _rename_polynomial(raw_poly, mapping) if raw_poly is not None else None
                input_value: Any = definition
            else:
                expression = str(definition)
                mapping = {name: name for name in canonical_parameters}
                parsed_poly = parse_polynomial(expression, set(canonical_parameters))
                input_value = definition
            if parsed_poly is None:
                parsed = {"status": "unparseable", "raw": input_value}
            else:
                parsed = {"status": "ok", "terms": _polynomial_terms(parsed_poly)}
                checker_map[symbol] = polynomial_expression(parsed_poly)
            canonical_map[symbol] = parsed
            receipts.append(
                {
                    "path": f"/transcription/map/{symbol}",
                    "operation": "polynomial-ast-alpha-v2",
                    "status": parsed["status"],
                    "input": input_value,
                    "output": {
                        "canonical_parameters": canonical_parameters,
                        "parameter_mapping": mapping,
                        "polynomial": parsed,
                    },
                }
            )
            if parsed["status"] != "ok":
                supported = False
                issues.append(
                    {
                        "code": "POLYNOMIAL_UNPARSEABLE",
                        "path": f"/transcription/map/{symbol}",
                        "message": "definition arity/parameters are invalid or the expression is outside the nonnegative +/* polynomial grammar",
                    }
                )
        canonical_payload = {"map": canonical_map}
        checker_payload = {"map": checker_map}
        for optional in ("domain", "named"):
            if optional in transcription:
                canonical_payload[optional] = transcription[optional]
                checker_payload[optional] = transcription[optional]
                receipts.append(
                    {
                        "path": f"/transcription/{optional}",
                        "operation": "enum-identity",
                        "status": "ok",
                        "input": transcription[optional],
                        "output": transcription[optional],
                    }
                )
    else:
        canonical_payload = _canonicalize_value(
            transcription,
            path="/transcription",
            receipts=receipts,
            normalize_strings=not contract.is_v3,
        )
        checker_payload = json.loads(json.dumps(transcription))

    completeness_issues = kind_definition.completeness_issues(
        transcription,
        contract.signature,
        specificity=specificity,
        glyph_folds=contract.glyph_folds,
    )
    if completeness_issues:
        supported = False
        issues.extend(completeness_issues)

    if specificity == "partial":
        supported = False
        issues.append(
            {
                "code": "PARTIAL_CONSTRUCTION",
                "path": "/specificity",
                "message": "partial constructions are faithfully canonicalized but remain checker-unsupported until completed by the source itself",
            }
        )

    # Preserve the complete canonical transcription separately from the stable
    # mathematical identity projection.  This is the central v3.1 repair: prose
    # and optional checker parameters remain auditable but do not manufacture
    # distinct mathematical objects across honest extractors.
    transcription_core = {
        "kind": kind,
        "payload": deepcopy(canonical_payload),
    }
    if contract.is_v3:
        identity_payload, annotation_payload = project_identity_payload(
            kind_definition,
            canonical_payload,
            receipts=receipts,
        )
    else:
        identity_payload = deepcopy(canonical_payload)
        annotation_payload = {}
    mathematical_core = {
        "kind": kind,
        "payload": identity_payload,
    }
    assertion_core = {
        **mathematical_core,
        "specificity": specificity,
        "claimed_target": claim["claimed_target"],
    }

    if contract.is_v3:
        normalized_checker_payload = _normalize_checker_payload(
            kind, checker_payload
        )
        if normalized_checker_payload != checker_payload:
            receipts.append(
                {
                    "path": "/checker_payload",
                    "operation": "checker-input-normalization-v1",
                    "status": "applied",
                    "input": deepcopy(checker_payload),
                    "output": deepcopy(normalized_checker_payload),
                }
            )
            checker_payload = normalized_checker_payload
        checker_core = {
            "kind": kind,
            "payload": deepcopy(checker_payload),
        }
    else:
        checker_core = deepcopy(assertion_core)
        stripping = contract.semantic_identity_stripping.get(kind, ())
        if stripping and isinstance(checker_core["payload"], dict):
            for field in stripping:
                if field in checker_core["payload"]:
                    removed = checker_core["payload"].pop(field)
                    receipts.append(
                        {
                            "path": f"/transcription/{field}",
                            "operation": "checker-equivalence-strip",
                            "status": "telemetry-only",
                            "input": removed,
                            "output": None,
                        }
                    )

    mathematical_identity = canonical_sha256(mathematical_core)
    assertion_identity = canonical_sha256(assertion_core)
    transcription_identity = canonical_sha256(transcription_core)
    return CanonicalizationResult(
        core=assertion_core,
        identity=assertion_identity,
        mathematical_core=mathematical_core,
        mathematical_identity=mathematical_identity,
        assertion_core=assertion_core,
        assertion_identity=assertion_identity,
        transcription_core=transcription_core,
        transcription_identity=transcription_identity,
        annotation_payload=annotation_payload,
        checker_core=checker_core,
        checker_identity=canonical_sha256(checker_core),
        checker_payload=checker_payload,
        receipts=receipts,
        supported=supported,
        issues=issues,
    )
