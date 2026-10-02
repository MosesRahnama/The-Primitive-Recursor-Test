"""Keep quoted rewrite bounds separate from one-step descent certificates."""

from __future__ import annotations

import re

from .canonical import fold_glyph_tokens, fold_presentation
from .native_math import render_term
from .proof_obligations import _parsed_rules, _substitute, _variables
from .structural_premises import _replay_step, _step

_BOUND = re.compile(
    r"\b(?:the )?(?:recursion|recursive(?: call)?) depth is bounded by\b"
    r"|\byou can only apply (?:rule|the rule)\b[^.!?\n]{0,100}\bas many times as\b"
    r"|\bthe number of (?:possible )?(?:reductions|rewrite steps|rule applications) "
    r"is bounded by\b",
    re.I,
)


def quoted_total_bound_refutation(claim, contract):
    """Refute an explicitly universal zero-count bound with one replayed step."""
    if (claim.get("kind") != "call_measure" or claim.get("specificity") != "unparseable"
            or claim.get("claimed_target") != "full_contextual_sn"
            or claim.get("transcription") or (claim.get("source_specification") or {}).get("status") != "complete"
            or contract.target_policy.get("relation_semantics") != "standard_contextual_closure"):
        return None
    pattern = re.compile(
        r"Every reduction sequence(?: therefore)? must terminate after finitely many steps "
        r"\(bounded by the number of ([A-Za-z][A-Za-z0-9_]*) constructors in the "
        r"(first|second|third|fourth|fifth) argument\)\.")
    parsed = _parsed_rules(contract.rules, contract.signature)
    heads = {lhs[0] for _, lhs, _ in parsed}
    if len(heads) != 1:
        return None
    recursive = next(iter(heads))
    for anchor in claim.get("evidence", []):
        text = fold_glyph_tokens(fold_presentation(anchor["text"], markdown_emphasis=True), contract.glyph_folds)
        text = re.sub(r"\s+", " ", text).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            match = pattern.fullmatch(sentence)
            if not match:
                continue
            symbol = match[1]
            argument = ["first", "second", "third", "fourth", "fifth"].index(match[2]) + 1
            if (symbol not in contract.signature or len(contract.signature[symbol]) != 1
                    or argument > len(contract.signature[recursive])):
                continue
            constants = sorted(s for s, params in contract.signature.items() if not params)
            if not constants:
                continue
            seed = constants[0], ()

            def count(term):
                return int(term[0] == symbol) + sum(count(a) for a in term[1])

            for rule, lhs, rhs in parsed:
                if set(rule) - {"name", "lhs", "rhs"}:
                    continue
                substitution = dict.fromkeys(_variables(lhs, contract.signature), seed)
                source = _substitute(lhs, substitution)
                step = _step(rule, lhs, rhs, substitution, source, [])
                left, right = _replay_step(step, parsed, contract.signature)
                bound = count(left[1][argument-1])
                if bound != 0:
                    continue
                proof = {"holds": False, "reason": "replayed_total_reduction_bound_counterexample",
                         "statement": sentence, "recursive_symbol": recursive, "argument": argument,
                         "counted_symbol": symbol, "counted_rules": "all", "replay_verified": True,
                         "witness": {"type": "reduction_length_exceeds_stated_bound", "steps": [step],
                                     "initial_argument": render_term(left[1][argument-1]),
                                     "bound": bound, "observed_steps": 1, "final_term": render_term(right)}}
                return proof, [anchor], "total_reduction_bound_as_stated"
    return None


def quoted_recursive_chain_bound(claim, contract):
    """Check the exact rule-2/S-chain bound from the structured rule table."""

    if (
        claim.get("kind") not in {"call_measure", "additive_measure"}
        or claim.get("claim_status") != "claimed_valid"
        or claim.get("claimed_target") != "local_descent"
    ):
        return None
    payload = claim.get("transcription") or {}
    if claim["kind"] == "call_measure":
        if (
            payload.get("argument") != 3
            or payload.get("scope") != "dependency_pair"
            or payload.get("measure") not in {"S_count", "symbol_count_S"}
        ):
            return None
    elif payload.get("named") not in {"S_count", "symbol_count_S"}:
        return None
    if "S" not in contract.signature or len(contract.signature["S"]) != 1:
        return None
    if "Z" not in contract.signature or contract.signature["Z"]:
        return None
    parsed = _parsed_rules(contract.rules, contract.signature)
    if len(parsed) != 2:
        return None
    _, base_lhs, base_rhs = parsed[0]
    step_rule, step_lhs, step_rhs = parsed[1]
    if (
        base_lhs[0] != step_lhs[0]
        or len(step_lhs[1]) < 3
        or base_lhs[1][2] != ("Z", ())
        or step_lhs[1][2][0] != "S"
        or len(step_lhs[1][2][1]) != 1
    ):
        return None
    recursive = step_lhs[0]
    predecessor = step_lhs[1][2][1][0]

    def calls(term):
        found = [term] if term[0] == recursive else []
        for argument in term[1]:
            found.extend(calls(argument))
        return found

    base_calls = calls(base_rhs)
    step_calls = calls(step_rhs)
    if (
        base_calls
        or len(step_calls) != 1
        or len(step_calls[0][1]) < 3
        or step_calls[0][1][2] != predecessor
    ):
        return None
    pattern = re.compile(
        r"(?:the recursion is structurally bounded:\s*)?you can only apply rule 2 "
        r"as many times as there are S constructors wrapping Z\.?",
        re.IGNORECASE,
    )
    for anchor in claim.get("evidence", []):
        text = fold_glyph_tokens(
            fold_presentation(anchor.get("text", ""), markdown_emphasis=True),
            contract.glyph_folds,
        )
        text = re.sub(r"\s+", " ", text).strip(" -")
        if not pattern.fullmatch(text):
            continue
        proof = {
            "holds": True,
            "reason": "one_recursive_call_removes_one_leading_S",
            "statement": text,
            "rule": step_rule.get("name"),
            "rule_ordinal_one_based": 2,
            "recursive_symbol": recursive,
            "argument": 3,
            "counted_symbol": "S",
            "base_symbol": "Z",
            "recursive_call_count": 1,
            "chain_scope": "one_recursive_call_chain",
            "supported_targets": ["local_descent"],
        }
        return proof, [anchor], "recursive_chain_bound_as_stated"
    return None


def bound_assertion_issue(claim: dict) -> str | None:
    """A descent certificate does not check an additional source bound.

    Inspect each reading's own evidence. Missing evidence is not a bound,
    and this guard issues neither a refutation nor a replacement measure.
    """
    kind = claim.get("mathematical_core", {}).get("kind")
    if kind not in {"call_measure", "additive_measure"}:
        return None
    for entries in claim.get("evidence_by_pass", {}).values():
        for anchor in entries:
            text = re.sub(r"[`*_]", "", anchor.get("text", ""))
            if _BOUND.search(text):
                return "source_bound_requires_separate_obligation"
    return None
