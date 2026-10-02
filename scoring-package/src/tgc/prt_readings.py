"""Check each independent reading without inventing claim-level consensus."""

from __future__ import annotations

import re
from copy import deepcopy

from .assertion_obligations import (
    bound_assertion_issue,
    quoted_recursive_chain_bound,
    quoted_total_bound_refutation,
)
from .canonical import canonical_tuple_order, fold_glyph_tokens
from .common import canonical_sha256
from .native_math import _typed_interpretation, generated_minimum, parse_term
from .occurrence_obligations import (
    quoted_global_multiset,
    quoted_inert_head,
    quoted_multiset_refutation,
    quoted_occurrence_sum,
)
from .path_order_obligations import quoted_universal_precedence
from .proof_obligations import (
    ground_term_interpretation_decision,
    interpretation_payload_matches,
    rule_size_decision,
)
from .prt_policy import POLICY_VERSION, project_checked_claims
from .scoring_v3 import _boundary_verdict
from .validation import load_sources

AXES = ("method_mathematical_validity", "method_correct_and_admissible")


def _evidence(claim):
    entries = list(claim.get("evidence", []))
    for field in ("axis_evidence", "field_evidence"):
        for values in claim.get(field, {}).values():
            entries.extend(values)
    return list({(a["source_id"], a["start"], a["end"]): a for a in entries}.values())


def _rule_key(lhs, rhs, signature):
    variables = {}

    def key(term):
        name, args = term
        if name not in signature:
            if args:
                raise ValueError("unknown function symbol")
            return ("variable", variables.setdefault(name, len(variables)))
        if len(args) != len(signature[name]):
            raise ValueError("wrong arity")
        return name, tuple(key(a) for a in args)

    return key(lhs), key(rhs)


# Source names are aliases for these exact rule shapes, never proof authorities.
_RULE_ALIASES = {
    "R_int_delta": ("integrate(delta(t))", "void"),
    "R_merge_void_left": ("merge(void,t)", "t"),
    "R_merge_void_right": ("merge(t,void)", "t"),
    "R_merge_cancel": ("merge(t,t)", "t"),
    "R_eq_refl": ("eqW(a,a)", "void"),
}


def quoted_size_scope(claim, contract):
    """Recognize two closed forms of local size assertions in frozen records."""
    if (claim.get("kind") != "additive_measure" or claim.get("answer_role") != "supporting"
            or claim.get("claimed_target") != "local_descent"):
        return None
    payload = claim.get("transcription", {})
    if payload not in ({}, {"named": "term_size"}):
        return None
    rule_keys = {_rule_key(parse_term(r["lhs"]), parse_term(r["rhs"]), contract.signature): r["name"]
                 for r in contract.rules}
    texts = [re.sub(r"\s+", " ", a["text"]).strip()
             for a in claim.get("evidence", [])]
    for anchor, text in zip(claim.get("evidence", []), texts):
        match = re.fullmatch(r"(?:\d+\. )?In the (?:base|recursive) case `([^`]+)`, "
                             r"the term size strictly decreases\.?", text)
        if match:
            sides = re.split(r"\s*(?:->|→)\s*", fold_glyph_tokens(match[1], contract.glyph_folds))
            if len(sides) != 2:
                continue
            try:
                name = rule_keys.get(_rule_key(*(parse_term(s) for s in sides), contract.signature))
            except ValueError:
                continue
            if name:
                return [name], [anchor], "strict_term_size"
        match = re.fullmatch(
            r"((?:`R_\w+`(?:,? and |, | and )?)+) all replace a term with a strictly smaller one "
            r"\(`void` or a proper subterm `t`\)\. These rules clearly contribute to termination\.", text)
        if match and any("reduce the size or complexity of the term." in t for t in texts):
            aliases = re.findall(r"`(R_\w+)`", match[1])
            if not aliases or len(aliases) != len(set(aliases)) or not set(aliases) <= _RULE_ALIASES.keys():
                continue
            names = [rule_keys.get(_rule_key(*(parse_term(s) for s in _RULE_ALIASES[a]),
                                              contract.signature)) for a in aliases]
            if all(names):
                # Size proves the stated disjunction's first alternative; no
                # interpretation of the unspecified "complexity" is invented.
                return names, list(claim["evidence"]), "size_or_complexity_by_size"
    return None


