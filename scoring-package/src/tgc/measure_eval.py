"""Ground-step counterexample search for stated termination measures.

REFUTED-only route. A lex-tuple measure claim asserts that EVERY step of the
claimed rewrite relation strictly decreases the stated tuple. Refuting that
claim needs exactly one concrete step on which the tuple fails to decrease;
certifying it would need the monotone-algebra premise over all steps, which
this module never attempts. The emitted certificate is a single rewrite step
(rule, substitution, context, both ground terms) together with either the
evaluated component values or, for an argument-only function, the selected
argument's syntactic identity on both sides, so any auditor can recompute it
by hand.

Soundness boundaries, in order:

1. Components are parsed into a closed evaluatable grammar. Anything that does
   not parse ends the parsed PREFIX; nothing is guessed. With a full parse a
   step refutes when the tuple does not strictly decrease. With a partial
   prefix a step refutes ONLY when the parsed prefix strictly INCREASES
   lexicographically: whatever the unparsed tail means, a lex comparison that
   finds a strict increase before the tail never consults it.
2. The claimed target gates the step universe. Root steps belong to every
   target in the rewrite family, so a root counterexample refutes all of them;
   steps under a context are used only when every substantive target vote
   names a contextual relation. A vote outside the rewrite family (for
   example `dependency_pair_termination`, whose steps are chain steps, not
   rewrite steps) disables the route entirely.
3. Rules whose left-hand side carries two or more DISTINCT variables are
   instantiated with pairwise distinct ground terms. Distinctness can only
   avoid an implicit disequality guard (`eq_diff` fires beside `eq_refl`), so
   it never fabricates a step the live relation lacks; repeated variables in a
   nonlinear pattern still share one binding, as unification demands.
4. The comparison is lexicographic. The registry's `lex_tuple` cue pins the
   kind to "compared lexicographically", so a missing `order` field is
   kind-implied; a stated order that does not fold to "lex" disables the
   route rather than reinterpreting the claim.
"""

from __future__ import annotations

import itertools
import re
from typing import Any

from .canonical import canonical_tuple_order, fold_glyph_tokens, fold_presentation
from .common import canonical_sha256

# Ground terms are immutable tuples: (symbol, (child, child, ...)).
Term = tuple[str, tuple]

# Targets whose step universe is ordinary rewriting. Root steps are steps of
# every member; context steps only of the contextual members.
CONTEXTUAL_TARGETS = frozenset({"full_contextual_sn"})
ROOT_TARGETS = frozenset({"root_only_termination"})
REWRITE_FAMILY_TARGETS = CONTEXTUAL_TARGETS | ROOT_TARGETS

# Deterministic search caps. The search space is enumerated in a fixed order,
# so the caps change how far the search LOOKS, never what a found certificate
# means; a capped miss leaves the claim UNKNOWN exactly as an unparsed one does.
_MAX_GENERATOR_TERMS = 320
_MAX_GENERATOR_SIZE = 5
_MAX_SUBSTITUTIONS_PER_RULE = 4096
_MAX_STEPS_EVALUATED = 120000

_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
}


def _effective_claimed_targets(consensus_claim: dict[str, Any]) -> list[str]:
    """Return the gate-decided target when available, otherwise open votes.

    A threshold-agreed value is the row's typed target.  Retaining an outvoted
    minority reading here would let one weaker extraction disable a certificate
    for the agreed object.  Unresolved/malformed target fields stay fail-closed
    by exposing every substantive vote to the caller.
    """

    target = (consensus_claim.get("field_consensus") or {}).get(
        "claimed_target", {}
    )
    if not isinstance(target, dict):
        return []
    value = target.get("value")
    if (
        target.get("status") == "agreed"
        and isinstance(value, str)
        and value not in {"", "unclear", "none"}
    ):
        return [value]
    votes = target.get("votes") or {}
    if not isinstance(votes, dict):
        return []
    return [
        vote
        for vote in votes.values()
        if isinstance(vote, str) and vote not in {"", "unclear", "none"}
    ]


def parse_term(text: str) -> Term:
    """Parse `f(a,g(b))` notation into an immutable term tuple."""

    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[(),]", text)
    position = 0

    def parse() -> Term:
        nonlocal position
        if position >= len(tokens):
            raise ValueError(f"unexpected end of term in {text!r}")
        head = tokens[position]
        if not re.match(r"[A-Za-z_]", head):
            raise ValueError(f"expected symbol at {position} in {text!r}")
        position += 1
        children: list[Term] = []
        if position < len(tokens) and tokens[position] == "(":
            position += 1
            while True:
                children.append(parse())
                if position < len(tokens) and tokens[position] == ",":
                    position += 1
                    continue
                break
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError(f"unbalanced parentheses in {text!r}")
            position += 1
        return (head, tuple(children))

    term = parse()
    if position != len(tokens):
        raise ValueError(f"trailing tokens in {text!r}")
    return term


def render_term(term: Term) -> str:
    symbol, children = term
    if not children:
        return symbol
    return f"{symbol}({','.join(render_term(child) for child in children)})"


def _substitute(term: Term, bindings: dict[str, Term], signature: set[str]) -> Term:
    symbol, children = term
    if symbol not in signature and not children:
        if symbol not in bindings:
            raise ValueError(f"unbound variable {symbol}")
        return bindings[symbol]
    return (symbol, tuple(_substitute(child, bindings, signature) for child in children))


def _term_size(term: Term) -> int:
    return 1 + sum(_term_size(child) for child in term[1])


def _term_depth(term: Term) -> int:
    return 1 + max((_term_depth(child) for child in term[1]), default=0)


def _term_variables(term: Term, signature: set[str]) -> list[str]:
    symbol, children = term
    found: list[str] = []
    if symbol not in signature and not children:
        found.append(symbol)
    for child in children:
        for name in _term_variables(child, signature):
            if name not in found:
                found.append(name)
    return found


