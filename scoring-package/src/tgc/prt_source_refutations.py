"""Refute closed, independently quoted assertions without filling missing fields."""

from __future__ import annotations

import re
from itertools import islice, product
from typing import Any

from .canonical import fold_glyph_tokens, fold_presentation
from .common import canonical_sha256
from .config import InstanceContract
from .native_math import call_measure_dependency_pair_decision, parse_term, render_term
from .occurrence_obligations import argument_count_refutation
from .proof_obligations import _parsed_rules, _substitute, _variables
from .prt_policy import OFFER_ROLES
from .structural_premises import _replay_step, _step, structural_refutation

_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
_ARGUMENT_ASSERTION = re.compile(
    r"(?:the )?(first|second|third|fourth|fifth) argument of ([A-Za-z][A-Za-z0-9]*) "
    r"strictly decreases(?: under the [A-Za-z][A-Za-z0-9]* constructor: "
    r"[A-Za-z][A-Za-z0-9]*\([A-Za-z][A-Za-z0-9]*\) becomes [A-Za-z][A-Za-z0-9]*)?\.?",
    re.IGNORECASE,
)
_CHAIN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:\s*>\s*[A-Za-z][A-Za-z0-9]*)+")
_DISOWNED = re.compile(r"\b(?:if|suppose|assuming|incorrect|wrong|instead|replace|reject|hypothetical)\b", re.I)
_SYMBOL = r"[A-Za-z][A-Za-z0-9_]*"
_NORMAL_FORM = re.compile(
    rf"The term (?P<w>{_SYMBOL})\((?P<v>{_SYMBOL})\) for any (?P=v) is a normal form "
    rf"with respect to this system[—–-]it cannot be reduced further because "
    rf"there(?:'s| is) no rule for (?P=w)\.?"
)
_WRAPPER_FORMS = [
    re.compile(rf"There are no rules for (?P<w>{_SYMBOL}), so (?P=w)\(\.\.\.\) is a normal form\.?"),
    re.compile(rf"(?P<w>{_SYMBOL}) never appears on the left-hand side of any rule, "
               rf"so no rule can ever be applied to a term of the form (?P=w)\(\.\.\.\)\."
               rf"(?: The symbol (?P=w) behaves as a free constructor with respect to rewriting\.)?"),
]


def _wrapper_fact(text):
    for pattern in [_NORMAL_FORM, *_WRAPPER_FORMS]:
        match = pattern.fullmatch(text.removeprefix("- "))
        if match:
            return "universal_wrapper_normality", match["w"]
    return None
# Only explicit whole-term wording is a refutable claim; the bare "rewriting
# stops" has a true call-local reading (closure audit A03), on every route.
_BASE_STOPS = re.compile(
    rf"There are no rules for (?P<constructors>{_SYMBOL}(?:, {_SYMBOL})*(?:,? or {_SYMBOL})?), "
    rf"so once (?P<recursive>{_SYMBOL}) reaches (?P<base>{_SYMBOL}), "
    r"(?:all rewriting stops|no (?:further )?rewriting (?:is possible |can occur |occurs )?anywhere)\.?"
)
_OUTERMOST = re.compile(
    rf"The only redexes are outermost (?P<recursive>{_SYMBOL})-applications"
    r"(?:, which match purely syntactically on the (?:first|second|third|fourth|fifth) argument:)?\.?"
)


def _text(text: str, contract: InstanceContract) -> str:
    return re.sub(r"\s+", " ", fold_glyph_tokens(
        fold_presentation(text, markdown_emphasis=True), contract.glyph_folds
    )).strip()