def _source_term_map(claim, contract, source_texts):
    if (contract.instance_key != "test01-ko7" or claim.get("kind") != "poly_interpretation"
            or claim.get("specificity") != "concrete"
            or claim.get("claimed_target") != "full_contextual_sn"):
        return None
    evidence = _evidence(claim)
    definitions = [a for p, entries in claim.get("field_evidence", {}).items()
                   if p.startswith("/transcription/definitions/") for a in entries]
    if not definitions:
        return None
    first = min(definitions, key=lambda a: a["start"])
    for anchor in evidence:
        if anchor["source_id"] != first["source_id"]:
            continue
        text = anchor["text"]
        if re.search(r"\b(?:not|if|suppose|hypothetical|wrong|reject|incorrect)\b", text, re.I):
            continue
        if not re.search(
            r"`(?:‖·‖|\|?[A-Za-z][A-Za-z0-9_]*\|?)\s*:\s*"
            r"Trace\s*(?:→|->)\s*(?:ℕ|Nat)`",
            text,
        ):
            continue
        if anchor["start"] <= first["start"] < anchor["end"]:
            return anchor
        if anchor["end"] > first["start"] or first["start"] - anchor["end"] > 96:
            continue
        gap = source_texts[anchor["source_id"]][anchor["end"]:first["start"]]
        if gap.strip(" \t\r\n`:") and not re.fullmatch(
            r"\s*\|\s*Constructor\s*\|\s*Interpretation\s*\|\s*"
            r"\|\s*:?-+:?\s*\|\s*:?-+:?\s*\|\s*",
            gap,
            re.IGNORECASE,
        ):
            continue
        return anchor
    return None


def _descriptor(claim, number):
    # The checker API accepts assertions as well as consensus objects. These
    # are the one reader's actual fields, not a second vote or a forged gate.
    key = str(number)
    return {
        "decision_context": "single_independent_reading_not_claim_consensus",
        "mathematical_core": claim["mathematical_core"],
        "representative_checker_object": claim["checker_object"],
        "checker_objects_by_pass": {key: claim["checker_object"]},
        "checker_input_schema_version": claim["checker_input_schema_version"],
        "evidence_by_pass": {key: claim["evidence"]},
        "field_evidence_by_pass": {key: claim["field_evidence"]},
        "axis_evidence_by_pass": {key: claim["axis_evidence"]},
        "field_consensus": {axis: {"status": "agreed", "value": claim[axis],
                                   "votes": {key: claim[axis]}, "support_count": 1}
                            for axis in ("claim_status", "answer_role", "claimed_target", "specificity")},
    }


def _source_obligation(claim, contract, source_texts):
    bounded_chain = quoted_recursive_chain_bound(claim, contract)
    if bounded_chain is not None:
        return bounded_chain
    for route in (quoted_occurrence_sum, quoted_multiset_refutation, quoted_global_multiset, quoted_inert_head,
                  quoted_universal_precedence):
        result = route(claim, contract)
        if result is not None:
            return result
    scoped = quoted_size_scope(claim, contract)
    if scoped:
        rules, evidence, statement = scoped
        proof = rule_size_decision(rules, "strict", contract.rules, contract.signature)
        return proof, evidence, statement
    scope = _source_term_map(claim, contract, source_texts)
    if scope and interpretation_payload_matches(
            claim["mathematical_core"], claim["checker_object"].get("payload", {}), contract.signature):
        interpretation, issue = _typed_interpretation(claim["mathematical_core"], contract.signature)
        constants = [p.get((), 0) for params, p in interpretation.values() if not params]
        safe = (not issue and constants and 0 <= min(constants) <= 1024
                and all(c >= 0 for _, polynomial in interpretation.values() for c in polynomial.values()))
        minimum = generated_minimum(interpretation) if safe else None
        if minimum is not None:
            proof = ground_term_interpretation_decision(
                claim["mathematical_core"], contract.rules, contract.signature, minimum[0])
            proof["term_lower_bound_basis"] = "computed_from_complete_constructor_definitions"
            return proof, [scope] + list(claim["evidence"]), "ground_term_map_as_stated"
    return None


