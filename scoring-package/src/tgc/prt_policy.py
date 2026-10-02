"""PRT whole-response judgments over independently transcribed, checked claims."""

from __future__ import annotations

from typing import Any

from .strict_policy import STRICT_POLICY_VERSION, decide_strict_response

POLICY_VERSION = STRICT_POLICY_VERSION
OFFER_ROLES = frozenset({"primary", "co_primary", "alternative_sufficient", "supporting"})
WITNESS_ROLES = OFFER_ROLES - {"supporting"}
EXTERNAL_KINDS = frozenset(
    {
        "poly_interpretation",
        "lpo",
        "rpo",
        "mpo",
        "kbo",
        "matrix_interpretation",
        "ordinal_measure",
    }
)


def _value(claim: dict[str, Any], axis: str) -> Any:
    vote = claim.get("field_consensus", {}).get(axis, {})
    return vote.get("value") if vote.get("status") == "agreed" else None


def _fruit_refutation_applies(outcome: dict[str, Any]) -> bool:
    """A counterexample to an unguarded rule need not survive a disequality guard.

    Only an explicit counterexample to an unchanged rule is transported here;
    an eq_diff refutation needs a guarded replay and remains undecided.
    """
    certificate = outcome.get("certificate") or {}
    decision = certificate.get("decision") or {}
    witness = decision.get("witness") or {}
    unchanged = {
        "rec_zero",
        "rec_succ",
        "merge_vl",
        "merge_vr",
        "merge_cancel",
        "int_delta",
        "eq_refl",
    }
    if witness.get("type") == "reachable_rule_counterexample":
        if (witness.get("rule") == "eq_diff"
                and certificate.get("certificate_type") == "source-scoped-obligation/v1"
                and certificate.get("statement") == "universal_precedence_as_stated"
                and decision.get("reason") == "universal_precedence_ground_counterexample"
                and decision.get("replay_verified") is True):
            # This certificate's checker replays the instantiated rule and
            # its disequality guard; an unguarded rule failure is insufficient.
            from .native_math import parse_term, render_term
            try:
                source = parse_term(witness["source"])
                guard = witness.get("guard") or {}
                return (source[0] == "eqW" and len(source[1]) == 2
                        and source[1][0] != source[1][1]
                        and guard.get("predicate") == "distinct_eqW_arguments"
                        and guard.get("arguments") == [render_term(t) for t in source[1]])
            except (ValueError, KeyError, TypeError):
                return False
        return witness.get("rule") in unchanged
    if certificate.get("certificate_type") == "root-control-source-obligations/v1":
        readings = certificate.get("reading_decisions", {})
        return bool(readings) and all(
            r.get("verdict") == "REFUTED" and r.get("detail") == "root_control_uniform_bound_false"
            and r.get("witness", {}).get("rule") in unchanged
            and r["witness"].get("type") == "projection_rule_arbitrarily_long_root_chains"
            and type(r["witness"].get("claimed_bound")) is int
            and r["witness"]["claimed_bound"] >= 0
            and r["witness"].get("chain_length") == r["witness"]["claimed_bound"] + 1
            for r in readings.values())
    if certificate.get("certificate_type") != "lex-occurrence-duplication-counterexample/v1":
        return False
    witness = certificate.get("witness") or {}
    rule, variable = witness.get("rule"), witness.get("variable")
    left, right = witness.get("lhs_multiplicity"), witness.get("rhs_multiplicity")
    if (certificate.get("verdict") != "REFUTED" or rule not in unchanged
            or certificate.get("leading_component_basis") != "whole_term_occurrence_sum"
            or not isinstance(variable, str) or not variable
            or type(left) is not int or type(right) is not int or not 0 < left < right):
        return False
    return any(
        row.get("rule") == rule and row.get("duplicated", {}).get(variable) == {
            "lhs_multiplicity": left, "rhs_multiplicity": right,
        }
        for row in certificate.get("duplicating_rules", []) if isinstance(row, dict)
    )


def project_prt_row(row: dict[str, Any], *, fruit_guarded: bool = False) -> dict[str, Any]:
    """Do not substitute the generic engine's existential witness score for PRT."""
    result = {
        "policy_version": POLICY_VERSION,
        "method_mathematical_validity": "Unknown",
        "method_correct_and_admissible": "Unknown",
        "reasons": [],
    }
    reasons: list[str] = result["reasons"]
    for axis in ("record_status", "coverage_status"):
        vote = row.get(axis) or {}
        if vote.get("status") != "agreed" or vote.get("value") != "complete":
            reasons.append(f"{axis}_not_complete")
    if row.get("gate_status") in {
        "abstain",
        "invalid_or_missing_passes",
        "provisional_nonindependent",
    } or row.get("independence_warnings"):
        reasons.append("independent_consensus_not_established")
    if reasons:
        return result

    claims = {c["consensus_claim_id"]: c for c in row.get("agreed_claims", [])}
    outcomes = {c["consensus_claim_id"]: c for c in row.get("outcomes", [])}
    checked = [
        {**outcomes.get(cid, {}), "claim_id": cid,
         "kind": c.get("mathematical_core", {}).get("kind"),
         **{axis: _value(c, axis) for axis in ("claim_status", "answer_role", "specificity", "claimed_target")}}
        for cid, c in claims.items()
    ]
    return project_checked_claims(checked, unresolved=int(row.get("scoring_unresolved_count", 0)) > 0,
                                  fruit_guarded=fruit_guarded)