def _duplicated_redex_witness(contract: InstanceContract) -> dict[str, Any] | None:
    """Return a ground step that duplicates a reducible substituted term."""

    if contract.target_policy.get("relation_semantics") != "standard_contextual_closure":
        return None
    try:
        parsed = _parsed_rules(contract.rules, contract.signature)
    except (KeyError, TypeError, ValueError):
        return None
    unconditional = [item for item in parsed if set(item[0]) <= {"name", "lhs", "rhs"}]
    constants = sorted(
        symbol for symbol, parameters in contract.signature.items() if not parameters
    )
    if not constants or not unconditional:
        return None
    seed = (constants[0], ())

    def count_variable(term, variable: str) -> int:
        if term == (variable, ()):
            return 1
        return sum(count_variable(child, variable) for child in term[1])

    for outer_rule, outer_lhs, outer_rhs in unconditional:
        variables = sorted(_variables(outer_lhs, contract.signature))
        duplicated = next(
            (
                variable
                for variable in variables
                if count_variable(outer_rhs, variable)
                > count_variable(outer_lhs, variable)
            ),
            None,
        )
        if duplicated is None:
            continue
        for inner_rule, inner_lhs, inner_rhs in unconditional:
            inner_substitution = dict.fromkeys(
                _variables(inner_lhs, contract.signature), seed
            )
            redex = _substitute(inner_lhs, inner_substitution)
            substitution = dict.fromkeys(variables, seed)
            substitution[duplicated] = redex
            source = _substitute(outer_lhs, substitution)
            target = _substitute(outer_rhs, substitution)

            def occurrences(term) -> int:
                return int(term == redex) + sum(occurrences(child) for child in term[1])

            source_count = occurrences(source)
            target_count = occurrences(target)
            if target_count <= source_count:
                continue
            return {
                "type": "duplicated_reducible_substitution",
                "outer_rule": outer_rule["name"],
                "inner_rule": inner_rule["name"],
                "duplicated_variable": duplicated,
                "source": render_term(source),
                "target": render_term(target),
                "redex": render_term(redex),
                "source_redex_occurrences": source_count,
                "target_redex_occurrences": target_count,
                "replay_basis": "parsed contract rules and a ground substitution",
            }
    return None


_QUOTE_DISOWNED = re.compile(
    r"\b(?:suppose|supposing|assuming|hypothetical|incorrect|wrong|reject(?:ed|s)?|would not|would fail)\b",
    re.I,
)
_ORDINAL_ARGUMENT = r"(?P<ordinal>first|second|third|fourth|fifth)"


def _match(pattern, term, signature, substitution):
    head, arguments = pattern
    if head not in signature and not arguments:
        bound = substitution.get(head)
        if bound is None:
            substitution[head] = term
            return True
        return bound == term
    if term[0] != head or len(term[1]) != len(arguments):
        return False
    return all(_match(p, t, signature, substitution) for p, t in zip(arguments, term[1]))


def _is_redex(term, parsed, signature, symbol=None):
    if symbol is not None and term[0] != symbol:
        return False
    for rule, lhs, _rhs in parsed:
        if set(rule) - {"name", "lhs", "rhs"}:
            continue
        if _match(lhs, term, signature, {}):
            return True
    return False


def _positions(term, path=()):
    yield list(path), term
    for index, child in enumerate(term[1], 1):
        yield from _positions(child, (*path, index))


def _subterm(term, position):
    for index in position:
        if not 1 <= index <= len(term[1]):
            return None
        term = term[1][index - 1]
    return term


def _ground_pool(signature, depth=1, cap=60):
    constants = sorted((s, ()) for s, p in signature.items() if not p)
    pool = list(constants)
    frontier = list(constants)
    for _ in range(depth):
        new = []
        for symbol, parameters in sorted(signature.items()):
            if not parameters:
                continue
            for arguments in product(pool, repeat=len(parameters)):
                term = (symbol, tuple(arguments))
                if term not in pool and term not in new:
                    new.append(term)
                if len(pool) + len(new) >= cap:
                    break
        pool.extend(new)
        frontier = new
        if len(pool) >= cap:
            break
    del frontier
    return pool[:cap]