def _unresolved_action(claim, entry):
    spec = claim.get("source_specification") or {}
    if spec.get("status") == "missing_definition":
        return {"reason": "source_definition_missing", "missing_components": spec["missing_components"],
                "action": "deny_witness_credit;retain_stated_obligations;never_supply_missing_content"}
    if spec.get("status") == "ambiguous":
        return {"reason": "source_ambiguity", "action": "check_every_recorded_reading;do_not_choose_a_verdict"}
    if entry["detail"] == "source_bound_requires_separate_obligation":
        return {"reason": "bound_not_checked_by_descent",
                "action": "retain_counted_rules_initial_quantity_and_scope;check_bound_separately"}
    if claim["kind"] == "poly_interpretation" and "domain" not in claim.get("transcription", {}):
        return {"reason": "unstated_carrier_or_term_scope",
                "action": "seek_explicit_carrier_or_term_map_in_source;do_not_supply_one"}
    if claim["kind"] == "root_control_proof" and claim["specificity"] == "partial":
        return {"reason": "structural_premise_not_typed",
                "action": "quote_scope_quantifiers_and_comparison;retain_ambiguity_if_unstated"}
    if claim["specificity"] == "unparseable":
        if spec.get("status") == "complete":
            return {"reason": "complete_source_unsupported_by_checker",
                    "action": "implement_source_faithful_representation_and_checker;do_not_deny_credit_for_engine_limits"}
        return {"reason": "source_gap_or_unsupported_representation",
                "action": "distinguish_missing_definition_from_template_limit;never_complete_source"}
    return {"reason": entry["detail"], "action": "inspect_unproved_obligation_without_changing_source"}


STATUS_WORDING_NOT_TRANSCRIBED = "path_status_wording_in_claim_evidence_not_transcribed"
_PATH_STATUS_WORDING = re.compile(
    r"\b(?:lexicographic(?:ally)?|multiset|subterm-based|recursive path|lexicographic path)\b",
    re.IGNORECASE,
)


def _alternative_statuses(claim):
    """Statuses stated as alternatives ('lexicographic or multiset status')."""

    transcription = claim.get("transcription") or {}
    if claim.get("kind") not in {"lpo", "rpo"} or "status" not in transcription:
        return None
    status = str(transcription.get("status") or "")
    if canonical_tuple_order(status).get("mode") != "lex_of_multiset":
        return None
    if not re.search(r"\b(?:or|either)\b", status, re.IGNORECASE):
        return None
    return ("lex", "multiset")