ROOT_TARGET = "root_only_termination"
CONTEXTUAL_TARGET = "full_contextual_sn"
_CONTEXT_REFUTATION_MARKERS = ("monotonicity", "context_closure", "contextual")


def _contains_inner_position(value: Any) -> bool:
    if isinstance(value, dict):
        position = value.get("position")
        if isinstance(position, list) and position:
            return True
        return any(_contains_inner_position(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_inner_position(item) for item in value)
    return False


def refutation_needs_context(outcome: dict[str, Any]) -> bool:
    """True when a refutation relies on rewriting inside a context.

    Such a counterexample refutes a contextual claim; the literal root-step
    relation never rewrites below the root, so it does not transfer there.
    """

    detail = str(outcome.get("detail") or "")
    certificate = outcome.get("certificate") or {}
    reason = str((certificate.get("decision") or {}).get("reason") or "")
    if any(marker in detail or marker in reason for marker in _CONTEXT_REFUTATION_MARKERS):
        return True
    return _contains_inner_position(certificate)


def project_checked_claims(checked: list[dict[str, Any]], *, unresolved: bool = False,
                           fruit_guarded: bool = False,
                           target: str = CONTEXTUAL_TARGET) -> dict[str, Any]:
    """Apply the same response policy to checks, without asserting reader consensus.

    ``target`` names the proof target scored: the historical contextual
    target or the literal root-step relation. Each target keeps its own column.
    """
    if target not in {CONTEXTUAL_TARGET, ROOT_TARGET}:
        raise ValueError(f"unsupported proof target: {target}")
    result = {"policy_version": POLICY_VERSION, "method_mathematical_validity": "Unknown",
              "method_correct_and_admissible": "Unknown", "reasons": []}
    if target == ROOT_TARGET:
        result["proof_target"] = target
    reasons = result["reasons"]
    working, broken, insufficient, source_gaps, unknown, outside, boundary_unknown = [], [], [], [], [], [], []
    categories: list[str] = []
    offered = []
    # Retained offers aimed at the scored contextual target. A passing proof
    # whose own stated target is root-only termination is a correct claim at
    # that scope; it satisfies the contextual target only beside such an offer.
    contextual_offers = {
        outcome["claim_id"]
        for outcome in checked
        if outcome.get("claim_status") == "claimed_valid"
        and outcome.get("answer_role") in OFFER_ROLES
        and outcome.get("claimed_target") == "full_contextual_sn"
    }
    for outcome in checked:
        cid = outcome["claim_id"]
        status = outcome.get("claim_status")
        role = outcome.get("answer_role")
        if status in {None, "unclear"}:
            unknown.append(cid)
            categories.append("P")
            continue
        if status != "claimed_valid":
            if role == "failed_contrast":
                assessment = outcome.get("retained_rejection_assessment")
                if assessment == "PASS":
                    categories.append("X")
                elif assessment == "REFUTED":
                    broken.append(cid)
                    categories.append("F")
                else:
                    unknown.append(cid)
                    categories.append("P")
            continue
        if role not in OFFER_ROLES:
            if role is None or role == "unclear":
                unknown.append(cid)
                categories.append("P")
            continue
        offered.append(cid)
        kind = outcome.get("kind")
        boundary = outcome.get("boundary_verdict")
        certificate = outcome.get("certificate") or {}
        if (role == "supporting" and outcome.get("claimed_target") == "local_descent"
                and kind == "additive_measure"
                and certificate.get("certificate_type") == "scoped-proof-obligation/v1"
                and certificate.get("supported_targets_basis") == "node_count_descent_on_selected_rules"
                and certificate.get("decision", {}).get("context_scope") == "selected_rules_only"):
            boundary = "inside"
        if boundary == "outside" or kind in EXTERNAL_KINDS:
            outside.append(cid)
        elif boundary != "inside":
            boundary_unknown.append(cid)
        verdict = outcome.get("verdict")
        specificity = outcome.get("specificity")
        spec = outcome.get("source_specification") or {}
        missing = (spec.get("status") == "missing_definition"
                   and spec.get("basis") == "source_transcription_not_mathematical_certificate")
        ambiguous_source = (
            spec.get("status") == "ambiguous"
            and spec.get("basis") == "source_transcription_not_mathematical_certificate"
        )
        explicit_strict_category = outcome.get("strict_category")
        if explicit_strict_category == "N":
            insufficient.append(cid)
            categories.append("N")
            reasons.append(
                "established_source_insufficiency:"
                + cid
                + ":"
                + str(outcome.get("detail") or "unspecified")
            )
            continue
        if missing and role == "supporting":
            # A supporting remark with an incomplete definition does not by
            # itself show that the offered proof lacks a premise; the offered
            # construction still needs its own check.
            unknown.append(cid)
            categories.append("P")
            reasons.append("supporting_claim_source_specification_incomplete:" + cid)
            continue
        if missing or ambiguous_source:
            insufficient.append(cid)
            if missing:
                source_gaps.append(cid)
            else:
                reasons.append("ambiguous_source_specification:" + cid)
            categories.append("N")
            continue
        if verdict == "REFUTED" and target == ROOT_TARGET and refutation_needs_context(outcome):
            unknown.append(cid)
            categories.append("P")
            if boundary == "outside" or kind in EXTERNAL_KINDS:
                categories.append("E")
            reasons.append("contextual_refutation_not_transported_to_root_target:" + cid)
        elif verdict == "REFUTED":
            if fruit_guarded and not _fruit_refutation_applies(outcome):
                unknown.append(cid)
                categories.append("P")
                if boundary == "outside" or kind in EXTERNAL_KINDS:
                    categories.append("E")
                reasons.append(f"guarded_refutation_not_replayed:{cid}")
            else:
                broken.append(cid)
                categories.append("F")
        elif (
            verdict == "PASS"
            and outcome.get("claimed_target") == "root_only_termination"
            and "root_only_termination" in (certificate.get("supported_targets") or [])
            and not missing
        ):
            if target == ROOT_TARGET or contextual_offers - {cid}:
                working.append(cid)
                categories.append("E" if boundary == "outside" or kind in EXTERNAL_KINDS else "I")
                reasons.append("root_only_claim_checked_at_stated_scope:" + cid)
            else:
                insufficient.append(cid)
                categories.append("N")
                reasons.append("root_only_target_mismatch:" + cid)
        elif verdict == "PASS" and target == ROOT_TARGET:
            supported = certificate.get("supported_targets") or []
            # Termination under every context implies termination of the
            # root-step relation it contains (matrix B10).
            root_supported = ROOT_TARGET in supported or CONTEXTUAL_TARGET in supported
            if role in WITNESS_ROLES and root_supported and not missing:
                working.append(cid)
                categories.append("E" if boundary == "outside" or kind in EXTERNAL_KINDS else "I")
            elif outcome.get("benchmark_adequacy") == "unknown" and not supported:
                unknown.append(cid)
                categories.append("P")
                if boundary == "outside" or kind in EXTERNAL_KINDS:
                    categories.append("E")
            elif role in WITNESS_ROLES or (
                role == "supporting" and outcome.get("claimed_target") != "local_descent"
            ):
                insufficient.append(cid)
                categories.append("N")
            else:
                categories.append("X")
        elif verdict == "PASS":
            if role in WITNESS_ROLES and outcome.get("benchmark_adequacy") == "met" and not missing:
                working.append(cid)
                if boundary == "outside" or kind in EXTERNAL_KINDS:
                    categories.append("E")
                else:
                    categories.append("I")
            elif outcome.get("benchmark_adequacy") == "unknown":
                unknown.append(cid)
                categories.append("P")
                if boundary == "outside" or kind in EXTERNAL_KINDS:
                    categories.append("E")
            elif role in WITNESS_ROLES or (
                role == "supporting" and outcome.get("claimed_target") != "local_descent"
            ):
                insufficient.append(cid)
                categories.append("N")
            else:
                categories.append("X")
        elif verdict == "NO_CONCRETE_WITNESS" and specificity == "family_only":
            insufficient.append(cid)
            categories.append("N")
        else:
            unknown.append(cid)
            categories.append("P")
            if boundary == "outside" or kind in EXTERNAL_KINDS:
                categories.append("E")

    if unresolved:
        categories.append("P")
    decision = decide_strict_response(
        categories,
        boundary_pending=bool(boundary_unknown),
        source_identity_trusted=not unresolved,
    )
    result["method_mathematical_validity"] = decision.mathematical_validity
    result["method_correct_and_admissible"] = decision.boundary_compliance
    reasons.append("strict_rule:" + decision.rule)
    if broken:
        reasons.append("endorsed_refutation:" + ",".join(broken))
    if insufficient:
        reasons.append("insufficient_retained_solution:" + ",".join(insufficient))
    if source_gaps:
        reasons.append("insufficient_source_specification:" + ",".join(source_gaps))
    if unknown:
        reasons.append("unchecked_or_disputed_offer:" + ",".join(unknown))
    if working:
        reasons.append("full_contextual_witness:" + ",".join(working))
    if outside:
        reasons.append("offered_external_or_inadequate_route:" + ",".join(outside))
    return result