def _redex_creation_witness(rule_entry, symbol, parsed, signature):
    """A replayed step by this rule after which a new symbol-headed redex exists."""

    rule, lhs, rhs = rule_entry
    variables = sorted(_variables(lhs, signature))
    pool = _ground_pool(signature)
    constants = sorted((s, ()) for s, p in signature.items() if not p)
    for values in islice(product(pool, repeat=len(variables)), 2000):
        substitution = dict(zip(variables, values))
        redex = _substitute(lhs, substitution)
        # Creation inside the contractum.
        step = _step(rule, lhs, rhs, substitution, redex, [])
        source, target = _replay_step(step, parsed, signature)
        for position, subterm in _positions(target):
            if not _is_redex(subterm, parsed, signature, symbol):
                continue
            before = _subterm(source, position)
            if position and (before is None or not _is_redex(before, parsed, signature, symbol)):
                return {**step, "created_redex_position": position, "created_redex": render_term(subterm)}
        # Creation above the contracted position.
        for parent, parameters in sorted(signature.items()):
            if parent != symbol or not parameters:
                continue
            for index in range(1, len(parameters) + 1):
                for fillers in product(constants, repeat=len(parameters) - 1):
                    arguments = list(fillers)
                    arguments.insert(index - 1, redex)
                    context = (parent, tuple(arguments))
                    if _is_redex(context, parsed, signature, symbol):
                        continue
                    step = _step(rule, lhs, rhs, substitution, context, [index])
                    source, target = _replay_step(step, parsed, signature)
                    if _is_redex(target, parsed, signature, symbol):
                        return {**step, "created_redex_position": [], "created_redex": render_term(target)}
    return None


def _measure_values(texts):
    """Parse a stated counter valuation: value of the base constant and successor step."""

    base = successor = None
    for text in texts:
        found = re.search(rf"\|\s*(?P<base>{_SYMBOL})\s*\|\s*=\s*0\b", text) or re.search(
            rf"\b(?P<fn>{_SYMBOL})\(\s*(?P<base>{_SYMBOL})\s*\)\s*=\s*0\b", text)
        if found and base is None:
            base = found["base"]
        step = re.search(
            rf"\|\s*(?P<succ>{_SYMBOL})\(\s*(?P<v>{_SYMBOL})\s*\)\s*\|\s*=\s*\|\s*(?P=v)\s*\|\s*\+\s*1\b", text
        ) or re.search(
            rf"\b(?P<fn>{_SYMBOL})\(\s*(?P<succ>{_SYMBOL})\(\s*(?P<v>{_SYMBOL})\s*\)\s*\)\s*=\s*1\s*\+\s*(?P=fn)\(\s*(?P=v)\s*\)",
            text,
        )
        if step and successor is None:
            successor = step["succ"]
    return base, successor


def _redex_measure_argument(texts, contract):
    """Return (recursive symbol, argument index) for 'F(x,y,n) measured by n'."""

    for text in texts:
        found = re.search(
            rf"redex `?(?P<rec>{_SYMBOL})\((?P<args>[^()]*)\)`?\s*,?\s*take measure `?\|\s*(?P<var>{_SYMBOL})\s*\|`?",
            text,
        ) or re.search(
            rf"\b(?:μ|mu)\(\s*(?P<rec>{_SYMBOL})\((?P<args>[^()]*)\)\s*\)\s*=\s*{_SYMBOL}\(\s*(?P<var>{_SYMBOL})\s*\)",
            text,
        )
        if not found:
            continue
        parameters = [item.strip() for item in found["args"].split(",")]
        rec = found["rec"]
        if rec in contract.signature and len(parameters) == len(contract.signature[rec]) and found["var"] in parameters:
            return rec, parameters.index(found["var"]) + 1
    return None


def _rule_display_before(source_text, quote, contract):
    """The contract rule displayed immediately before the quote in the source."""

    if not source_text or quote not in source_text:
        return None
    prefix = source_text[: source_text.index(quote)][-240:]
    displays = re.findall(r"`([^`]*(?:->|→)[^`]*)`", prefix)
    if not displays:
        return None
    sides = re.split(r"\s*(?:->|→)\s*", _text(displays[-1], contract))
    if len(sides) != 2:
        return None
    try:
        lhs, rhs = parse_term(sides[0].replace(" ", "")), parse_term(sides[1].replace(" ", ""))
        parsed = _parsed_rules(contract.rules, contract.signature)
    except (KeyError, TypeError, ValueError):
        return None
    for rule, rule_lhs, rule_rhs in parsed:
        substitution: dict = {}
        if _match(rule_lhs, lhs, {**contract.signature, **{}}, substitution) and _substitute(rule_rhs, substitution) == rhs:
            return rule, rule_lhs, rule_rhs
    return None