def _source_insufficiency(claim):
    """Return a strict-N reason only when the represented source is definite."""

    transcription = claim.get("transcription") or {}
    kind = claim.get("kind")
    if kind in {"lpo", "rpo"} and "status" in transcription:
        status = str(transcription.get("status") or "")
        mode = canonical_tuple_order(status).get("mode")
        if mode == "unparseable" and re.search(
            r"\b(?:treated )?monoton(?:ic|ically)\b", status, re.IGNORECASE
        ):
            evidence_text = " ".join(
                str(anchor.get("text") or "") for anchor in claim.get("evidence", [])
            )
            if _PATH_STATUS_WORDING.search(evidence_text) and not _PATH_STATUS_WORDING.search(status):
                # The claim's own quotation names a status the field omits:
                # an extraction gap, not a source omission.
                return STATUS_WORDING_NOT_TRANSCRIBED
            return "path_argument_comparison_not_specified"
    if kind == "global_multiset_measure":
        order = transcription.get("order")
        if isinstance(order, str) and (
            canonical_tuple_order(order).get("mode") == "lex_of_multiset"
            or (
                re.search(r"\bmultisets?\b", order, re.IGNORECASE)
                and re.search(r"\blexicograph", order, re.IGNORECASE)
            )
        ):
            return "multiset_comparison_order_not_defined"
    if (
        kind == "poly_interpretation"
        and transcription.get("interpretation_scope") != "dependency_pair"
        and "domain" not in transcription
    ):
        evidence_text = " ".join(
            str(anchor.get("text") or "") for anchor in claim.get("evidence", [])
        )
        if not re.search(
            r"\b(?:natural numbers?|naturals?|positive integers?|carrier|codomain)\b|ℕ",
            evidence_text,
            re.IGNORECASE,
        ):
            return "polynomial_scalar_domain_not_stated"
    return None


def _variant_claim(claim, core_updates, checker_updates):
    variant = deepcopy(claim)
    variant["mathematical_core"].setdefault("payload", {}).update(core_updates)
    variant["checker_object"].setdefault("payload", {}).update(checker_updates)
    return variant


def _run_contract_checker(claim, number, checker):
    """Run the contract checker once; a decision needs an input-bound certificate."""

    context = _descriptor(claim, number)
    result = checker(context)
    outcome = result.as_dict()
    certificate = outcome.get("certificate")
    derived = getattr(checker, "__tgc_contract_derived__", {})
    expected_hash = (derived["input_sha256_for_claim"](context)
                     if claim["kind"] in derived.get("kinds", set())
                     else canonical_sha256(claim["checker_object"]))
    if result.verdict in {"PASS", "REFUTED"} and (
        not isinstance(certificate, dict) or certificate.get("input_sha256") != expected_hash
        or certificate.get("verdict") != result.verdict
    ):
        return {"verdict": "UNKNOWN", "detail": "invalid_checker_certificate", "certificate": None,
                "compliant": False}
    return outcome


def _legacy_literal_precedence(claim):
    receipts = (claim.get("canonicalization") or {}).get("receipts") or []
    return any(
        isinstance(receipt, dict)
        and receipt.get("operation") == "legacy-path-order-literal-relation-v1"
        and receipt.get("status") == "applied"
        for receipt in receipts
    )


def _ignored_argument_refutation(claim, contract):
    """An interpretation that ignores an argument of a symbol whose argument can
    rewrite fails strict decrease inside that argument on every carrier."""

    if claim.get("kind") != "poly_interpretation" or claim.get("claimed_target") != "full_contextual_sn":
        return None
    if contract.target_policy.get("relation_semantics") != "standard_contextual_closure":
        return None
    interpretation, issue = _typed_interpretation(claim["mathematical_core"], contract.signature)
    if issue:
        return None
    from .native_math import poly_vars
    from .proof_obligations import _parsed_rules, _substitute, _variables
    from .structural_premises import _replay_step, _step

    constants = sorted(symbol for symbol, parameters in contract.signature.items() if not parameters)
    if not constants:
        return None
    seed = constants[0], ()
    parsed = _parsed_rules(contract.rules, contract.signature)
    for symbol, (parameters, polynomial) in sorted(interpretation.items()):
        present = poly_vars(polynomial)
        for index, parameter in enumerate(parameters, 1):
            if parameter in present:
                continue
            for rule, lhs, rhs in parsed:
                if set(rule) - {"name", "lhs", "rhs"}:
                    continue
                substitution = dict.fromkeys(_variables(lhs, contract.signature), seed)
                arguments = [seed] * len(parameters)
                arguments[index - 1] = _substitute(lhs, substitution)
                step = _step(rule, lhs, rhs, substitution, (symbol, tuple(arguments)), [index])
                source, target = _replay_step(step, parsed, contract.signature)
                if source != target:
                    return {
                        "holds": False,
                        "reason": f"interpretation_ignores_argument_on_every_carrier[{symbol}:{parameter}]",
                        "witness": {**step, "ignored_parameter": parameter,
                                    "value_change": "none: the interpretation of the context ignores this argument"},
                        "replay_verified": True,
                        "supported_targets": [],
                    }
    return None