# --- component grammar -------------------------------------------------------
#
# AST forms (all evaluate to a natural number on a ground term):
#   ("size",)                       total node count
#   ("count", s)                    occurrences of symbol s anywhere in the term
#   ("sym_depth", s)                max s-nesting along any root-to-leaf path
#   ("max_arg_sym_depth", f, k, s)  max over f-subterms of sym_depth(s) of arg k
#   ("sum_arg_chain", f, k, s)      sum over f-subterms of the leading s-chain
#                                   length of their k-th argument
#   ("root_arg_chain", f, k, s)     leading s-chain of the root's k-th argument
#                                   if the root is f, else 0
#   ("root_arg_metric", f, k, m, s) measure m of the root f-term's k-th
#                                   argument, else 0; m is size, depth, or
#                                   symbol_count (whose symbol is s)
#   ("sum_arg_leading_affine", f, k, s, c)
#                                   sum, over every f-subterm, of c plus the
#                                   leading s-chain length of argument k
#   ("count_arg_root", f, k, g)    number of f-subterms whose k-th argument
#                                   has root g
#   ("root_match", f, g_or_None)    1 if root is f (and arg 1's root is g), else 0
#   ("root_in", frozenset)          1 if the root symbol is in the set, else 0
#   ("multiset_arg_sym_depth", f, k, s)
#                                   the MULTISET (descending tuple) of
#                                   sym_depth(s) of arg k over every f-subterm;
#                                   compared by the Dershowitz-Manna order

_WHOLE_TERM_SUFFIX = r"(?:\s+in\s+(?:the\s+)?(?:whole\s+|entire\s+)?(?:term|t))?"
_SIZE_TEXT = re.compile(
    r"^(?:ordinary\s+)?(?:total\s+|structural\s+)?(?:term[\s_-]?)?size(?:\s*\(t\))?"
    + _WHOLE_TERM_SUFFIX
    + r"$"
    r"|^(?:total\s+)?(?:number|count)\s+of\s+(?:all\s+)?"
    r"constructors?(?:\s+applications?)?" + _WHOLE_TERM_SUFFIX + r"$"
    r"|^(?:total\s+)?(?:number|count)\s+of\s+constructor\s+applications?"
    + _WHOLE_TERM_SUFFIX
    + r"$"
    r"|^constructor[\s_-]?count$",
    re.IGNORECASE,
)


def _strip_gloss(text: str) -> str:
    """Drop a trailing parenthetical gloss and collapse whitespace."""

    value = re.sub(r"\s*\([^()]*\)\s*$", "", text.strip())
    return re.sub(r"\s+", " ", value).strip().rstrip(".").strip()