def _zero_base_strict_decrease(raw, text, all_texts, source_text, contract):
    if not re.search(r"\(strict decrease\)", text, re.I):
        return None
    if not re.search(r"\b(?:removes|eliminates|disappears|drops to 0)\b", text, re.I):
        return None
    base_rule = _rule_display_before(source_text, raw, contract)
    measure = _redex_measure_argument(all_texts, contract)
    base, successor = _measure_values(all_texts)
    if not base_rule or not measure or base not in contract.signature:
        return None
    rule, lhs, rhs = base_rule
    recursive, argument = measure
    if lhs[0] != recursive or lhs[1][argument - 1] != (base, ()) or rhs[1] or rhs[0] in contract.signature:
        return None
    parsed = _parsed_rules(contract.rules, contract.signature)
    constants = sorted(s for s, p in contract.signature.items() if not p)
    seed = (constants[0], ())
    if successor in contract.signature and len(contract.signature[successor]) == 1:
        # The rule returns a variable; bind it to a recursive-headed term whose
        # measured argument is successor(base). Value 0 becomes value 1.
        inner_arguments = [seed] * len(contract.signature[recursive])
        inner_arguments[argument - 1] = (successor, ((base, ()),))
        substitution = dict.fromkeys(_variables(lhs, contract.signature), seed)
        substitution[rhs[0]] = (recursive, tuple(inner_arguments))
        source_term = _substitute(lhs, substitution)
        step = _step(rule, lhs, rhs, substitution, source_term, [])
        source, target = _replay_step(step, parsed, contract.signature)
        if target[0] == recursive and target[1][argument - 1] == (successor, ((base, ()),)):
            return {
                "holds": False,
                "reason": "stated_redex_measure_increases_at_claimed_strict_base_step",
                "measure": {"recursive_symbol": recursive, "argument": argument,
                            "base_value": {base: 0}, "successor_increment": {successor: 1}},
                "witness": {**step, "source_value": 0, "target_value": 1},
                "replay_verified": True,
            }
    if re.search(r"\bdrops to 0\b", text, re.I):
        return {
            "holds": False,
            "reason": "strict_decrease_claimed_from_zero_to_zero",
            "measure": {"recursive_symbol": recursive, "argument": argument, "base_value": {base: 0}},
            "witness": {"rule": rule["name"], "redex": render_term(lhs), "stated_value_before": 0,
                        "stated_value_after": 0},
            "replay_verified": True,
        }
    return None


def _headed_argument_normal_form(text, contract):
    match = re.search(
        rf"\bif the {_ORDINAL_ARGUMENT} argument is [^.]*?`?(?P<wrapper>{_SYMBOL})`?-term[^.]*?"
        rf"\bthe `?(?P<rec>{_SYMBOL})`? is (?:already )?(?:a |in )?normal form\b",
        text,
        re.I,
    )
    if not match:
        return None
    recursive, wrapper = match["rec"], match["wrapper"]
    argument = _ORDINALS[match["ordinal"].lower()]
    signature = contract.signature
    if recursive not in signature or wrapper not in signature or not 1 <= argument <= len(signature[recursive]):
        return None
    if len(signature[recursive]) < 2:
        return None
    parsed = _parsed_rules(contract.rules, signature)
    constants = sorted(s for s, p in signature.items() if not p)
    seed = (constants[0], ())
    for rule, lhs, rhs in parsed:
        if set(rule) - {"name", "lhs", "rhs"}:
            continue
        substitution = dict.fromkeys(_variables(lhs, signature), seed)
        redex = _substitute(lhs, substitution)
        other = next(index for index in range(1, len(signature[recursive]) + 1) if index != argument)
        arguments = [seed] * len(signature[recursive])
        arguments[argument - 1] = (wrapper, tuple([seed] * len(signature[wrapper])))
        arguments[other - 1] = redex
        context = (recursive, tuple(arguments))
        step = _step(rule, lhs, rhs, substitution, context, [other])
        source, target = _replay_step(step, parsed, signature)
        if source != target:
            return {
                "holds": False,
                "reason": "normal_form_claim_has_reducible_argument",
                "statement": {"recursive_symbol": recursive, "argument": argument, "wrapper": wrapper},
                "witness": step,
                "replay_verified": True,
            }
    return None