def _check_reading(record, contract, checker, fruit_guarded):
    number = record["extractor"]["pass_number"]
    sources, issues = load_sources(record)
    if issues:
        raise ValueError("reading source changed after compilation")
    checked = []
    for claim in record["claims"]:
        entry = {k: claim[k] for k in ("claim_id", "kind", "claim_status", "answer_role",
                                      "specificity", "claimed_target")}
        entry.update({"verdict": "UNKNOWN", "detail": "unresolved_reading",
                      "certificate": None, "benchmark_adequacy": "unknown", "boundary_verdict": "unknown"})
        checked.append(entry)
        if "source_specification" in claim:
            entry["source_specification"] = {
                **claim["source_specification"],
                "basis": "source_transcription_not_mathematical_certificate",
                "compiled_claim_sha256": canonical_sha256(claim),
                "contract": contract.binding(),
            }
        checking_rejection = (
            claim["claim_status"] == "claimed_invalid"
            and claim["answer_role"] == "failed_contrast"
        )
        if claim["claim_status"] != "claimed_valid" and not checking_rejection:
            entry["detail"] = "not_endorsed"
            continue
        context = _descriptor(claim, number)
        entry["boundary_verdict"] = _boundary_verdict(context, record["policy_bundle"]["boundary"])
        source_insufficiency = _source_insufficiency(claim)
        if source_insufficiency == STATUS_WORDING_NOT_TRANSCRIBED:
            entry["detail"] = source_insufficiency
            entry["resolution"] = {
                "reason": "status_wording_in_source_not_transcribed",
                "action": "transcribe_the_quoted_path_status;do_not_deny_credit_for_extraction_gaps",
            }
            continue
        if source_insufficiency == "polynomial_scalar_domain_not_stated":
            refutation = _ignored_argument_refutation(claim, contract)
            if refutation is not None:
                entry.update(
                    verdict="REFUTED",
                    detail=refutation["reason"],
                    benchmark_adequacy="not_met",
                    certificate={
                        "certificate_type": "carrier-independent-refutation/v1", "verdict": "REFUTED",
                        "compiled_claim_sha256": canonical_sha256(claim), "contract": contract.binding(),
                        "decision": refutation, "supported_targets": [],
                    },
                )
                continue
        if source_insufficiency:
            entry.update(
                verdict="NO_CONCRETE_WITNESS",
                detail=source_insufficiency,
                benchmark_adequacy="not_met",
                strict_category="N",
                source_insufficiency={
                    "status": "established_from_transcribed_fields",
                    "reason": source_insufficiency,
                    "compiled_claim_sha256": canonical_sha256(claim),
                },
            )
            continue
        if (claim.get("source_specification") or {}).get("status") == "ambiguous":
            entry["detail"] = "source_specification_ambiguous"
            entry["resolution"] = _unresolved_action(claim, entry)
            continue
        bound_obligation = (
            quoted_total_bound_refutation(claim, contract)
            or quoted_recursive_chain_bound(claim, contract)
        )
        bound_issue = bound_assertion_issue(context) if bound_obligation is None else None
        if bound_issue:
            entry["detail"] = bound_issue
            entry["resolution"] = _unresolved_action(claim, entry)
            continue
        obligation = bound_obligation or _source_obligation(claim, contract, sources)
        if obligation is not None:
            proof, evidence, statement = obligation
            if proof.get("holds") is not None:
                entry["verdict"] = "PASS" if proof["holds"] else "REFUTED"
                entry["detail"] = proof["reason"]
                entry["certificate"] = {
                    "certificate_type": "source-scoped-obligation/v1", "verdict": entry["verdict"],
                    "compiled_claim_sha256": canonical_sha256(claim), "contract": contract.binding(),
                    "statement": statement, "source_evidence": evidence, "decision": proof,
                    "supported_targets": proof.get("supported_targets", []) if proof["holds"] else [],
                }
                if statement in {"strict_term_size", "size_or_complexity_by_size",
                                  "absence_of_head_rules_as_stated"} and claim["answer_role"] == "supporting":
                    entry["boundary_verdict"] = "inside"
            else:
                entry["detail"] = proof["reason"]
        elif claim["specificity"] == "family_only":
            entry["verdict"] = "NO_CONCRETE_WITNESS"
            entry["detail"] = "no_parameters_supplied_for_family"
        elif ((claim["specificity"] == "concrete" and claim["canonicalization"]["supported"])
              or (claim["specificity"] == "partial" and claim.get("transcription")
                  and {i.get("code") for i in claim["canonicalization"].get("issues", [])}
                  <= {"PARTIAL_CONSTRUCTION"})):
            alternatives = _alternative_statuses(claim)
            if alternatives:
                # 'lexicographic or multiset status': decide only when every
                # stated alternative gives the same verdict.
                outcomes = {
                    mode: _run_contract_checker(
                        _variant_claim(claim, {"status": {"mode": mode}}, {"status": mode}), number, checker
                    )
                    for mode in alternatives
                }
                verdicts = {outcome["verdict"] for outcome in outcomes.values()}
                if verdicts == {"PASS"}:
                    targets = set.intersection(*(
                        set((outcome.get("certificate") or {}).get("supported_targets", []))
                        for outcome in outcomes.values()
                    ))
                    entry.update(verdict="PASS", detail="every_stated_status_alternative_orients", certificate={
                        "certificate_type": "path-status-alternatives/v1", "verdict": "PASS",
                        "compiled_claim_sha256": canonical_sha256(claim),
                        "alternatives": {mode: outcome["certificate"] for mode, outcome in outcomes.items()},
                        "supported_targets": sorted(targets),
                    })
                elif verdicts == {"REFUTED"}:
                    entry.update(verdict="REFUTED", detail="every_stated_status_alternative_refuted", certificate={
                        "certificate_type": "path-status-alternatives/v1", "verdict": "REFUTED",
                        "compiled_claim_sha256": canonical_sha256(claim),
                        "alternatives": {mode: outcome["certificate"] for mode, outcome in outcomes.items()},
                        "supported_targets": [],
                    })
                else:
                    entry.update(verdict="UNKNOWN", certificate=None, detail=(
                        "stated_status_alternatives_not_decided_alike["
                        + ",".join(f"{mode}:{outcome['verdict']}" for mode, outcome in sorted(outcomes.items()))
                        + "]"
                    ))
            else:
                entry.update(_run_contract_checker(claim, number, checker))
                if (
                    entry["verdict"] == "REFUTED"
                    and claim["kind"] in {"lpo", "rpo"}
                    and _legacy_literal_precedence(claim)
                ):
                    # The legacy format had no quantifier field, so the exact
                    # reading was applied by default. Refute only when no total
                    # extension orients the rules either.
                    extended = _run_contract_checker(
                        _variant_claim(
                            claim,
                            {"precedence_quantifier": "exists_total_extension"},
                            {"precedence_quantifier": "exists_total_extension"},
                        ),
                        number,
                        checker,
                    )
                    if extended["verdict"] != "REFUTED":
                        entry.update(
                            verdict="UNKNOWN",
                            certificate=None,
                            detail="legacy_exact_precedence_refutation_requires_quantifier_reading",
                        )
            if (
                claim["specificity"] == "partial"
                and entry["verdict"] == "PASS"
                and not (
                    claim["kind"] == "root_control_proof"
                    and isinstance(entry.get("certificate"), dict)
                    and entry["certificate"].get("certificate_type")
                    == "root-control-source-obligations/v1"
                )
            ):
                # A missing object field cannot be filled by a successful
                # default in the checker. An explicit false field still refutes.
                entry.update(verdict="UNKNOWN", detail="partial_construction_not_a_full_witness", certificate=None)
        supported = (entry.get("certificate") or {}).get("supported_targets", [])
        if entry["verdict"] == "PASS":
            missing = (claim.get("source_specification") or {}).get("status") == "missing_definition"
            entry["benchmark_adequacy"] = "met" if "full_contextual_sn" in supported and not missing else "not_met"
        elif entry["verdict"] in {"REFUTED", "NO_CONCRETE_WITNESS"}:
            entry["benchmark_adequacy"] = "not_met"
        if entry["verdict"] == "UNKNOWN":
            entry["resolution"] = _unresolved_action(claim, entry)
        if checking_rejection:
            entry["retained_rejection_assessment"] = {
                "REFUTED": "PASS",
                "PASS": "REFUTED",
            }.get(entry["verdict"], "UNKNOWN")
            entry["retained_rejection_basis"] = "checked_rejected_construction"
    return {"pass_number": number, "extractor_id": record["extractor"]["extractor_id"],
            "compiled_record_sha256": canonical_sha256(record), "checks": checked,
            "projection": project_checked_claims(checked, fruit_guarded=fruit_guarded)}