def parse_component(component: Any, signature: dict[str, list[str]],
                    glyph_folds: tuple[tuple[str, str], ...]) -> tuple | None:
    """Map one stated component to an evaluatable AST, or None.

    Deterministic and fail-closed: the patterns below are the spellings
    measured on live rounds, folded through the contract's presentation and
    glyph folds first so a fruit-obfuscated transcript parses identically to
    its KO7 twin.
    """

    if not isinstance(component, str) or not component.strip():
        return None
    symbols = set(signature)
    text = fold_presentation(component, markdown_emphasis=True)
    text = fold_glyph_tokens(text, glyph_folds)
    # LaTeX escapes its hash; the escaped and bare spellings are one glyph.
    text = text.replace("\\#", "#")
    # Greek deltas that survived the contract folds (the folds catch composed
    # names like recΔ) are the bare symbol; Σ is summation prose.
    text = text.replace("Σ", "sum").replace("Δ", "delta").replace("δ", "delta")
    text = fold_glyph_tokens(text, glyph_folds)
    text = re.sub(r"\s+", " ", text).strip()
    stripped = _strip_gloss(text)

    candidates = [stripped, text]
    # A leading naming label ("Grape depth: Maximum nesting depth of ...") is
    # presentation. Tried LAST, so a grammar form that itself contains a colon
    # (the Σ-over-subterms shape) is never truncated by the label strip.
    for base in (stripped, text):
        delabeled = re.sub(r"^[A-Za-z][\w\s\"'-]{0,40}:\s*", "", base).strip()
        if delabeled and delabeled not in candidates:
            candidates.append(delabeled)
    # A multiset-labeled per-subterm family keeps its aggregation semantics
    # even after the label strip; the flag travels with the parse below.
    text_is_multiset = "multiset" in text.lower()
    # Shorthand identifiers fuse a display symbol to a suffix with an
    # underscore ("grape_depth"), where the word-boundary glyph fold cannot
    # see the symbol. The spaced variant is the same spelling with the fusion
    # undone, folded again.
    for base in list(candidates):
        if "_" in base:
            spaced = fold_glyph_tokens(base.replace("_", " "), glyph_folds)
            spaced = re.sub(r"\s+", " ", spaced).strip()
            if spaced and spaced not in candidates:
                candidates.append(spaced)

    for candidate in candidates:
        if not candidate:
            continue
        if _SIZE_TEXT.fullmatch(candidate):
            return ("size",)
        # count(sym) / #sym(t) / #sym / number of sym nodes|constructors|occurrences
        match = re.fullmatch(r"count\((\w+)\)(?:\s*\(t\))?", candidate)
        if match and match.group(1) in symbols:
            return ("count", match.group(1))
        match = re.fullmatch(r"#\s*(\w+)(?:\s*\(t\))?", candidate)
        if match and match.group(1) in symbols:
            return ("count", match.group(1))
        match = re.fullmatch(
            r"(?:total\s+)?(?:number|count|#)\s*(?:of\s+)?(\w+)"
            r"(?:[\s-]+(?:constructor|symbol|node|occurrence)s?)?"
            r"(?:\s+in\s+(?:(?:a|the)\s+)?(?:whole\s+|entire\s+)?(?:term|t))?",
            candidate,
            re.IGNORECASE,
        )
        if match and match.group(1) in symbols:
            return ("count", match.group(1))
        match = re.fullmatch(
            r"sum of (depths|sizes) of (\w+) arguments of all (\w+)(?:['’]s|s)?",
            candidate, re.IGNORECASE,
        )
        if match:
            metric, ordinal, outer = match.groups()
            index = _ORDINALS.get(ordinal.lower())
            if outer in symbols and index is not None and index <= len(signature[outer]):
                return ("sum_arg_metric", outer, index,
                        "depth" if metric.lower() == "depths" else "size", None)
        # sym-depth / sym depth / sym_depth / nesting depth of sym
        match = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9]*)[\s_-]?depth(?:\s*\(t\))?(?:\s+of\s+t)?",
            candidate,
            re.IGNORECASE,
        )
        if match and match.group(1) in symbols:
            return ("sym_depth", match.group(1))
        match = re.fullmatch(
            r"(?:maximum\s+|max\s+)?nesting\s+depth\s+of\s+(\w+)"
            r"(?:\s+constructors?)?" + _WHOLE_TERM_SUFFIX,
            candidate,
            re.IGNORECASE,
        )
        if match and match.group(1) in symbols:
            return ("sym_depth", match.group(1))
        # maximum nesting depth of S constructors appearing as the Nth
        # argument of any F subterm -> max over F-subterms of arg-N S-depth
        match = re.fullmatch(
            r"(?:maximum\s+|max\s+)?nesting\s+depth\s+of\s+(\w+)\s+"
            r"constructors?\s+appearing\s+as\s+the\s+(\w+)\s+argument\s+of\s+"
            r"any\s+(\w+)\s+subterms?",
            candidate,
            re.IGNORECASE,
        )
        if match:
            inner, ordinal, outer = match.group(1), match.group(2), match.group(3)
            index = _ORDINALS.get(ordinal.lower())
            if inner in symbols and outer in symbols and index is not None:
                if index <= len(signature[outer]):
                    return ("max_arg_sym_depth", outer, index, inner)
        # sym-depth in f <ordinal> argument(s): max over f-subterms of arg k
        match = re.fullmatch(
            r"(\w+)[\s-]?depth\s+(?:in|of)\s+(\w+)\s+(\w+)\s+arguments?",
            candidate,
            re.IGNORECASE,
        )
        if match:
            inner, outer, ordinal = match.group(1), match.group(2), match.group(3)
            index = _ORDINALS.get(ordinal.lower())
            if inner in symbols and outer in symbols and index is not None:
                if index <= len(signature[outer]):
                    return ("max_arg_sym_depth", outer, index, inner)
        # for each f <vars>, count the (maximum) s-depth of <var> — a
        # per-subterm family; MULTISET semantics only when the original text
        # says so, fail-closed (measured 2026-08-07: "Multiset of recΔ
        # recursion heights: For each recΔ b s n, count the maximum
        # delta-depth of n").
        match = re.fullmatch(
            r"for each (\w+)((?:\s+\w+)+),\s*count the "
            r"(?:maximum\s+|max\s+)?(\w+)[\s_-]?depth of (\w+)",
            candidate,
            re.IGNORECASE,
        )
        if match and text_is_multiset:
            outer, variables, inner, target = (
                match.group(1),
                match.group(2).split(),
                match.group(3),
                match.group(4),
            )
            if outer in symbols and inner in symbols and target in variables:
                index = variables.index(target) + 1
                if index <= len(signature[outer]):
                    return ("multiset_arg_sym_depth", outer, index, inner)
        # number of outermost s wrappers in the Nth argument of every f —
        # the same per-f-subterm SUM the Σ-form states (measured 2026-08-07,
        # o3: "number of outermost delta wrappers occurring in the third
        # argument of every recΔ").
        match = re.fullmatch(
            r"(?:number|count) of outermost (\w+) (?:wrappers?|constructors?)"
            r"\s+(?:occurring\s+)?in the (\w+) argument of "
            r"(?:every|each|all) (\w+)(?:\s+subterms?)?",
            candidate,
            re.IGNORECASE,
        )
        if match:
            inner, ordinal, outer = match.group(1), match.group(2), match.group(3)
            index = _ORDINALS.get(ordinal.lower())
            if inner in symbols and outer in symbols and index is not None:
                if index <= len(signature[outer]):
                    return ("sum_arg_chain", outer, index, inner)
        # sum over all f <vars> subterms: leading s-chain of the named argument
        match = re.fullmatch(
            r"sum over all (\w+)((?:\s+\w+)+) subterms:?\s*"
            r"(?:number|count) of consecutive leading (\w+) constructors? in (\w+)",
            candidate,
            re.IGNORECASE,
        )
        if match:
            outer, variables, inner, target = (
                match.group(1),
                match.group(2).split(),
                match.group(3),
                match.group(4),
            )
            if outer in symbols and inner in symbols and target in variables:
                index = variables.index(target) + 1
                if index <= len(signature[outer]):
                    return ("sum_arg_chain", outer, index, inner)
        # number of top-level f (g _) redices — the exact root-pattern
        # indicator only; a trailing qualifier ("... that match one of the
        # three merge rules") changes the semantics and fails the parse,
        # ending the prefix, fail-closed.
        match = re.fullmatch(
            r"(?:number|count) of top[\s-]?level (\w+)"
            r"(?:\s*\(\s*(\w+)\s+_\s*\))?\s+red(?:ex(?:es)?|ices)"
            r"(?:\s+in\s+t)?",
            candidate,
            re.IGNORECASE,
        )
        if match:
            outer, inner = match.group(1), match.group(2)
            if outer in symbols and (inner is None or inner in symbols):
                return ("root_match", outer, inner)
        # An explicitly inlined subterm-pattern count. The optional left side
        # is only a label; the right side must state the full ternary shape,
        # so a shorthand name alone never activates this grammar.
        match = re.fullmatch(
            r"(?:[A-Za-z][A-Za-z0-9_]*\s*\(t\)\s*=\s*)?"
            r"(?:number|count) of subterms of form "
            r"(\w+)\(\s*_\s*,\s*_\s*,\s*(\w+)\(\s*_\s*\)\s*\)",
            candidate,
            re.IGNORECASE,
        )
        if match:
            outer, inner = match.group(1), match.group(2)
            if (
                outer in symbols
                and inner in symbols
                and len(signature[outer]) == 3
                and len(signature[inner]) == 1
            ):
                return ("count_arg_root", outer, 3, inner)
        # length of the outermost s-chain in the <ordinal> argument of a
        # top-level f redex (0 if the root is not f)
        match = re.fullmatch(
            r"length of the outermost (\w+)[\s-]?chain in the (\w+) argument of "
            r"a top[\s-]?level (\w+) redex",
            candidate,
            re.IGNORECASE,
        )
        if match:
            inner, ordinal, outer = match.group(1), match.group(2), match.group(3)
            index = _ORDINALS.get(ordinal.lower())
            if inner in symbols and outer in symbols and index is not None:
                if index <= len(signature[outer]):
                    return ("root_arg_chain", outer, index, inner)
        # 1 if the root of t is in {a, b, c}, 0 otherwise
        match = re.fullmatch(
            r"1 if the root(?:\s+of\s+t)?\s+is\s+in\s*\{?([\w,\s]+)\}?"
            r"(?:,?\s*(?:and\s+)?0 otherwise)?",
            candidate,
            re.IGNORECASE,
        )
        if match:
            members = frozenset(
                token for token in re.split(r"[,\s]+", match.group(1)) if token
            )
            if members and members <= symbols:
                return ("root_in", members)
    return None