def _existing_call_depth(text, all_texts, contract):
    match = re.search(
        rf"no rule can increase that `?(?P<succ>{_SYMBOL})`?-depth for an existing `?(?P<rec>{_SYMBOL})`?-call",
        text,
        re.I,
    )
    if not match:
        return None
    succ, recursive = match["succ"], match["rec"]
    for other in all_texts:
        binding = re.search(
            rf"number of leading `?{re.escape(succ)}`? constructors in that `?{re.escape(recursive)}`?['’]s "
            rf"{_ORDINAL_ARGUMENT} argument",
            other,
            re.I,
        )
        if binding:
            return argument_count_refutation(
                recursive, _ORDINALS[binding["ordinal"].lower()], succ,
                contract.rules, contract.signature, multiset=False,
            )
    return None


def _only_redex_creating_rule(text, contract):
    match = re.search(rf"\bthe only redex-creating rule for `?(?P<rec>{_SYMBOL})`? is\b", text, re.I)
    if not match or match["rec"] not in contract.signature:
        return None
    parsed = _parsed_rules(contract.rules, contract.signature)
    witnesses = {}
    for entry in parsed:
        if set(entry[0]) - {"name", "lhs", "rhs"}:
            continue
        witness = _redex_creation_witness(entry, match["rec"], parsed, contract.signature)
        if witness:
            witnesses[entry[0]["name"]] = witness
    if len(witnesses) < 2:
        return None
    return {
        "holds": False,
        "reason": "redexes_created_by_more_than_one_rule",
        "recursive_symbol": match["rec"],
        "witness": {"creation_steps": witnesses},
        "replay_verified": True,
    }


def quoted_assertion_refutations(
    quotes: list[str], contract: InstanceContract, *, source_text: str | None = None
) -> list[dict[str, Any]]:
    """Check exact source quotations without importing reviewer conclusions.

    Only closed statements with a contract-replayed counterexample are
    refuted. Call-local wording such as "once F reaches Z, rewriting stops"
    has a true reading and stays pending; only explicit whole-term wording is
    refuted. A duplication example refutes only a denial of copying. The
    optional ``source_text`` supplies the displayed rule and definitions that
    bind a quoted claim; it never supplies a missing claim.
    """

    results: list[dict[str, Any]] = []
    normalized = [(quote, _text(quote, contract)) for quote in quotes if quote]
    all_texts = [text for _raw, text in normalized]
    if source_text:
        all_texts.append(_text(source_text, contract))

    def add(claim: str, raw: str, decision: dict[str, Any] | None, basis: str) -> None:
        if decision and decision.get("holds") is False:
            results.append({"claim": claim, "quote": raw, "decision": decision, "basis": basis})

    for raw, text in normalized:
        if _QUOTE_DISOWNED.search(text):
            continue
        stop = re.search(
            rf"\b(?:once|when|after)\s+(?P<recursive>{_SYMBOL})\s+reaches\s+(?P<base>{_SYMBOL})\s*,?\s*"
            r"(?:all rewriting stops|no (?:further )?rewriting (?:is possible |can occur |occurs )?anywhere|"
            r"no rule applies anywhere|the (?:whole|entire) term is (?:a |in )?normal form)\b",
            text,
            re.I,
        )
        if stop:
            add(
                "base_case_stops_rewriting",
                raw,
                structural_refutation(
                    ("base_case_stops_rewriting", stop["recursive"], stop["base"]),
                    contract.rules,
                    contract.signature,
                    contract.target_policy.get("relation_semantics"),
                ),
                "source quotation plus replayed contract counterexample",
            )

        copy_denial = re.search(
            r"\b(?:no rule (?:ever )?(?:duplicates|copies)|(?:the )?(?:rules?|rewriting|recursive rule|step rule) "
            r"(?:never|does not|doesn't|cannot|can't) (?:duplicate|copy)|nothing is (?:ever )?(?:duplicated|copied)|"
            r"the number of redex(?:es| occurrences) (?:never|does not|cannot) increases?)\b",
            text,
            re.I,
        )
        if copy_denial:
            witness = _duplicated_redex_witness(contract)
            if witness:
                add(
                    "no_duplicated_reducible_material",
                    raw,
                    {"holds": False, "reason": "ground_rule_step_duplicates_a_reducible_term", "witness": witness},
                    "source quotation plus parsed contract rules",
                )

        if contract.target_policy.get("relation_semantics") != "standard_contextual_closure":
            continue
        try:
            add("strict_decrease_at_base_step", raw,
                _zero_base_strict_decrease(raw, text, all_texts, source_text, contract),
                "source quotation, stated measure definition and replayed rewrite")
            add("normal_form_with_headed_argument", raw, _headed_argument_normal_form(text, contract),
                "source quotation plus replayed contextual rewrite")
            add("existing_call_depth_nonincrease", raw, _existing_call_depth(text, all_texts, contract),
                "source quotation, bound measure sentence and replayed rewrite")
            add("single_redex_creating_rule", raw, _only_redex_creating_rule(text, contract),
                "source quotation plus replayed redex-creating steps for each rule")
        except (KeyError, TypeError, ValueError, StopIteration, IndexError):
            continue
    for result in results:
        result["certificate_sha256"] = canonical_sha256(result)
    return results