def reading_agreement(records, contract, checker, *, fruit_guarded=False):
    """Require the same checked answer under every complete independent reading."""
    if len(records) < 2:
        return None
    readers = [r["extractor"] for r in records]
    if (len({r["extractor_id"] for r in readers}) != len(readers)
            or len({r["pass_number"] for r in readers}) != len(readers)
            or not all(r.get("independence_attestation") is True for r in readers)
            or any(r["record_status"] != "complete" or r["coverage"]["completeness_status"] != "complete"
                   or r["coverage"].get("completeness_attestation") is not True for r in records)
            or len({canonical_sha256(r["session"]) for r in records}) != 1
            or any(r["contract"] != contract.binding() for r in records)):
        return None
    readings = [_check_reading(r, contract, checker, fruit_guarded)
                for r in sorted(records, key=lambda r: r["extractor"]["pass_number"])]
    result = {"certificate_type": "independent-reading-score-agreement/v1",
              "policy_version": POLICY_VERSION, "contract": contract.binding(), "readings": readings,
              "source_specification_used": any("source_specification" in c for r in records for c in r["claims"]),
              "claim_level_consensus_fabricated": False, "projection": {}}
    for axis in AXES:
        values = {r["projection"][axis] for r in readings}
        result["projection"][axis] = values.pop() if len(values) == 1 and "Unknown" not in values else "Unknown"
    result["certificate_sha256"] = canonical_sha256(result)
    return result


def apply_reading_agreement(projection, evidence):
    result = deepcopy(projection)
    if evidence is None:
        return result
    for axis in AXES:
        value = evidence["projection"][axis]
        if value == "Unknown":
            if evidence.get("source_specification_used"):
                # The older consensus path does not vote this new annotation.
                # It cannot overrule disagreement or a remaining source ambiguity.
                result[axis] = "Unknown"
                result["reasons"].append("source_specification_readings_unresolved:" + axis)
            continue
        if result[axis] == "Unknown":
            result[axis] = value
            result["reasons"].append("all_readings_checked:" + evidence["certificate_sha256"] + ":" + axis)
        elif result[axis] != value:
            result[axis] = "Unknown"
            result["reasons"].append("engine_decision_conflict:" + axis)
    return result