def _leading_chain(term: Term, symbol: str) -> int:
    length = 0
    node = term
    while node[0] == symbol and len(node[1]) >= 1:
        length += 1
        node = node[1][0]
    return length


def _subterms(term: Term):
    yield term
    for child in term[1]:
        yield from _subterms(child)


def evaluate_component(ast: tuple, term: Term) -> int:
    """Evaluate one component AST on a ground term. Total by construction."""

    head = ast[0]
    if head == "size":
        return _term_size(term)
    if head == "count":
        return sum(1 for node in _subterms(term) if node[0] == ast[1])
    if head == "sym_depth":
        symbol = ast[1]

        def depth(node: Term) -> int:
            own = 1 if node[0] == symbol else 0
            return own + max((depth(child) for child in node[1]), default=0)

        return depth(term)
    if head == "max_arg_sym_depth":
        outer, index, inner = ast[1], ast[2], ast[3]
        best = 0
        for node in _subterms(term):
            if node[0] == outer and len(node[1]) >= index:
                best = max(
                    best, evaluate_component(("sym_depth", inner), node[1][index - 1])
                )
        return best
    if head == "sum_arg_chain":
        outer, index, inner = ast[1], ast[2], ast[3]
        return sum(
            _leading_chain(node[1][index - 1], inner)
            for node in _subterms(term)
            if node[0] == outer and len(node[1]) >= index
        )
    if head == "root_arg_chain":
        outer, index, inner = ast[1], ast[2], ast[3]
        if term[0] == outer and len(term[1]) >= index:
            return _leading_chain(term[1][index - 1], inner)
        return 0
    if head == "root_arg_metric":
        outer, index, measure, inner = ast[1], ast[2], ast[3], ast[4]
        if term[0] != outer or len(term[1]) < index:
            return 0
        argument = term[1][index - 1]
        if measure == "size":
            return _term_size(argument)
        if measure == "depth":
            return _term_depth(argument)
        if measure == "symbol_count" and isinstance(inner, str):
            return evaluate_component(("count", inner), argument)
        raise ValueError(f"unknown root argument metric {ast!r}")
    if head == "sum_arg_metric":
        outer, index, measure, inner = ast[1], ast[2], ast[3], ast[4]
        total = 0
        for node in _subterms(term):
            if node[0] != outer or len(node[1]) < index:
                continue
            argument = node[1][index - 1]
            if measure == "size":
                total += _term_size(argument)
            elif measure == "depth":
                total += _term_depth(argument)
            elif measure == "symbol_count" and isinstance(inner, str):
                total += evaluate_component(("count", inner), argument)
            else:
                raise ValueError(f"unknown summed argument metric {ast!r}")
        return total
    if head == "sum_arg_leading_affine":
        outer, index, inner, offset = ast[1], ast[2], ast[3], ast[4]
        return sum(
            offset + _leading_chain(node[1][index - 1], inner)
            for node in _subterms(term)
            if node[0] == outer and len(node[1]) >= index
        )
    if head == "count_arg_root":
        outer, index, inner = ast[1], ast[2], ast[3]
        return sum(
            1
            for node in _subterms(term)
            if node[0] == outer
            and len(node[1]) >= index
            and node[1][index - 1][0] == inner
        )
    if head == "root_match":
        outer, inner = ast[1], ast[2]
        if term[0] != outer:
            return 0
        if inner is None:
            return 1
        return 1 if term[1] and term[1][0][0] == inner else 0
    if head == "root_in":
        return 1 if term[0] in ast[1] else 0
    if head == "multiset_arg_sym_depth":
        outer, index, inner = ast[1], ast[2], ast[3]
        values = sorted(
            (
                evaluate_component(("sym_depth", inner), node[1][index - 1])
                for node in _subterms(term)
                if node[0] == outer and len(node[1]) >= index
            ),
            reverse=True,
        )
        return tuple(values)
    raise ValueError(f"unknown component AST {ast!r}")


def _multiset_gt(left: tuple, right: tuple) -> bool:
    """Dershowitz-Manna order on finite N-multisets (descending tuples)."""

    if tuple(left) == tuple(right):
        return False
    left_bag = list(left)
    right_bag = list(right)
    for value in list(left_bag):
        if value in right_bag:
            left_bag.remove(value)
            right_bag.remove(value)
    # left > right iff every element right gained is dominated by some
    # element right lost.
    return all(any(x > y for x in left_bag) for y in right_bag)


def _component_eq(before, after) -> bool:
    return before == after


def _component_gt(before, after) -> bool:
    if isinstance(before, tuple) or isinstance(after, tuple):
        return _multiset_gt(tuple(before), tuple(after))
    return before > after