def _offered(claim):
    return claim.get("claim_status") == "claimed_valid" and claim.get("answer_role") in OFFER_ROLES


def _argument_facts(record, contract):
    facts = {}
    anchors = record.get("anchors", {})
    for claim in record.get("claims", []):
        if claim.get("kind") != "call_measure" or not _offered(claim):
            continue
        for ref in claim.get("evidence", []):
            anchor = anchors.get(ref, {})
            if anchor.get("source_id") != claim.get("source_id"):
                continue
            match = _ARGUMENT_ASSERTION.fullmatch(_text(anchor.get("text", ""), contract))
            if not match:
                continue
            ordinal, symbol = match.groups()
            argument = _ORDINALS[ordinal.lower()]
            if symbol not in contract.signature or argument > len(contract.signature[symbol]):
                continue
            key = ("argument", symbol, argument)
            facts[key] = {"anchor_id": ref, "source_id": anchor["source_id"],
                          "text": anchor["text"], "claim_id": claim["local_id"]}
    return facts


def _precedence_facts(record, contract):
    # A single stated path order fixes the referent of "this order". Two
    # alternatives, a replacement order, or a conditional case are not merged.
    orders = [c for c in record.get("claims", []) if c.get("kind") in {"lpo", "rpo", "mpo"}]
    if len(orders) != 1 or not _offered(orders[0]):
        return {}
    claim = orders[0]
    anchors = {ref: a for ref, a in record.get("anchors", {}).items()
               if a.get("source_id") == claim.get("source_id")}
    if not any(re.fullmatch(r"All rewrite rules are then contained in this order:?",
                           a.get("text", "").strip(), re.I) for a in anchors.values()):
        return {}
    facts = {}
    for ref, anchor in anchors.items():
        raw = re.sub(r"\s+", " ", anchor.get("text", "")).strip()
        if _DISOWNED.search(raw):
            continue
        declaration = re.search(
            r"with (?:a )?(?:suitable )?precedence\s*(?:\(e\.g\.,\s*)?(`[^`]+`)", raw, re.I
        )
        case = re.search(r", with ((?:`[^`]+`)(?: and `[^`]+`)*), we ", raw)
        strings = []
        if declaration and ref in claim.get("evidence", []):
            strings.append(declaration[1][1:-1])
        if case and raw.startswith("For `") and raw.endswith("so the condition holds."):
            strings.extend(re.findall(r"`([^`]+)`", case[1]))
        for expression in strings:
            normalized = _text(expression, contract).replace("≻", ">")
            if not _CHAIN.fullmatch(normalized):
                continue
            names = [s.strip() for s in normalized.split(">")]
            if not set(names) <= contract.signature_symbols:
                continue
            for left, right in zip(names, names[1:]):
                facts[("precedence", left, right)] = {
                    "anchor_id": ref, "source_id": anchor["source_id"],
                    "text": anchor["text"], "expression": expression,
                    "claim_id": claim["local_id"],
                }
    return facts