def _serialize_ast(ast: tuple) -> Any:
    return [sorted(item) if isinstance(item, frozenset) else item for item in ast]


def generator_terms(signature: dict[str, list[str]]) -> list[Term]:
    """Ground terms up to a fixed size, smallest first, deterministic order."""

    constants = sorted(symbol for symbol, args in signature.items() if not args)
    if not constants:
        return []
    by_size: dict[int, list[Term]] = {1: [(symbol, ()) for symbol in constants]}
    for size in range(2, _MAX_GENERATOR_SIZE + 1):
        layer: list[Term] = []
        for symbol in sorted(signature):
            arity = len(signature[symbol])
            if arity == 0:
                continue
            budget = size - 1
            if budget < arity:
                continue
            for split in _compositions(budget, arity):
                pools = [by_size.get(part, []) for part in split]
                if any(not pool for pool in pools):
                    continue
                for children in itertools.product(*pools):
                    layer.append((symbol, tuple(children)))
        by_size[size] = layer
    ordered: list[Term] = []
    for size in range(1, _MAX_GENERATOR_SIZE + 1):
        ordered.extend(by_size.get(size, []))
        if len(ordered) >= _MAX_GENERATOR_TERMS:
            break
    return ordered[:_MAX_GENERATOR_TERMS]


def _compositions(total: int, parts: int):
    if parts == 1:
        yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest


def _contexts(signature: dict[str, list[str]]) -> list[tuple[str, int] | None]:
    """None is the empty context; (f, i) wraps the redex at argument i of f
    with minimal-constant siblings."""

    wrappers: list[tuple[str, int] | None] = [None]
    for symbol in sorted(signature):
        for position in range(1, len(signature[symbol]) + 1):
            wrappers.append((symbol, position))
    return wrappers


def _apply_context(
    context: tuple[str, int] | None,
    redex: Term,
    signature: dict[str, list[str]],
    filler: Term,
) -> Term:
    if context is None:
        return redex
    symbol, position = context
    children = tuple(
        redex if index == position else filler
        for index in range(1, len(signature[symbol]) + 1)
    )
    return (symbol, children)


def _render_context(context: tuple[str, int] | None, signature: dict[str, list[str]],
                    filler: Term) -> str:
    if context is None:
        return "□"
    symbol, position = context
    slots = [
        "□" if index == position else render_term(filler)
        for index in range(1, len(signature[symbol]) + 1)
    ]
    return f"{symbol}({','.join(slots)})"


def _candidate_substitutions(variables: list[str], pool: list[Term]):
    """Deterministic substitution order: targeted sweeps, then the product.

    Phase 1 sweeps ONE variable through the whole pool while the others take
    the smallest pairwise-distinct fillers — the "one deep value, rest small"
    shape every duplication/monotonicity counterexample needs, reachable even
    when the full product would blow the cap (measured 2026-08-07: a
    multiset-height refutation needs a size-5 filler the product order could
    not reach). Phase 2 is the bounded pairwise-distinct product, deduplicated
    against phase 1. Pairwise distinctness throughout: never step onto a
    diagonal a sibling rule may guard (`eq_refl` beside `eq_diff`).
    """

    if not variables:
        yield ()
        return
    seen: set[tuple] = set()
    arity = len(variables)
    for position in range(arity):
        for candidate in pool:
            smallest = [term for term in pool if term != candidate][: arity - 1]
            if len(smallest) < arity - 1:
                continue
            # Every arrangement of the smallest fillers around the swept
            # value: which slot gets the minimal term matters (a duplication
            # counterexample may need the RECURSION argument minimal while
            # the duplicated one is deep). Bounded by (arity-1)! and arity
            # is tiny for first-order rules.
            for arrangement in itertools.permutations(smallest):
                fillers = iter(arrangement)
                values: list[Term] = []
                for index in range(arity):
                    if index == position:
                        values.append(candidate)
                    else:
                        values.append(next(fillers))
                key = tuple(values)
                if key not in seen:
                    seen.add(key)
                    yield key
    for values in itertools.product(pool, repeat=arity):
        if arity >= 2 and len(set(values)) != len(values):
            continue
        if values in seen:
            continue
        seen.add(values)
        yield values


def _lex_strictly_decreases(before: list, after: list) -> bool:
    """Lexicographic strict decrease with per-position semantics: ints by <,
    multiset positions by the Dershowitz-Manna order."""

    for left, right in zip(before, after):
        if _component_eq(left, right):
            continue
        return _component_gt(left, right)
    return False


def _prefix_strictly_increases(before: list, after: list) -> bool:
    for left, right in zip(before, after):
        if _component_eq(left, right):
            continue
        return _component_gt(right, left)
    return False


def _search_component_asts(
    parsed: list[tuple],
    *,
    component_count: int,
    full_parse: bool,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
    allow_context_steps: bool,
    contexts_override: list[tuple[str, int] | None] | None = None,
) -> dict[str, Any] | None:
    """Search the bounded ground-step universe for already-typed components."""

    generators = generator_terms(signature)
    if not generators:
        return None
    filler = generators[0]
    signature_set = set(signature)
    contexts = (
        contexts_override
        if contexts_override is not None
        else _contexts(signature)
        if allow_context_steps
        else [None]
    )

    evaluated = 0
    for rule in rules:
        try:
            lhs = parse_term(str(rule["lhs"]))
            rhs = parse_term(str(rule["rhs"]))
        except ValueError:
            continue
        variables = _term_variables(lhs, signature_set)
        if set(_term_variables(rhs, signature_set)) - set(variables):
            # A right-hand variable the left does not bind is not a rewrite
            # rule this search can instantiate; skip it, fail-closed.
            continue
        pool = generators
        combos = 0
        for values in _candidate_substitutions(variables, pool):
            combos += 1
            if combos > _MAX_SUBSTITUTIONS_PER_RULE:
                break
            bindings = dict(zip(variables, values))
            redex_before = _substitute(lhs, bindings, signature_set)
            redex_after = _substitute(rhs, bindings, signature_set)
            for context in contexts:
                before = _apply_context(context, redex_before, signature, filler)
                after = _apply_context(context, redex_after, signature, filler)
                evaluated += 1
                if evaluated > _MAX_STEPS_EVALUATED:
                    return None
                values_before = [evaluate_component(ast, before) for ast in parsed]
                values_after = [evaluate_component(ast, after) for ast in parsed]
                if full_parse:
                    refutes = not _lex_strictly_decreases(values_before, values_after)
                    basis = "tuple_not_strictly_decreasing"
                else:
                    refutes = _prefix_strictly_increases(values_before, values_after)
                    basis = "parsed_prefix_strictly_increases"
                if refutes:
                    return {
                        "rule": str(rule.get("name") or ""),
                        "substitution": {
                            name: render_term(term)
                            for name, term in sorted(bindings.items())
                        },
                        "context": _render_context(context, signature, filler),
                        "step_kind": "root" if context is None else "contextual",
                        "term_before": render_term(before),
                        "term_after": render_term(after),
                        "component_asts": [_serialize_ast(ast) for ast in parsed],
                        "parsed_prefix_length": len(parsed),
                        "component_count": component_count,
                        "values_before": values_before,
                        "values_after": values_after,
                        "comparison_basis": basis,
                    }
    return None