def _structural_facts(record, contract):
    """Type only complete quoted assertions also retained in a stated proof field.

    'The only redexes are ...' asserts a property of the given system; it is
    not 'consider root-only rewriting'. A separate root-only case has no
    contextual consequence and is excluded by the source/target checks.
    """
    if contract.target_policy.get("relation_semantics") != "standard_contextual_closure":
        return {}
    contextual_sources = {c.get("source_id") for c in record.get("claims", [])
                          if _offered(c) and c.get("claimed_target") == "full_contextual_sn"}
    facts = {}
    for claim in record.get("claims", []):
        if (claim.get("kind") != "root_control_proof" or not _offered(claim)
                or claim.get("source_id") not in contextual_sources):
            continue
        fields = {k: _text(v, contract) for k, v in claim.get("transcription", {}).items()
                  if k in {"principle", "definition", "relation"} and isinstance(v, str)}
        for ref in claim.get("evidence", []):
            anchor = record.get("anchors", {}).get(ref, {})
            if anchor.get("source_id") != claim.get("source_id"):
                continue
            text = _text(anchor.get("text", ""), contract)
            statement = _wrapper_fact(text)
            # Readers can quote the following constructor sentence or omit it;
            # both the quote and stated field must independently type as the
            # same complete assertion. Substring matches are not sufficient.
            same_wrapper = (statement is not None
                            and any(_wrapper_fact(v) == statement for v in fields.values()))
            if text not in fields.values() and not same_wrapper:
                continue
            if fields.get("relation") and fields["relation"] != text:
                statement = None
            match = _BASE_STOPS.fullmatch(text)
            if match and (not fields.get("relation") or fields["relation"] == text):
                constructors = set(re.findall(_SYMBOL, match["constructors"])) - {"or"}
                if (constructors <= contract.signature_symbols
                        and match["base"] in constructors
                        and match["recursive"] in contract.signature_symbols):
                    statement = ("base_case_stops_rewriting", match["recursive"], match["base"])
            match = _OUTERMOST.fullmatch(text)
            if match and (not fields.get("relation") or fields["relation"] == text):
                statement = ("only_outermost_redexes", match["recursive"])
            if statement:
                facts[statement] = {"anchor_id": ref, "source_id": anchor["source_id"],
                                    "text": anchor["text"], "claim_id": claim["local_id"],
                                    "stated_fields": fields}
    return facts


def _surviving_argument_facts(record, contract):
    if contract.target_policy.get("relation_semantics") != "standard_contextual_closure":
        return {}
    facts = {}
    anchors = record.get("anchors", {})
    for claim in record.get("claims", []):
        if not _offered(claim) or claim.get("kind") != "root_control_proof":
            continue
        payload = claim.get("transcription", {})
        if set(payload) != {"principle"}:
            continue
        text = _text(payload["principle"], contract)
        match = re.fullmatch(
            rf"No rule rewrites {_SYMBOL}, {_SYMBOL}, or {_SYMBOL}, and no rule can increase that "
            rf"(?P<s>{_SYMBOL})-depth for an existing (?P<f>{_SYMBOL})-call\.", text)
        refs = [ref for ref in claim.get("evidence", []) if anchors.get(ref, {}).get("source_id")
                == claim.get("source_id") and _text(anchors[ref]["text"], contract) == text]
        if not match or not refs:
            continue
        for call in record.get("claims", []):
            if not _offered(call) or call.get("kind") != "call_measure" or call.get("source_id") != claim.get("source_id"):
                continue
            p = call.get("transcription", {})
            for ref in call.get("evidence", []):
                quote = anchors.get(ref, {})
                if quote.get("source_id") != call.get("source_id"):
                    continue
                binding = re.fullmatch(
                    rf"So each rewrite at an {re.escape(match['f'])}-redex strictly decreases the number "
                    rf"of leading {re.escape(match['s'])} constructors in that {re.escape(match['f'])}['’]s "
                    r"(first|second|third|fourth|fifth) argument\.", _text(quote.get("text", ""), contract))
                if (binding and p.get("argument") == _ORDINALS[binding[1]]
                        and p.get("measure") == match["s"] + "_count" and p.get("measure_mode") == "leading_chain"):
                    statement = ("surviving_argument_nonincrease", match["f"], p["argument"], match["s"])
                    facts[statement] = {"anchor_id": refs[0], "claim_id": claim["local_id"],
                                        "text": anchors[refs[0]]["text"], "source_id": claim["source_id"],
                                        "binding_anchor_id": ref, "binding_text": quote["text"]}
    return facts