def find_step_counterexample(
    components: list[Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
    glyph_folds: tuple[tuple[str, str], ...],
    allow_context_steps: bool,
) -> dict[str, Any] | None:
    """Search for one rewrite step on which the stated tuple fails to decrease.

    Returns a fully recomputable certificate payload, or None (no finding
    within the deterministic search bounds — which is NOT a validation).
    """

    parsed: list[tuple] = []
    for component in components:
        ast = parse_component(component, signature, glyph_folds)
        if ast is None:
            break
        parsed.append(ast)
    if not parsed:
        return None
    full_parse = len(parsed) == len(components)
    return _search_component_asts(
        parsed,
        component_count=len(components),
        full_parse=full_parse,
        signature=signature,
        rules=rules,
        allow_context_steps=allow_context_steps,
    )


def _contains_symbol(term: Term, symbol: str) -> bool:
    return term[0] == symbol or any(
        _contains_symbol(child, symbol) for child in term[1]
    )


def _recursive_symbol(
    signature: dict[str, list[str]], rules: tuple[dict[str, Any], ...]
) -> str | None:
    """Unique rule root that occurs recursively in one of its right sides."""

    candidates: set[str] = set()
    for rule in rules:
        try:
            lhs = parse_term(str(rule["lhs"]))
            rhs = parse_term(str(rule["rhs"]))
        except ValueError:
            continue
        if lhs[0] in signature and _contains_symbol(rhs, lhs[0]):
            candidates.add(lhs[0])
    return next(iter(candidates)) if len(candidates) == 1 else None


def _whole_term_call_measure_ast(
    payload: dict[str, Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
) -> tuple | None:
    if payload.get("scope") != "whole_term":
        return None
    argument = payload.get("argument")
    if not isinstance(argument, int):
        return None
    outer = _recursive_symbol(signature, rules)
    if outer is None or argument < 1 or argument > len(signature.get(outer, [])):
        return None
    measure = payload.get("measure")
    if measure in {"size", "term_size"}:
        return ("root_arg_metric", outer, argument, "size", None)
    if measure in {"depth", "constructor_depth"}:
        return ("root_arg_metric", outer, argument, "depth", None)
    symbol_by_measure = {
        "S_count": "S",
        "symbol_count_S": "S",
        "delta_count": "delta",
        "symbol_count_delta": "delta",
    }
    counted = symbol_by_measure.get(measure)
    if counted in signature:
        return ("root_arg_metric", outer, argument, "symbol_count", counted)
    return None


def _whole_term_argument_only(
    payload: dict[str, Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
) -> tuple[str, int] | None:
    """Recognize the narrow argument-only whole-term call-measure family.

    A payload in this family states one deterministic function of one selected
    argument of the unique recursive symbol.  The optional ``measure`` field
    refines *which* such function was named, but is irrelevant to the sibling
    context counterexample below: contracting a redex in another argument
    leaves the selected argument syntactically identical.

    The exact-key guard is deliberate.  It prevents the independence proof
    from being reused for richer call-measure semantics whose extra fields may
    make the value depend on more than the selected argument.
    """

    if set(payload) - {"scope", "argument", "measure"}:
        return None
    if payload.get("scope") != "whole_term":
        return None
    argument = payload.get("argument")
    if not isinstance(argument, int) or isinstance(argument, bool):
        return None
    outer = _recursive_symbol(signature, rules)
    if outer is None or argument < 1 or argument > len(signature.get(outer, [])):
        return None
    if "measure" in payload and _whole_term_call_measure_ast(
        payload,
        signature=signature,
        rules=rules,
    ) is None:
        # A stated but unregistered measure is not silently reinterpreted as
        # an arbitrary function of the argument.  The contract schema normally
        # rejects this first; the checker retains the same fail-closed boundary
        # when called directly.
        return None
    return outer, argument


def _sibling_context_invariance_witness(
    outer: str,
    argument: int,
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    """Construct one real contextual step preserving ``outer`` argument k.

    This is not a bounded semantic search for a particular measure.  It only
    instantiates a contract rule and places that redex in a sibling argument
    of an outer recursive-symbol occurrence.  Equality of the selected
    argument before and after is then checked syntactically and recorded.
    """

    sibling_positions = [
        position
        for position in range(1, len(signature.get(outer, [])) + 1)
        if position != argument
    ]
    generators = generator_terms(signature)
    if not sibling_positions or not generators:
        return None
    filler = generators[0]
    signature_set = set(signature)
    context = (outer, sibling_positions[0])
    for rule in rules:
        try:
            lhs = parse_term(str(rule["lhs"]))
            rhs = parse_term(str(rule["rhs"]))
        except (KeyError, ValueError):
            continue
        variables = _term_variables(lhs, signature_set)
        if set(_term_variables(rhs, signature_set)) - set(variables):
            continue
        # No semantic search is needed: every contract rule is an unconditional
        # first-order rewrite rule, so one ground filler for every variable is a
        # valid instance.  This keeps the invariance certificate linear in rule
        # arity instead of entering the general bounded counterexample search.
        bindings = {name: filler for name in variables}
        redex_before = _substitute(lhs, bindings, signature_set)
        redex_after = _substitute(rhs, bindings, signature_set)
        before = _apply_context(context, redex_before, signature, filler)
        after = _apply_context(context, redex_after, signature, filler)
        selected_before = before[1][argument - 1]
        selected_after = after[1][argument - 1]
        if selected_before != selected_after:
            continue
        return {
            "rule": str(rule.get("name") or ""),
            "substitution": {
                name: render_term(term) for name, term in sorted(bindings.items())
            },
            "context": _render_context(context, signature, filler),
            "context_symbol": outer,
            "context_argument": context[1],
            "step_kind": "contextual",
            "term_before": render_term(before),
            "term_after": render_term(after),
            "selected_argument": argument,
            "selected_argument_before": render_term(selected_before),
            "selected_argument_after": render_term(selected_after),
            "selected_argument_syntactically_identical": True,
        }
    return None


def _aggregate_call_measure_ast(
    payload: dict[str, Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
) -> tuple | None:
    """Closed semantics for exact summed and affine argument aggregates.

    The scope spelling names ``F`` rather than an arbitrary recursive symbol,
    so this evaluator deliberately applies only when ``F`` is the unique
    recursive rule root. Other aggregate spellings remain UNKNOWN.
    """

    scope = payload.get("scope")
    if scope not in {"all_F_subterms_sum", "all_recursive_subterms_sum"}:
        return None
    outer = _recursive_symbol(signature, rules)
    if outer is None or (scope == "all_F_subterms_sum" and outer != "F"):
        return None
    argument = payload.get("argument")
    if (
        not isinstance(argument, int)
        or isinstance(argument, bool)
        or argument < 1
        or argument > len(signature.get(outer, []))
    ):
        return None

    if set(payload) == {"scope", "argument", "measure"}:
        measure = payload.get("measure")
        if measure in {"size", "term_size", "third_argument_size"}:
            return ("sum_arg_metric", outer, argument, "size", None)
        if measure in {"depth", "constructor_depth", "third_argument_depth"}:
            return ("sum_arg_metric", outer, argument, "depth", None)
        symbol_by_measure = {
            "S_count": "S",
            "symbol_count_S": "S",
            "delta_count": "delta",
            "symbol_count_delta": "delta",
        }
        counted = symbol_by_measure.get(measure)
        if counted in signature:
            return ("sum_arg_metric", outer, argument, "symbol_count", counted)
        return None

    # The refined affine syntax is currently instance-specific to F/S.
    if scope != "all_F_subterms_sum":
        return None
    if payload.get("measure") != "S_count":
        return None
    if payload.get("measure_mode") != "leading_chain":
        return None
    # A stated sum of leading-chain counts has the ordinary zero offset.  The
    # optional occurrence_offset field represents the distinct affine measure
    # sum(offset + chain), and silence must not be rewritten as a missing
    # source definition.  Both objects use the same exact evaluator.
    offset = payload.get("occurrence_offset", 0)
    if (
        not isinstance(argument, int)
        or isinstance(argument, bool)
        or not isinstance(offset, int)
        or isinstance(offset, bool)
        or offset < 0
    ):
        return None
    if outer != "F" or argument < 1 or argument > len(signature.get("F", [])):
        return None
    if len(signature.get("S", [])) != 1:
        return None
    return ("sum_arg_leading_affine", "F", argument, "S", offset)


def call_measure_step_counterexample(
    consensus_claim: dict[str, Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    """REFUTED-only decision for closed typed recursive-argument measures."""

    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "call_measure":
        return None
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return None
    payload = checker_object.get("payload") or {}

    substantive = _effective_claimed_targets(consensus_claim)
    if any(vote not in REWRITE_FAMILY_TARGETS for vote in substantive):
        return None
    allow_context = bool(substantive) and all(
        vote in CONTEXTUAL_TARGETS for vote in substantive
    )

    argument_only = _whole_term_argument_only(
        payload,
        signature=signature,
        rules=rules,
    )
    if argument_only is not None:
        if not allow_context:
            return None
        outer, argument = argument_only
        witness = _sibling_context_invariance_witness(
            outer,
            argument,
            signature=signature,
            rules=rules,
        )
        if witness is None:
            return None
        stated_ast = _whole_term_call_measure_ast(
            payload,
            signature=signature,
            rules=rules,
        )
        if stated_ast is not None:
            before = parse_term(witness["term_before"])
            after = parse_term(witness["term_after"])
            witness = {
                **witness,
                "component_asts": [_serialize_ast(stated_ast)],
                "parsed_prefix_length": 1,
                "component_count": 1,
                "values_before": [evaluate_component(stated_ast, before)],
                "values_after": [evaluate_component(stated_ast, after)],
                "comparison_basis": "selected_argument_syntactic_identity",
            }
        input_sha256 = canonical_sha256(checker_object)
        dependency_receipt = {
            "receipt_type": "whole-term-call-measure-sibling-invariance/v1",
            "depends_on": [
                "/kind",
                "/payload/scope",
                "/payload/argument",
            ],
            "independent_of": ["/payload/measure"],
            "basis": "selected_argument_syntactically_identical",
        }
        return {
            "verdict": "REFUTED",
            "detail": (
                "call_measure_argument_invariance_counterexample"
                f"[{witness['rule']}|contextual]"
            ),
            "certificate": {
                "certificate_type": (
                    "call-measure-argument-invariance-counterexample/v1"
                ),
                "checker_object_sha256": input_sha256,
                "input_sha256": input_sha256,
                "verdict": "REFUTED",
                "kind": "call_measure",
                "typed_payload": dict(payload),
                "field_dependency_receipt": dependency_receipt,
                "witness": witness,
                "argument": (
                    "the redex is contracted in a sibling argument of an "
                    "outer recursive-symbol occurrence, so the selected "
                    "argument is syntactically identical before and after; "
                    "every deterministic function solely of that argument "
                    "therefore ties on this contextual rewrite step"
                ),
                "supported_targets": [],
            },
        }

    # Every registered plain whole-term argument object was handled above.
    # Do not let the legacy metric AST silently drop an extra refinement or
    # reinterpret an unregistered measure spelling.
    if payload.get("scope") == "whole_term":
        return None

    ast = _whole_term_call_measure_ast(payload, signature=signature, rules=rules)
    if ast is None:
        ast = _aggregate_call_measure_ast(
            payload,
            signature=signature,
            rules=rules,
        )
    if ast is None:
        return None
    outer, argument = ast[1], ast[2]
    contexts: list[tuple[str, int] | None] | None
    if ast[0] == "root_arg_metric":
        if not allow_context:
            return None
        contexts = [
            (outer, position)
            for position in range(1, len(signature[outer]) + 1)
            if position != argument
        ]
        if not contexts:
            return None
    elif ast[0] == "sum_arg_leading_affine":
        # Contract the base redex inside the very argument whose leading
        # chain the outer occurrence observes. For the calibrated payload
        # this deterministically reaches
        # F(Z,Z,F(S(Z),Z,Z)) -> F(Z,Z,S(Z)), a 2 -> 2 tie.
        contexts = [(outer, argument)]
    else:
        # Exact whole-term sums can be checked at the root under every rewrite
        # target and under contexts only for the full contextual target.
        contexts = None
    witness = _search_component_asts(
        [ast],
        component_count=1,
        full_parse=True,
        signature=signature,
        rules=rules,
        allow_context_steps=allow_context,
        contexts_override=contexts,
    )
    if witness is None:
        return None
    if ast[0] in {"root_arg_metric", "sum_arg_leading_affine"}:
        before_term = parse_term(witness["term_before"])
        after_term = parse_term(witness["term_after"])
        if (
            before_term[0] == outer
            and after_term[0] == outer
            and len(before_term[1]) >= argument
            and len(after_term[1]) >= argument
        ):
            witness = {
                **witness,
                "selected_argument": argument,
                "selected_argument_before": render_term(
                    before_term[1][argument - 1]
                ),
                "selected_argument_after": render_term(
                    after_term[1][argument - 1]
                ),
            }
    if ast[0] == "root_arg_metric":
        argument_text = (
            "the redex is contracted in a sibling argument of an outer "
            "recursive-symbol occurrence, so the selected argument is "
            "identical before and after; the typed whole-term function of "
            "that argument therefore ties on a contextual rewrite step"
        )
    elif ast[0] == "sum_arg_leading_affine":
        argument_text = (
            "the certified redex is contracted in the selected argument of "
            "an outer F occurrence; the certificate recomputes the stated "
            "per-occurrence offset plus leading-S-chain sum before and after, "
            "where it fails to decrease strictly"
        )
    else:
        argument_text = (
            "the certificate evaluates the exact sum of the stated metric over "
            "the selected argument of every recursive-symbol subterm before "
            "and after one concrete rewrite step"
        )
    input_sha256 = canonical_sha256(checker_object)
    return {
        "verdict": "REFUTED",
        "detail": (
            "call_measure_step_counterexample"
            f"[{witness['rule']}|{witness['step_kind']}]"
        ),
        "certificate": {
            "certificate_type": "call-measure-step-counterexample/v1",
            "checker_object_sha256": input_sha256,
            "input_sha256": input_sha256,
            "verdict": "REFUTED",
            "typed_payload": dict(payload),
            "witness": witness,
            "argument": argument_text,
            "supported_targets": [],
        },
    }


def measure_step_counterexample(
    consensus_claim: dict[str, Any],
    *,
    signature: dict[str, list[str]],
    rules: tuple[dict[str, Any], ...],
    glyph_folds: tuple[tuple[str, str], ...],
) -> dict[str, Any] | None:
    """REFUTED-only decision for a lex_tuple claim; None when it does not apply.

    Target gating: root steps refute every rewrite-family target, so they are
    always admissible; context steps are admissible only when every
    substantive target vote is contextual. Any vote outside the rewrite
    family disables the route.
    """

    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "lex_tuple":
        return None
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return None
    payload = checker_object.get("payload") or {}
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        return None
    order = payload.get("order")
    order_basis = "kind_implied_lexicographic"
    if "order" in payload:
        if canonical_tuple_order(order).get("mode") != "lex":
            return None
        order_basis = "stated"

    substantive = _effective_claimed_targets(consensus_claim)
    if any(vote not in REWRITE_FAMILY_TARGETS for vote in substantive):
        return None
    allow_context = bool(substantive) and all(
        vote in CONTEXTUAL_TARGETS for vote in substantive
    )

    witness = find_step_counterexample(
        components,
        signature=signature,
        rules=rules,
        glyph_folds=glyph_folds,
        allow_context_steps=allow_context,
    )
    if witness is None:
        return None
    input_sha256 = canonical_sha256(checker_object)
    return {
        "verdict": "REFUTED",
        "detail": (
            "measure_step_counterexample"
            f"[{witness['rule']}|{witness['step_kind']}]"
        ),
        "certificate": {
            "certificate_type": "measure-step-counterexample/v1",
            "checker_object_sha256": input_sha256,
            "input_sha256": input_sha256,
            "verdict": "REFUTED",
            "order_basis": order_basis,
            "witness": witness,
            "argument": (
                "the stated components evaluate on both sides of one concrete "
                "rewrite step admitted by the claimed target; the values shown "
                "fail the strict lexicographic decrease the claim asserts, and "
                "when only a prefix of the components parsed, that prefix "
                "strictly increases, which no reading of the remaining "
                "components can undo"
            ),
            "supported_targets": [],
        },
    }