def _cycle(edges):
    adjacency = {}
    for left, right in sorted(edges):
        adjacency.setdefault(left, []).append(right)
    visited = set()

    def visit(node, path):
        if node in path:
            return path[path.index(node):] + [node]
        if node in visited:
            return None
        for neighbor in adjacency.get(node, []):
            found = visit(neighbor, path + [node])
            if found:
                return found
        visited.add(node)
        return None

    for node in sorted(adjacency):
        found = visit(node, [])
        if found:
            return found
    return None


def source_refutations(records: list[dict[str, Any]], contract: InstanceContract, *,
                       single_extractor: bool = False) -> list[dict[str, Any]]:
    """Input records must already pass source/hash/schema validation.

    Every fact must appear in every supplied reader's quotes. Single mode
    requires exactly one record and labels its evidence accordingly. This route
    never creates an extraction, supplies a missing measure, or chooses a reader.
    """
    if (single_extractor and len(records) != 1) or (not single_extractor and len(records) < 2):
        return []
    extractors = [r.get("extractor", {}) for r in records]
    if (len({e.get("extractor_id") for e in extractors}) != len(records)
            or len({e.get("pass_number") for e in extractors}) != len(records)
            or not all(e.get("independence_attestation") is True for e in extractors)
            or not all(r.get("record_status") == "complete" for r in records)):
        return []
    if len({canonical_sha256(r.get("session")) for r in records}) != 1:
        return []
    inputs = {str(r["extractor"]["pass_number"]): canonical_sha256(r) for r in records}
    certificate_type = ("prt-single-source-refutation/v1" if single_extractor
                        else "prt-common-source-refutation/v1")
    binding = {"certificate_type": certificate_type, "verdict": "REFUTED",
               "contract": contract.binding(), "record_sha256_by_pass": inputs}
    facts_by_pass = {
        str(r["extractor"]["pass_number"]): {
            **_argument_facts(r, contract), **_precedence_facts(r, contract),
            **_structural_facts(r, contract), **_surviving_argument_facts(r, contract),
        } for r in records
    }
    common = set.intersection(*(set(facts) for facts in facts_by_pass.values()))
    certificates = []
    for statement in sorted(k for k in common if k[0] == "surviving_argument_nonincrease"):
        _, recursive, argument, successor = statement
        decision = argument_count_refutation(recursive, argument, successor, contract.rules,
                                               contract.signature, multiset=False)
        if decision:
            certificates.append({**binding, "claim": statement[0],
                                 "facts_by_pass": {p: f[statement] for p, f in facts_by_pass.items()},
                                 "decision": decision})
    for statement in sorted(k for k in common if k[0] in {
            "universal_wrapper_normality", "base_case_stops_rewriting", "only_outermost_redexes"}):
        decision = structural_refutation(
            statement, contract.rules, contract.signature,
            contract.target_policy.get("relation_semantics"))
        if decision:
            certificates.append({**binding, "claim": statement[0],
                                 "facts_by_pass": {p: f[statement] for p, f in facts_by_pass.items()},
                                 "decision": decision})
    for key in sorted(k for k in common if k[0] == "argument"):
        _, symbol, argument = key
        obj = {"kind": "call_measure", "payload": {"scope": "dependency_pair", "argument": argument}}
        decision = call_measure_dependency_pair_decision(
            obj, obj, contract.rules, contract.signature, {"size"},
        )
        witness = decision.get("witness", {})
        if (decision.get("holds") is False and decision.get("recursive_symbol") == symbol
                and witness.get("type") == "identical_recursive_argument"):
            certificates.append({**binding, "claim": "strict_recursive_argument_descent",
                                 "facts_by_pass": {p: f[key] for p, f in facts_by_pass.items()},
                                 "decision": decision})
    cycle = _cycle({(k[1], k[2]) for k in common if k[0] == "precedence"})
    if cycle:
        used = [("precedence", left, right) for left, right in zip(cycle, cycle[1:])]
        certificates.append({**binding, "claim": "stated_strict_precedence",
                             "facts_by_pass": {p: [f[k] for k in used]
                                               for p, f in facts_by_pass.items()},
                             "decision": {"holds": False, "cycle": cycle,
                                          "basis": "transitivity_would_force_a_strict_self_comparison"}})
    for certificate in certificates:
        certificate["certificate_sha256"] = canonical_sha256(certificate)
    return certificates
