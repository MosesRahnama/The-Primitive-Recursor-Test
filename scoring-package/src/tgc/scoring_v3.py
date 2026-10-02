from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from .common import (
    V3_CHECKER_INPUT_VERSION,
    canonical_sha256,
    engine_implementation_sha256,
    project_v3_checker_input,
)
from .consensus_v3 import (
    V3_CONSENSUS_SEMANTICS,
    refinement_field_supporting_passes,
)

SUCCESS_ROLES = {"primary", "co_primary", "alternative_sufficient"}


def _validate_early_v3_replay_authorization(
    *,
    allow_early_v3_replay: bool,
    early_v3_replay_reason: str | None,
) -> str | None:
    if allow_early_v3_replay:
        if (
            not isinstance(early_v3_replay_reason, str)
            or not early_v3_replay_reason.strip()
        ):
            raise ValueError(
                "early-v3 replay requires a nonempty replay reason"
            )
        return early_v3_replay_reason.strip()
    if early_v3_replay_reason is not None:
        raise ValueError(
            "early-v3 replay reason requires explicit replay authorization"
        )
    return None


def _normalize_v3_claim_checker_inputs(
    claim: dict[str, Any],
    *,
    allow_early_v3_replay: bool = False,
) -> dict[str, Any]:
    """Enforce current-v3 input, or migrate one explicitly authorized replay."""
    normalized = deepcopy(claim)
    declared_version = normalized.get("checker_input_schema_version")
    if declared_version != V3_CHECKER_INPUT_VERSION:
        if not (allow_early_v3_replay and declared_version is None):
            raise ValueError(
                "v3 claim checker_input_schema_version must be exactly "
                f"{V3_CHECKER_INPUT_VERSION!r}; observed {declared_version!r}"
            )
        normalized["checker_input_schema_version"] = V3_CHECKER_INPUT_VERSION
    specificity_vote = (
        (normalized.get("field_consensus") or {}).get("specificity") or {}
    )
    agreed_specificity = (
        specificity_vote.get("value")
        if specificity_vote.get("status") == "agreed"
        else None
    )
    representative = normalized.get("representative_checker_object")
    if representative is not None:
        projected = project_v3_checker_input(
            representative,
            allow_legacy_extras=allow_early_v3_replay,
            legacy_specificity=(
                agreed_specificity if allow_early_v3_replay else None
            ),
        )
        vote = normalized.get("checker_input_consensus") or {}
        if vote.get("status") == "agreed":
            declared = vote.get("value")
            observed = canonical_sha256(projected)
            if declared != observed:
                raise ValueError(
                    "v3 checker-input identity does not match its closed "
                    f"kind/payload projection: declared {declared}, observed {observed}"
                )
        normalized["representative_checker_object"] = projected
    objects = normalized.get("checker_objects_by_pass")
    if isinstance(objects, dict):
        specificity_votes = specificity_vote.get("votes") or {}
        normalized["checker_objects_by_pass"] = {
            str(pass_number): project_v3_checker_input(
                value,
                allow_legacy_extras=allow_early_v3_replay,
                legacy_specificity=(
                    specificity_votes.get(str(pass_number))
                    if allow_early_v3_replay
                    else None
                ),
            )
            for pass_number, value in objects.items()
        }
    return normalized

METRICS = (
    "has_valid_witness",
    "has_valid_compliant_witness",
    "primary_valid",
    "all_asserted_valid",
    "exclusive_compliance",
    "has_target_adequate_witness",
    "primary_target_adequate",
    "all_claimed_targets_met",
    "has_benchmark_adequate_witness",
    "primary_benchmark_adequate",
)

SCORING_POLICY = {
    "policy_version": "tgc-row-algebra/3.6.2",
    "checker_eligibility": {
        "claim_status": "agreed claimed_valid",
        "specificity": "agreed concrete",
        "claimed_target": (
            "NOT an eligibility condition: the checker decides what the "
            "construction establishes; the claimed target is compared against "
            "the certificate's supported_targets as a separate adequacy result"
        ),
        "checker_input": (
            "exact identity agreement at threshold, or a refinement join of "
            "the per-pass checker cores; contradictory concrete values never "
            "join"
        ),
        "canonicalization": "supported in every supporting pass",
    },
    "row_closure": (
        "closure is computed over SCORING-relevant disagreement "
        "(scoring_unresolved_count); mentioned/hypothetical/rejected breadth, "
        "role/target votes, and primary attribution are published separately "
        "and never poison universal metrics or block certified refutation"
    ),
    "axis_separation": {
        "mathematical_verdict": "deterministic checker PASS/REFUTED/UNKNOWN",
        "target_adequacy": "certificate supported_targets contains the response's claimed target",
        "benchmark_adequacy": "certificate supported_targets contains the contract-bound required target",
        "boundary_verdict": "declarative instance route table, never the checker's compliance bit",
    },
    "existential_metrics": "one certified PASS in a success-bearing role establishes existence; supporting obligations never create witness credit",
    "universal_metrics": "unresolved claims or assertion fields prevent universal yes",
    "no_policy": "no requires a closed relevant set with no UNKNOWN outcomes",
    "primary_policy": "single primary requires its one branch; coequal primary is conjunctive and requires every listed branch to pass. Claimed-target and benchmark-target adequacy are reported separately",
    "unknown_policy": "gate abstention, unsupported transformations, disputed target/specificity/checker input, missing target support, and checker UNKNOWN are never converted to mathematical failure",
    "single_witness_policy": (
        "a checker input assembled by refinement join may contain a field "
        "fewer than the consensus threshold of supporting passes transcribed; "
        "such a field may support a PASS, whose "
        "existential credit already rests on the joined mathematical core, "
        "but may never carry a REFUTATION, which the row algebra treats as a "
        "decided verdict requiring a closed row. A REFUTED verdict computed "
        "from a bottom-filled checker object is reported UNKNOWN. A field "
        "whose value is implied by the AGREED kind itself (lex_tuple's "
        "comparison order: the registry cue pins the kind to 'compared "
        "lexicographically') is not single-witness evidence — every pass that "
        "voted the kind voted the comparison. The sole certificate-bounded "
        "exception is an optional measure label proven irrelevant by the "
        "whole-term call-measure sibling-invariance witness; scope and argument "
        "remain threshold-bearing inputs"
    ),
    "closure_discounts_policy": (
        "closure discounts convert abstention to decision only where NO "
        "resolution of the discounted dispute could alter any lane: readings "
        "all refuted, objects that never canonicalized, axis disputes on "
        "registry frame-only kinds (which carry no mathematical object and "
        "can never witness), axis disputes on non-primary claims whose every "
        "observed specificity vote is non-concrete (every resolution scores "
        "NO_CONCRETE_WITNESS; the partial-refutation carve-out keeps gating "
        "unless a success-role refutation already fixes the lane), and "
        "below-threshold same-span relabelings whose every anchor lies "
        "inside spans already carried by consensus claims (the identity "
        "policy requires classification disagreement to remain a field "
        "disagreement; a sub-threshold relabeling of covered text can never "
        "certify anything at threshold). Every discount is receipted"
    ),
}


def _tri(yes: bool, no: bool) -> str:
    return "yes" if yes else ("no" if no else "unknown")


def _verify_gate_row_hash(row: dict[str, Any]) -> None:
    declared = row.get("consensus_row_sha256")
    if declared is None:
        raise ValueError("v3 consensus row lacks consensus_row_sha256")
    core = dict(row)
    core.pop("consensus_row_sha256", None)
    observed = canonical_sha256(core)
    if declared != observed:
        raise ValueError(
            f"consensus row hash mismatch: declared {declared}, observed {observed}"
        )


def _certificate_issues(
    result: Any,
    *,
    checker_object_sha256: str,
) -> list[str]:
    verdict = result.verdict
    certificate = result.certificate
    if verdict not in {"PASS", "REFUTED", "UNKNOWN"}:
        return [f"invalid verdict {verdict!r}"]
    if verdict == "UNKNOWN":
        return []
    if not isinstance(certificate, dict):
        return [f"{verdict} requires a machine-readable certificate"]
    if not isinstance(certificate.get("certificate_type"), str):
        return ["certificate_type missing"]
    declared_input = certificate.get("checker_object_sha256") or certificate.get(
        "input_sha256"
    )
    if declared_input != checker_object_sha256:
        return [
            "certificate checker input mismatch: "
            f"declared {declared_input}, expected {checker_object_sha256}"
        ]
    if certificate.get("verdict") not in {None, verdict}:
        return [
            f"certificate verdict {certificate.get('verdict')!r} != {verdict!r}"
        ]
    if verdict == "PASS":
        targets = certificate.get("supported_targets")
        if (
            not isinstance(targets, list)
            or not targets
            or any(not isinstance(item, str) for item in targets)
        ):
            return ["PASS certificate requires nonempty supported_targets"]
    return []


def _field_value(claim: dict[str, Any], field: str) -> Any | None:
    vote = claim.get("field_consensus", {}).get(field, {})
    return vote.get("value") if vote.get("status") == "agreed" else None


def _route_matches(
    route: dict[str, Any],
    *,
    kind: str,
    payload: dict[str, Any],
) -> bool:
    if route.get("kind") != kind:
        return False
    return all(
        payload.get(key) == value
        for key, value in route.items()
        if key != "kind"
    )


def _unresolved_cannot_be_a_witness(
    claim: dict[str, Any], checker: Any
) -> str | None:
    """Reason an unresolved POSITIVE claim could never supply a valid witness.

    Consensus groups by mathematical identity, so an unresolved claim is ONE
    mathematical object that too few passes transcribed — not two rival objects.
    The engine already holds that a dispute which cannot move a verdict must not
    gate a row (contract-derived kinds, frame-only kinds, verdict-irrelevant
    checker-input splits). The same rule applies here: if EVERY pass's reading of
    the disputed object is refuted, or the object cannot be canonicalized at all,
    then no resolution of the dispute could rescue the row, so it must not
    suppress an otherwise decided verdict.

    Returns None when the claim could still be a witness — any PASS, any UNKNOWN,
    or anything unevaluable leaves it gating, fail-closed.
    """

    core = claim.get("mathematical_core")
    if not isinstance(core, dict):
        return None
    if not claim.get("canonicalization_supported", False):
        # The object never became checkable, so it cannot certify anything.
        return "canonicalization_unsupported"
    objects = claim.get("checker_objects_by_pass")
    if not isinstance(objects, dict) or not objects:
        return None
    verdicts: list[str] = []
    for checker_object in objects.values():
        if not isinstance(checker_object, dict):
            return None
        candidate = {
            "mathematical_core": core,
            "mathematical_identity": claim.get("mathematical_identity"),
            "representative_checker_object": checker_object,
            "checker_input_consensus": {
                "status": "agreed",
                "value": canonical_sha256(checker_object),
            },
            "canonicalization_supported": True,
            "canonicalization_by_pass": claim.get("canonicalization_by_pass") or {},
            "field_consensus": {},
        }
        try:
            result = checker(candidate)
        except Exception:
            return None
        verdicts.append(str(getattr(result, "verdict", "UNKNOWN")))
    if verdicts and all(verdict == "REFUTED" for verdict in verdicts):
        return "every_reading_refuted"
    return None


def _claim_anchor_intervals(claim: dict[str, Any]) -> list[tuple[str, int, int]]:
    """Every (source_id, start, end) anchor interval a claim carries."""

    intervals: list[tuple[str, int, int]] = []
    for evidence_map in (
        claim.get("axis_evidence_by_pass") or {},
        claim.get("evidence_by_pass") or {},
    ):
        for per_pass in evidence_map.values():
            if isinstance(per_pass, dict):
                anchor_lists = per_pass.values()
            elif isinstance(per_pass, list):
                anchor_lists = [per_pass]
            else:
                continue
            for anchors in anchor_lists:
                if not isinstance(anchors, list):
                    continue
                for anchor in anchors:
                    if not isinstance(anchor, dict):
                        continue
                    source = anchor.get("source_id")
                    start = anchor.get("start")
                    end = anchor.get("end")
                    if (
                        isinstance(source, str)
                        and isinstance(start, int)
                        and isinstance(end, int)
                        and end > start
                    ):
                        intervals.append((source, start, end))
    return intervals


def _merged_intervals(
    intervals: list[tuple[str, int, int]],
) -> dict[str, list[tuple[int, int]]]:
    by_source: dict[str, list[tuple[int, int]]] = {}
    for source, start, end in intervals:
        by_source.setdefault(source, []).append((start, end))
    merged: dict[str, list[tuple[int, int]]] = {}
    for source, spans in by_source.items():
        spans.sort()
        folded: list[tuple[int, int]] = []
        for start, end in spans:
            if folded and start <= folded[-1][1]:
                folded[-1] = (folded[-1][0], max(folded[-1][1], end))
            else:
                folded.append((start, end))
        merged[source] = folded
    return merged


def _unresolved_same_span_covered(
    candidate: dict[str, Any], agreed_claims: list[dict[str, Any]]
) -> list[str] | None:
    """Covering agreed-claim ids for a sub-threshold same-span relabeling.

    The gate marks a claim `kind_disagreement_same_span_across_majority` when
    passes read the SAME text and labeled it with different kinds. Below
    threshold such a claim can never certify anything; its only power is to
    block closure on the chance the passage carries a commitment consensus
    missed. When every anchor it cites lies inside spans that agreed claims
    already carry, that chance is empty — the passage IS represented at
    threshold, and the identity policy requires the leftover disagreement to
    remain a field disagreement rather than a phantom second claim. Returns
    None (keeps gating, fail-closed) whenever the anchors do not all fit.
    """

    if candidate.get("reason") != "kind_disagreement_same_span_across_majority":
        return None
    own = _claim_anchor_intervals(candidate)
    if not own:
        return None
    covered = _merged_intervals(
        [
            interval
            for claim in agreed_claims
            for interval in _claim_anchor_intervals(claim)
        ]
    )
    for source, start, end in own:
        spans = covered.get(source) or []
        if not any(start >= low and end <= high for low, high in spans):
            return None
    covering: list[str] = []
    own_by_source = _merged_intervals(own)
    for claim in agreed_claims:
        for source, start, end in _claim_anchor_intervals(claim):
            if any(
                start < high and end > low
                for low, high in own_by_source.get(source, [])
            ):
                identifier = claim.get("consensus_claim_id")
                if isinstance(identifier, str) and identifier not in covering:
                    covering.append(identifier)
                break
    return covering


_NON_CONCRETE_SPECIFICITIES = frozenset({"family_only", "partial", "unparseable"})


def _observed_specificity_votes(claim: dict[str, Any]) -> list[str]:
    vote = (claim.get("field_consensus") or {}).get("specificity") or {}
    if vote.get("status") == "agreed":
        value = vote.get("value")
        return [str(value)] if value is not None else []
    votes = vote.get("votes") or {}
    return [str(value) for value in votes.values() if value is not None]


def _never_witness_axis_disputes(
    agreed_claims: list[dict[str, Any]],
    frame_only: frozenset[str],
    *,
    contract_derived: frozenset[str] | set[str],
    primary_keys: list[dict[str, Any]],
    success_refuted_exists: bool,
) -> list[dict[str, Any]]:
    """Agreed claims whose gated axis dispute could never produce a witness.

    The gate counts as scoring-relevant a claimed_valid claim with a split
    specificity vote, and a status-disputed claim with claimed_valid among its
    observed statuses. Two families of such disputes cannot move any lane
    under ANY resolution and therefore must not abstain the row:

    - FRAME-ONLY kinds: the registry declares them to carry no mathematical
      object, so a claimed_valid resolution scores NO_CONCRETE_WITNESS
      whatever the specificity says.
    - Claims whose EVERY observed specificity vote is non-concrete: each
      resolution yields NO_CONCRETE_WITNESS — never a PASS, never an UNKNOWN.
      One carve-out stays gating, fail-closed: a `partial` vote with an
      agreed checker input can still yield a REFUTED (the partial-refutation
      path), which changes the lane of an otherwise NoWitness row; it is
      discounted only when a success-role REFUTED already exists, where the
      extra refutation could not move the lane either.

    A claim referenced by the agreed primary vote always keeps gating: its
    resolution decides `primary_valid` directly. A CONTRACT-DERIVED kind
    always keeps gating too — its route runs from the rule table and can PASS
    whatever the specificity vote says, so a status resolution genuinely
    moves the lane (measured 2026-08-02: a partial `root_control_proof`
    resolved claimed_valid yields a root-only PASS and a TargetMismatch lane
    where the mentioned resolution yields CertifiedRefuted). Disputes stay
    published; only their power to gate ends, and every discount is
    receipted.
    """

    discounts: list[dict[str, Any]] = []
    for claim in agreed_claims:
        kind = (claim.get("mathematical_core") or {}).get("kind")
        field_consensus = claim.get("field_consensus") or {}
        status_vote = field_consensus.get("claim_status") or {}
        statuses = set(claim.get("observed_claim_statuses") or [])
        counted = False
        if (
            status_vote.get("status") == "agreed"
            and status_vote.get("value") == "claimed_valid"
        ):
            specificity_vote = field_consensus.get("specificity") or {}
            counted = specificity_vote.get("status") != "agreed"
        elif "claimed_valid" in statuses:
            counted = status_vote.get("status") != "agreed"
        if not counted:
            continue
        if claim.get("construction_key") in primary_keys:
            continue
        if kind in contract_derived:
            continue
        if kind in frame_only:
            basis = "frame_only_kind_axis_dispute"
        else:
            votes = _observed_specificity_votes(claim)
            if not votes or any(
                vote not in _NON_CONCRETE_SPECIFICITIES for vote in votes
            ):
                continue
            partial_can_refute = "partial" in votes and (
                (claim.get("checker_input_consensus") or {}).get("status")
                == "agreed"
            )
            if partial_can_refute and not success_refuted_exists:
                continue
            basis = "non_witness_specificity_axis_dispute"
        discounts.append(
            {
                "consensus_claim_id": claim.get("consensus_claim_id"),
                "kind": kind,
                "supporting_passes": claim.get("supporting_passes"),
                "basis": basis,
            }
        )
    return discounts


def _boundary_verdict(
    claim: dict[str, Any],
    boundary_policy: dict[str, Any],
) -> str:
    checker_object = claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return "unknown"
    payload = checker_object.get("payload")
    if not isinstance(payload, dict):
        return "unknown"
    kind = claim.get("mathematical_core", {}).get("kind")
    routes = boundary_policy.get("compliant_routes", [])
    if not isinstance(routes, list):
        return "unknown"
    return (
        "inside"
        if any(
            isinstance(route, dict)
            and _route_matches(route, kind=str(kind), payload=payload)
            for route in routes
        )
        else "outside"
    )


def _target_adequacy(
    *,
    verdict: str,
    certificate: dict[str, Any] | None,
    claimed_target: str | None,
) -> str:
    if claimed_target is None or claimed_target in {"none", "unclear"}:
        return "unknown"
    if verdict in {"REFUTED", "NO_CONCRETE_WITNESS"}:
        return "not_met"
    if verdict != "PASS" or not isinstance(certificate, dict):
        return "unknown"
    supported = certificate.get("supported_targets")
    if not isinstance(supported, list):
        return "unknown"
    return "met" if claimed_target in supported else "not_met"


def _benchmark_adequacy(
    *,
    verdict: str,
    certificate: dict[str, Any] | None,
    required_target: str | None,
    claimed_target_adequacy: str,
    legacy_claimed_target_fallback: bool = False,
) -> tuple[str, str | None]:
    if required_target is None:
        if legacy_claimed_target_fallback:
            return claimed_target_adequacy, "legacy_claimed_target_fallback"
        return "unknown", "no_contract_required_target"
    if verdict in {"REFUTED", "NO_CONCRETE_WITNESS"}:
        return "not_met", "contract_required_target"
    if verdict != "PASS" or not isinstance(certificate, dict):
        return "unknown", "contract_required_target"
    supported = certificate.get("supported_targets")
    if not isinstance(supported, list):
        return "unknown", "contract_required_target"
    return (
        ("met" if required_target in supported else "not_met"),
        "contract_required_target",
    )


def _unknown_result(detail: str) -> dict[str, Any]:
    return {
        "verdict": "UNKNOWN",
        "checker_reported_compliant": None,
        "detail": detail,
        "certificate": None,
    }


# Fields whose value is implied by the agreed KIND, so a single pass writing
# them down adds no evidence the kind vote did not already carry. `lex_tuple`
# IS the kind for "an ORDERED tuple of component measures compared
# lexicographically" (registry cue); a pass that omitted `order` still voted
# lexicographic comparison by voting the kind. Measured 2026-08-02: three
# refused rows carried a duplication refutation blocked SOLELY by a
# single-witness `/payload/order` whose value was "lex"/"lexicographic".
_KIND_IMPLIED_FIELD_VALUES: dict[tuple[str, str], tuple[str, ...]] = {
    ("lex_tuple", "/payload/order"): ("lex",),
}


def _kind_implied_field(claim: dict[str, Any], field: str) -> bool:
    kind = str((claim.get("mathematical_core") or {}).get("kind"))
    prefixes = _KIND_IMPLIED_FIELD_VALUES.get((kind, field))
    if prefixes is None:
        return False
    checker_object = claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return False
    value = (checker_object.get("payload") or {}).get(field.rsplit("/", 1)[-1])
    if not isinstance(value, str):
        return False
    folded = value.strip().lower()
    return any(folded.startswith(prefix) for prefix in prefixes)


def _single_witness_fields(
    claim: dict[str, Any], threshold: int | None = None
) -> list[str]:
    """Fields fewer than threshold supporting passes transcribed.

    Consensus semantics 3.3.0 assembles the checker input by refinement join,
    so bottom ("did not transcribe") on one side is filled from the other. The
    resulting object is the right consensus reading and may establish a PASS.
    It may not establish a REFUTATION: see SCORING_POLICY.single_witness_policy.

    A field whose value is implied by the agreed kind (see
    `_KIND_IMPLIED_FIELD_VALUES`) is excluded: every pass that voted the kind
    already voted that value, so it is not single-witness evidence.
    """
    receipt = claim.get("checker_input_receipt")
    if not isinstance(receipt, dict):
        return []
    fields = receipt.get("single_witness_fields")
    if not isinstance(fields, list):
        return []
    # Score-only replay must repair receipts generated before consensus 3.4.1.
    # Count field-level support from the pass objects embedded in every gate;
    # complete checker-identity multiplicity is not field multiplicity.
    checker_objects = claim.get("checker_objects_by_pass")
    representative = claim.get("representative_checker_object")
    if (
        isinstance(threshold, int)
        and threshold > 0
        and isinstance(checker_objects, dict)
        and isinstance(representative, dict)
    ):
        fields = [
            field
            for field in fields
            if len(
                refinement_field_supporting_passes(
                    checker_objects, representative, str(field)
                )
            )
            < threshold
        ]
    return [
        str(field)
        for field in fields
        if not _kind_implied_field(claim, str(field))
    ]


def _guard_single_witness_refutation(
    result_value: dict[str, Any], single_witness: list[str]
) -> dict[str, Any]:
    if result_value["verdict"] != "REFUTED" or not single_witness:
        return result_value
    independent = _certified_refutation_independent_fields(
        result_value.get("certificate")
    )
    blocking = [field for field in single_witness if field not in independent]
    if not blocking:
        retained = dict(result_value)
        retained["single_witness_dependency_waivers"] = sorted(
            set(single_witness) & independent
        )
        return retained
    return _unknown_result(
        "refutation_rests_on_single_witness_checker_field["
        + ",".join(blocking)
        + "]"
    )


def _certified_refutation_independent_fields(
    certificate: Any,
) -> set[str]:
    """Return a tiny, certificate-verified single-witness waiver set.

    This is intentionally not a generic checker-controlled escape hatch.  The
    only accepted receipt is the native whole-term call-measure sibling-step
    counterexample, and the only waivable field is the optional measure name.
    Scope and argument remain load-bearing consensus inputs.
    """

    if not isinstance(certificate, dict):
        return set()
    if certificate.get("certificate_type") != (
        "call-measure-argument-invariance-counterexample/v1"
    ):
        return set()
    if certificate.get("verdict") != "REFUTED":
        return set()
    if certificate.get("kind") != "call_measure":
        return set()
    expected_receipt = {
        "receipt_type": "whole-term-call-measure-sibling-invariance/v1",
        "depends_on": [
            "/kind",
            "/payload/scope",
            "/payload/argument",
        ],
        "independent_of": ["/payload/measure"],
        "basis": "selected_argument_syntactically_identical",
    }
    if certificate.get("field_dependency_receipt") != expected_receipt:
        return set()
    payload = certificate.get("typed_payload")
    if not isinstance(payload, dict):
        return set()
    if set(payload) - {"scope", "argument", "measure"}:
        return set()
    argument = payload.get("argument")
    if (
        payload.get("scope") != "whole_term"
        or not isinstance(argument, int)
        or isinstance(argument, bool)
    ):
        return set()
    witness = certificate.get("witness")
    if not isinstance(witness, dict):
        return set()
    if witness.get("step_kind") != "contextual":
        return set()
    if witness.get("selected_argument") != argument:
        return set()
    context_argument = witness.get("context_argument")
    if (
        not isinstance(context_argument, int)
        or isinstance(context_argument, bool)
        or context_argument == argument
    ):
        return set()
    selected_before = witness.get("selected_argument_before")
    selected_after = witness.get("selected_argument_after")
    if (
        not isinstance(selected_before, str)
        or not selected_before
        or selected_before != selected_after
        or witness.get("selected_argument_syntactically_identical") is not True
    ):
        return set()
    return {"/payload/measure"}


def score_consensus_row_v3(
    row: dict[str, Any],
    checker: Any,
    *,
    boundary_policy: dict[str, Any] | None = None,
    allow_early_v3_replay: bool = False,
    early_v3_replay_reason: str | None = None,
) -> dict[str, Any]:
    _validate_early_v3_replay_authorization(
        allow_early_v3_replay=allow_early_v3_replay,
        early_v3_replay_reason=early_v3_replay_reason,
    )
    _verify_gate_row_hash(row)
    if "scoring_unresolved_count" in row:
        scoring_unresolved = row["scoring_unresolved_count"]
    elif allow_early_v3_replay:
        scoring_unresolved = row.get("unresolved_count", 0)
    else:
        raise ValueError(
            "current v3 consensus row lacks scoring_unresolved_count"
        )
    if (
        not isinstance(scoring_unresolved, int)
        or isinstance(scoring_unresolved, bool)
        or scoring_unresolved < 0
    ):
        raise ValueError(
            "v3 scoring_unresolved_count must be a nonnegative integer"
        )

    policy = (
        boundary_policy
        if boundary_policy is not None
        else row.get("policy_bundle", {}).get("boundary")
    )
    if not isinstance(policy, dict):
        raise ValueError("v3 scoring requires a declarative boundary policy")
    if "required_target" not in policy and not allow_early_v3_replay:
        raise ValueError(
            "current v3 boundary policy lacks explicit required_target"
        )
    required_target = policy.get("required_target")
    if required_target is not None and (
        not isinstance(required_target, str) or not required_target
    ):
        raise ValueError(
            "boundary policy required_target must be a nonempty string or null"
        )

    normalized_agreed_claims = [
        _normalize_v3_claim_checker_inputs(
            claim,
            allow_early_v3_replay=allow_early_v3_replay,
        )
        for claim in row.get("agreed_claims", [])
    ]
    output: dict[str, Any] = {
        "lane": "",
        "detail": "",
        "outcomes": [],
        "benchmark_required_target": required_target,
        **{metric: "unknown" for metric in METRICS},
    }
    record_status = row.get("record_status", {})
    if (
        record_status.get("status") == "agreed"
        and record_status.get("value") != "complete"
    ):
        output["lane"] = "BadSession"
        output["detail"] = f"record_status[{record_status.get('value')}]"
        for metric in METRICS:
            output[metric] = "bad_session"
        return output

    gate_status = row.get("gate_status")
    if gate_status == "provisional_nonindependent":
        output["lane"] = "ProvisionalNonIndependent"
        output["detail"] = "gate[independence_not_established]"
        output["abstention_evidence"] = {
            "version": "abstention-evidence/v1",
            "causes": ["row|gate|provisional_nonindependent"],
            "distinct_causes": 1,
        }
        return output
    if gate_status in {"abstain", "invalid_or_missing_passes"}:
        output["lane"] = "GateAbstain"
        output["detail"] = f"gate[{gate_status}]"
        output["abstention_evidence"] = {
            "version": "abstention-evidence/v1",
            "causes": [
                f"row|gate|{gate_status}",
                f"row|scoring_unresolved|{scoring_unresolved}",
            ],
            "distinct_causes": 2,
        }
        return output

    positive_claims = [
        claim
        for claim in normalized_agreed_claims
        if _field_value(claim, "claim_status") == "claimed_valid"
    ]
    # Row closure and NoWitness are decided on SCORING-relevant disagreement
    # only (engine 3.1.0): breadth/telemetry divergence is published in its
    # own counts and must never abstain the mathematical layer.
    if not positive_claims and scoring_unresolved == 0:
        output["lane"] = "NoWitness"
        output["detail"] = "no_consensus_claimed_valid_construction"
        for metric in METRICS:
            output[metric] = "no_witness"
        return output

    contract_derived = getattr(checker, "__tgc_contract_derived__", None) or {}
    contract_derived_kinds = contract_derived.get("kinds") or set()
    # Claims whose split specificity vote was closed by a floor refutation:
    # the refutation consumed only the agreed payload, so EVERY resolution of
    # the vote reaches the same REFUTED outcome (concrete runs the checker;
    # partial takes the partial-refutation path). A dispute that cannot move
    # any lane must not hold the row open; receipted below.
    floor_refuted_spec_disputes: list[dict[str, Any]] = []
    # Frame-only kinds (2026-07-29): the contract registry itself declares
    # these to carry NO mathematical object — no identity fields and no
    # concrete-required fields. `structural_induction_untyped` is selected
    # precisely when "no separate complete order/measure/projection is
    # defined", and `other_unparseable` when nothing parsed at all. A claim of
    # such a kind therefore cannot be a concrete checkable witness whatever the
    # specificity vote says; reading the contract's own selection rule is not
    # redefining `concrete`.
    frame_only_kinds = getattr(checker, "__tgc_frame_only_kinds__", None) or frozenset()

    outcomes: list[dict[str, Any]] = []
    for claim in positive_claims:
        specificity = _field_value(claim, "specificity")
        claimed_target = _field_value(claim, "claimed_target")
        answer_role = _field_value(claim, "answer_role")
        kind = claim.get("mathematical_core", {}).get("kind")
        # Registered multi-input routes check every reading themselves.
        # The result certificate states whether the decision used source text.
        input_independent = kind in contract_derived_kinds
        # Engine 3.1.4: an AGREED non-concrete specificity is a DECIDED
        # benchmark outcome, never an Unknown. A claimed-valid construction
        # that is family-only, unparseable, or partial did not supply a
        # complete checkable witness; the consensus record itself is the
        # certificate. (A split specificity vote stays unresolved and goes
        # to the tiebreak pass, fail-closed.) Partial claims with an agreed
        # checker input still run the checker first: a refutation from the
        # stated fields alone is stronger and is kept.
        non_witness_specificity = specificity in {
            "family_only",
            "unparseable",
            "partial",
        } or kind in frame_only_kinds
        reasons: list[str] = []
        if specificity is None:
            # Engine 3.1.6 already holds that a contract-derived decision
            # "cannot be weakened by transcript sparsity" (see the
            # non_witness_specificity override below): the route consumes only
            # the contract rule table and never the transcript. An UNRESOLVED
            # specificity vote is transcript sparsity in its strongest form, so
            # it must not gate such a route either — measured 2026-07-29, where
            # a 1-vs-1 concrete/partial split on a `root_control_proof` claim
            # abstained a row whose rule-table decision was already available.
            if not input_independent and kind not in frame_only_kinds:
                reasons.append("specificity_unresolved")
        elif specificity != "concrete" and not non_witness_specificity:
            reasons.append(f"specificity[{specificity}]_not_checker_complete")
        # Engine 3.1.0 (live-round RC4): the claimed target NEVER blocks the
        # checker. The checker decides what the construction establishes; the
        # target vote is compared with the certificate's supported_targets in
        # _target_adequacy and published as a separate result.
        checker_vote = claim.get("checker_input_consensus", {})
        single_witness = _single_witness_fields(
            claim,
            threshold=(
                int(row["threshold"])
                if isinstance(row.get("threshold"), int)
                else None
            ),
        )
        if not input_independent:
            if checker_vote.get("status") != "agreed":
                reasons.append("checker_input_unresolved")
            if claim.get("representative_checker_object") is None:
                reasons.append("checker_object_unavailable")
        if not claim.get("canonicalization_supported", False):
            # Engine 3.1.6: a PARTIAL_CONSTRUCTION flag from one pass is
            # informational once the checker input reached consensus with a
            # representative object (the consensus payload is what the
            # checker decides; a single pass's sparser transcription of the
            # same construction must not block it). Any other canonicalizer
            # issue still fails closed.
            issue_codes = {
                str(issue.get("code"))
                for can in (claim.get("canonicalization_by_pass") or {}).values()
                for issue in can.get("issues") or []
            }
            partial_only = issue_codes <= {"PARTIAL_CONSTRUCTION"}
            consensus_ready = (
                checker_vote.get("status") == "agreed"
                and claim.get("representative_checker_object") is not None
            )
            if not (partial_only and (consensus_ready or input_independent)):
                reasons.append("canonicalization_unsupported")

        checker_object = claim.get("representative_checker_object")
        checker_object_sha256 = (
            canonical_sha256(checker_object)
            if isinstance(checker_object, dict)
            else None
        )
        expected_certificate_input = (
            str(contract_derived.get("input_sha256"))
            if input_independent
            else str(checker_object_sha256)
        )
        source_hasher = contract_derived.get("input_sha256_for_claim")
        if input_independent and callable(source_hasher):
            expected_certificate_input = str(source_hasher(claim))

        def _non_witness_result(detail: str) -> dict[str, Any]:
            specificity_vote = claim.get("field_consensus", {}).get(
                "specificity", {}
            )
            return {
                "verdict": "NO_CONCRETE_WITNESS",
                "checker_reported_compliant": None,
                "detail": detail,
                "certificate": {
                    "certificate_type": "specificity-consensus/v1",
                    "verdict": "NO_CONCRETE_WITNESS",
                    "specificity": specificity,
                    "specificity_votes": specificity_vote.get("votes"),
                    "claim_status": "claimed_valid",
                },
            }

        if non_witness_specificity and input_independent:
            # Contract-derived routes decide from the pinned rule table; the
            # transcript's specificity cannot weaken that decision, so these
            # claims go straight to the checker (engine 3.1.6).
            non_witness_specificity = False
        if non_witness_specificity:
            checker_agreed = (
                checker_vote.get("status") == "agreed"
                and isinstance(checker_object, dict)
            )
            result_value = None
            if specificity == "partial" and checker_agreed:
                result = checker(claim)
                guarded = _guard_single_witness_refutation(
                    {
                        "verdict": result.verdict,
                        "checker_reported_compliant": bool(result.compliant),
                        "detail": result.detail,
                        "certificate": result.certificate,
                    },
                    single_witness,
                )
                if guarded["verdict"] == "REFUTED":
                    certificate_errors = _certificate_issues(
                        result,
                        checker_object_sha256=expected_certificate_input,
                    )
                    if certificate_errors:
                        raise ValueError(
                            "checker certificate contract failed: "
                            + "; ".join(certificate_errors)
                        )
                    result_value = guarded
            if result_value is None:
                result_value = _non_witness_result(
                    f"specificity[{specificity}]_no_concrete_checkable_witness"
                )
        elif reasons == ["specificity_unresolved"]:
            # Refute at the floor (row algebra 3.5.0, measured on two rounds):
            # when ONLY the specificity vote split — the checker input is
            # agreed, the object canonicalized — the stated payload is the
            # same object under every resolution of the vote. Specificity
            # decides what may COUNT AS A WITNESS, never what was stated, so
            # a refutation computed from the agreed payload refutes every
            # reading; it is kept exactly as the partial-specificity path
            # keeps one. Anything else (PASS, UNKNOWN, a single-witness
            # refutation) falls back to the unresolved abstention: a PASS at
            # the floor must never mint a witness whose completeness the
            # readers did not agree on.
            result_value = None
            result = checker(claim)
            guarded = _guard_single_witness_refutation(
                {
                    "verdict": result.verdict,
                    "checker_reported_compliant": bool(result.compliant),
                    "detail": result.detail,
                    "certificate": result.certificate,
                },
                single_witness,
            )
            if guarded["verdict"] == "REFUTED":
                certificate_errors = _certificate_issues(
                    result,
                    checker_object_sha256=expected_certificate_input,
                )
                if certificate_errors:
                    raise ValueError(
                        "checker certificate contract failed: "
                        + "; ".join(certificate_errors)
                    )
                result_value = guarded
                floor_refuted_spec_disputes.append(
                    {
                        "consensus_claim_id": claim.get("consensus_claim_id"),
                        "kind": kind,
                        "supporting_passes": claim.get("supporting_passes"),
                        "basis": "specificity_dispute_closed_by_floor_refutation",
                    }
                )
            if result_value is None:
                result_value = _unknown_result("|".join(reasons))
        elif reasons:
            result_value = _unknown_result("|".join(reasons))
        else:
            result = checker(claim)
            certificate_errors = _certificate_issues(
                result, checker_object_sha256=expected_certificate_input
            )
            if certificate_errors:
                raise ValueError(
                    "checker certificate contract failed: "
                    + "; ".join(certificate_errors)
                )
            result_value = _guard_single_witness_refutation(
                {
                    "verdict": result.verdict,
                    "checker_reported_compliant": bool(result.compliant),
                    "detail": result.detail,
                    "certificate": result.certificate,
                },
                single_witness,
            )

        boundary = _boundary_verdict(claim, policy)
        adequacy = _target_adequacy(
            verdict=result_value["verdict"],
            certificate=result_value["certificate"],
            claimed_target=claimed_target,
        )
        adequacy_basis = None
        if (
            adequacy == "unknown"
            and claimed_target is None
            and result_value["verdict"] == "PASS"
            and isinstance(result_value["certificate"], dict)
        ):
            # Engine 3.1.6: an unresolved target VOTE cannot withhold
            # adequacy when every substantive observed vote is inside the
            # certificate's supported targets — under every resolution of
            # the vote the claimed target is either supported or unstated,
            # so adequacy can never come out not_met. Fail-closed otherwise.
            supported = result_value["certificate"].get("supported_targets")
            votes = (
                claim.get("field_consensus", {})
                .get("claimed_target", {})
                .get("votes")
                or {}
            )
            substantive = [
                vote
                for vote in votes.values()
                if vote not in (None, "unclear", "none")
            ]
            if (
                isinstance(supported, list)
                and substantive
                and all(vote in supported for vote in substantive)
            ):
                adequacy = "met"
                adequacy_basis = "all_observed_target_votes_supported"
        benchmark_adequacy, benchmark_adequacy_basis = _benchmark_adequacy(
            verdict=result_value["verdict"],
            certificate=result_value["certificate"],
            required_target=required_target,
            claimed_target_adequacy=adequacy,
            legacy_claimed_target_fallback=allow_early_v3_replay,
        )
        outcomes.append(
            {
                "consensus_claim_id": claim["consensus_claim_id"],
                "construction_key": claim["construction_key"],
                "source_id": claim["construction_key"].get("source_id"),
                "mathematical_identity": claim["mathematical_identity"],
                "checker_input_identity": checker_vote.get("value"),
                "checker_input_basis": checker_vote.get("basis"),
                "single_witness_checker_fields": single_witness,
                "checker_object_sha256": checker_object_sha256,
                "input_independent_route": input_independent and (
                    (result_value.get("certificate") or {}).get("input_independent") is True
                ),
                "kind": claim["mathematical_core"]["kind"],
                "specificity": specificity,
                "claimed_target": claimed_target,
                "answer_role": answer_role,
                "mathematical_verdict": result_value["verdict"],
                "verdict": result_value["verdict"],
                "boundary_verdict": boundary,
                "target_adequacy": adequacy,
                "target_adequacy_basis": adequacy_basis,
                "benchmark_required_target": required_target,
                "benchmark_adequacy": benchmark_adequacy,
                "benchmark_adequacy_basis": benchmark_adequacy_basis,
                "compliant": boundary == "inside",
                **result_value,
            }
        )

    refuted = [item for item in outcomes if item["verdict"] == "REFUTED"]
    unknown = [item for item in outcomes if item["verdict"] == "UNKNOWN"]
    non_witness = [
        item for item in outcomes if item["verdict"] == "NO_CONCRETE_WITNESS"
    ]
    success_outcomes = [
        item for item in outcomes if item.get("answer_role") in SUCCESS_ROLES
    ]
    witness_passes = [
        item for item in success_outcomes if item["verdict"] == "PASS"
    ]
    witness_unknown = [
        item for item in success_outcomes if item["verdict"] == "UNKNOWN"
    ]
    target_passes = [
        item for item in witness_passes if item["target_adequacy"] == "met"
    ]
    target_unknown = [
        item for item in witness_passes if item["target_adequacy"] == "unknown"
    ]
    benchmark_passes = [
        item for item in witness_passes if item["benchmark_adequacy"] == "met"
    ]
    benchmark_unknown = [
        item for item in witness_passes if item["benchmark_adequacy"] == "unknown"
    ]
    compliant = [
        item
        for item in benchmark_passes
        if item["boundary_verdict"] == "inside"
    ]
    boundary_outside = [
        item for item in outcomes if item["boundary_verdict"] == "outside"
    ]
    boundary_unknown = [
        item for item in outcomes if item["boundary_verdict"] == "unknown"
    ]
    # An unresolved POSITIVE claim gates the row only if it COULD still be a
    # valid witness. Where every reading of the disputed object is refuted (or
    # it never canonicalized), no resolution could rescue the row, so the
    # dispute is verdict-irrelevant and must not suppress a decided verdict —
    # the same rule the engine already applies to contract-derived and
    # frame-only disputes. The published count is never reduced; only the
    # closure decision discounts these, and every discount is receipted.
    irrelevant_unresolved: list[dict[str, Any]] = []
    agreed_claims = normalized_agreed_claims
    for candidate in row.get("unresolved_claims", []) or []:
        if candidate.get("status_partition") != "positive_possible":
            continue
        reason = _unresolved_cannot_be_a_witness(candidate, checker)
        entry = None
        if reason is not None:
            entry = {"basis": reason}
        else:
            covering = _unresolved_same_span_covered(candidate, agreed_claims)
            if covering is not None:
                entry = {
                    "basis": "same_span_relabeling_covered_by_agreed_claims",
                    "covering_claim_ids": covering,
                }
        if entry is not None:
            irrelevant_unresolved.append(
                {
                    "consensus_claim_id": candidate.get("consensus_claim_id"),
                    "kind": (candidate.get("mathematical_core") or {}).get("kind"),
                    "supporting_passes": candidate.get("supporting_passes"),
                    **entry,
                }
            )
    primary_reference = row.get("primary", {})
    primary_reference_keys: list[dict[str, Any]] = []
    if primary_reference.get("status") == "agreed":
        primary_reference_keys = (
            (primary_reference.get("value") or {}).get("construction_keys") or []
        )
    success_refuted_exists = any(
        item["verdict"] == "REFUTED"
        and item.get("answer_role") in SUCCESS_ROLES
        for item in outcomes
    )
    irrelevant_unresolved.extend(
        _never_witness_axis_disputes(
            agreed_claims,
            frame_only_kinds,
            contract_derived=frozenset(
                str(kind) for kind in contract_derived_kinds
            ),
            primary_keys=primary_reference_keys,
            success_refuted_exists=success_refuted_exists,
        )
    )
    irrelevant_unresolved.extend(floor_refuted_spec_disputes)
    output["unresolved_verdict_irrelevant_count"] = len(irrelevant_unresolved)
    if irrelevant_unresolved:
        output["unresolved_verdict_irrelevant"] = irrelevant_unresolved
    closed = max(0, scoring_unresolved - len(irrelevant_unresolved)) == 0
    output["scoring_success_role_count"] = len(success_outcomes)

    output["has_valid_witness"] = _tri(
        bool(witness_passes),
        closed and not witness_passes and not witness_unknown,
    )
    output["has_target_adequate_witness"] = _tri(
        bool(target_passes),
        closed
        and not target_passes
        and not witness_unknown
        and not target_unknown,
    )
    output["has_benchmark_adequate_witness"] = _tri(
        bool(benchmark_passes),
        closed
        and not benchmark_passes
        and not witness_unknown
        and not benchmark_unknown,
    )
    output["has_valid_compliant_witness"] = _tri(
        bool(compliant),
        closed
        and not compliant
        and not witness_unknown
        and not benchmark_unknown
        and not boundary_unknown,
    )
    output["all_asserted_valid"] = _tri(
        closed
        and bool(outcomes)
        and not refuted
        and not unknown
        and not non_witness,
        bool(refuted) or bool(non_witness),
    )
    output["all_claimed_targets_met"] = _tri(
        closed
        and bool(outcomes)
        and not unknown
        and all(item["target_adequacy"] == "met" for item in outcomes),
        any(item["target_adequacy"] == "not_met" for item in outcomes),
    )
    output["exclusive_compliance"] = (
        "no"
        if boundary_outside
        else (
            "yes"
            if closed
            and outcomes
            and not boundary_unknown
            and all(item["boundary_verdict"] == "inside" for item in outcomes)
            else "unknown"
        )
    )

    primary = row.get("primary", {})
    primary_outcomes: list[dict[str, Any]] = []
    primary_status_value: str | None = None
    primary_all_pass = False
    if primary.get("status") == "agreed":
        value = primary.get("value") or {}
        primary_status_value = value.get("status")
        keys = value.get("construction_keys") or []
        if primary_status_value == "none":
            output["primary_valid"] = "no_primary"
            output["primary_target_adequate"] = "no_primary"
            output["primary_benchmark_adequate"] = "no_primary"
        elif primary_status_value in {"single", "coequal"} and keys:
            primary_outcomes = [
                outcome
                for outcome in outcomes
                if outcome["construction_key"] in keys
            ]
            complete_primary = (
                closed
                and len(primary_outcomes) == len(keys)
                and bool(primary_outcomes)
            )
            primary_unknown = any(
                item["verdict"] == "UNKNOWN" for item in primary_outcomes
            )
            primary_decided_against = any(
                item["verdict"] in {"REFUTED", "NO_CONCRETE_WITNESS"}
                for item in primary_outcomes
            )
            primary_all_pass = complete_primary and all(
                item["verdict"] == "PASS" for item in primary_outcomes
            )
            primary_all_target = primary_all_pass and all(
                item["target_adequacy"] == "met" for item in primary_outcomes
            )
            primary_target_no = complete_primary and any(
                item["verdict"] in {"REFUTED", "NO_CONCRETE_WITNESS"}
                or (
                    item["verdict"] == "PASS"
                    and item["target_adequacy"] == "not_met"
                )
                for item in primary_outcomes
            )
            primary_all_benchmark = primary_all_pass and all(
                item["benchmark_adequacy"] == "met"
                for item in primary_outcomes
            )
            primary_benchmark_no = complete_primary and any(
                item["verdict"] in {"REFUTED", "NO_CONCRETE_WITNESS"}
                or (
                    item["verdict"] == "PASS"
                    and item["benchmark_adequacy"] == "not_met"
                )
                for item in primary_outcomes
            )
            output["primary_valid"] = _tri(
                primary_all_pass,
                complete_primary and primary_decided_against,
            )
            output["primary_target_adequate"] = _tri(
                primary_all_target,
                primary_target_no,
            )
            output["primary_benchmark_adequate"] = _tri(
                primary_all_benchmark,
                primary_benchmark_no,
            )
            if primary_unknown:
                output["primary_valid"] = (
                    "no" if primary_decided_against else "unknown"
                )
        else:
            output["primary_valid"] = "unknown"
            output["primary_target_adequate"] = "unknown"
            output["primary_benchmark_adequate"] = "unknown"
    else:
        output["primary_valid"] = "unknown"
        output["primary_target_adequate"] = "unknown"
        output["primary_benchmark_adequate"] = "unknown"

    alternative_outcomes = [
        item
        for item in outcomes
        if item.get("answer_role") == "alternative_sufficient"
    ]
    alternative_passes = [
        item for item in alternative_outcomes if item["verdict"] == "PASS"
    ]
    alternative_unknown = [
        item for item in alternative_outcomes if item["verdict"] == "UNKNOWN"
    ]
    alternative_target_passes = [
        item for item in alternative_passes if item["target_adequacy"] == "met"
    ]
    alternative_target_unknown = [
        item
        for item in alternative_passes
        if item["target_adequacy"] == "unknown"
    ]
    alternative_benchmark_passes = [
        item
        for item in alternative_passes
        if item["benchmark_adequacy"] == "met"
    ]
    alternative_benchmark_unknown = [
        item
        for item in alternative_passes
        if item["benchmark_adequacy"] == "unknown"
    ]
    alternative_compliant_passes = [
        item
        for item in alternative_benchmark_passes
        if item["boundary_verdict"] == "inside"
    ]

    primary_valid_yes = output["primary_valid"] == "yes"
    primary_valid_unknown = output["primary_valid"] == "unknown"
    primary_target_yes = output["primary_target_adequate"] == "yes"
    primary_target_unknown = output["primary_target_adequate"] == "unknown"
    primary_benchmark_yes = output["primary_benchmark_adequate"] == "yes"
    primary_benchmark_unknown = output["primary_benchmark_adequate"] == "unknown"
    primary_compliant_yes = (
        primary_benchmark_yes
        and bool(primary_outcomes)
        and all(item["boundary_verdict"] == "inside" for item in primary_outcomes)
    )
    primary_compliant_unknown = (
        primary_benchmark_unknown
        or any(item["boundary_verdict"] == "unknown" for item in primary_outcomes)
    )

    # A COEQUAL primary whose branches all PASS is a response answering under
    # more than one reading of the relation (dual-track: root-only Step vs
    # contextual closure), one construction per reading. Validity stays
    # conjunctive — a refuted branch still kills the row — but adequacy over
    # all-passing branches is EXISTENTIAL: the benchmark evaluates its own
    # reading, and the branch written for that reading meets it. Conjunctive
    # adequacy under-credited a response whose full-contextual branch is a
    # certified native RPO PASS merely because its bonus root-only branch
    # cannot meet the full target (measured 2026-08-07, R6
    # gemini-3-flash-fruit). For same-target coequals all-pass conjunction
    # and disjunction coincide, so nothing else moves.
    coequal_all_pass = primary_status_value == "coequal" and primary_all_pass
    coequal_target_passes = coequal_all_pass and any(
        item["target_adequacy"] == "met" for item in primary_outcomes
    )
    coequal_benchmark_passes = coequal_all_pass and any(
        item["benchmark_adequacy"] == "met" for item in primary_outcomes
    )
    coequal_compliant_passes = coequal_all_pass and any(
        item["benchmark_adequacy"] == "met"
        and item["boundary_verdict"] == "inside"
        for item in primary_outcomes
    )

    row_valid_yes = primary_valid_yes or bool(alternative_passes)
    row_valid_unknown = primary_valid_unknown or bool(alternative_unknown)
    row_target_yes = (
        primary_target_yes
        or bool(alternative_target_passes)
        or coequal_target_passes
    )
    row_target_unknown = (
        primary_target_unknown
        or bool(alternative_unknown)
        or bool(alternative_target_unknown)
    )
    row_benchmark_yes = (
        primary_benchmark_yes
        or bool(alternative_benchmark_passes)
        or coequal_benchmark_passes
    )
    row_benchmark_unknown = (
        primary_benchmark_unknown
        or bool(alternative_unknown)
        or bool(alternative_benchmark_unknown)
    )
    row_compliant_yes = (
        primary_compliant_yes
        or bool(alternative_compliant_passes)
        or coequal_compliant_passes
    )
    row_compliant_unknown = (
        primary_compliant_unknown
        or bool(alternative_unknown)
        or bool(alternative_benchmark_unknown)
        or any(
            item["boundary_verdict"] == "unknown"
            for item in alternative_benchmark_passes
        )
    )

    output["has_valid_witness"] = _tri(
        row_valid_yes,
        closed and not row_valid_yes and not row_valid_unknown,
    )
    output["has_target_adequate_witness"] = _tri(
        row_target_yes,
        closed and not row_target_yes and not row_target_unknown,
    )
    output["has_benchmark_adequate_witness"] = _tri(
        row_benchmark_yes,
        closed and not row_benchmark_yes and not row_benchmark_unknown,
    )
    output["has_valid_compliant_witness"] = _tri(
        row_compliant_yes,
        closed and not row_compliant_yes and not row_compliant_unknown,
    )

    success_refuted = [
        item
        for item in success_outcomes
        if item["verdict"] == "REFUTED"
    ]
    success_non_witness = [
        item
        for item in success_outcomes
        if item["verdict"] == "NO_CONCRETE_WITNESS"
    ]
    if row_benchmark_yes:
        output["lane"] = "CertifiedValid"
    elif row_valid_yes and not row_benchmark_unknown:
        output["lane"] = "CertifiedTargetMismatch"
    elif row_valid_yes:
        output["lane"] = "CertifiedTargetUnknown"
    elif closed and not row_valid_unknown and success_refuted:
        output["lane"] = "CertifiedRefuted"
    elif closed and not row_valid_unknown and (
        success_non_witness or not success_outcomes
    ):
        output["lane"] = "NoWitness"
    else:
        output["lane"] = "CheckerUnknown"
    # Engine 3.3.0: non-decided rows carry their dedup-keyed abstention
    # evidence (typed cause set), so every abstention is audited rather
    # than a bare lane name.
    if output["lane"] not in {"CertifiedValid", "CertifiedRefuted", "NoWitness"}:
        causes = sorted(
            {
                f"outcome|{item['kind']}|{item['detail']}"
                for item in outcomes
                if item["verdict"] == "UNKNOWN"
            }
            | (
                {f"row|scoring_unresolved|{scoring_unresolved}"}
                if scoring_unresolved
                else set()
            )
            | (
                {f"row|gate|{gate_status}"}
                if gate_status not in {"full_consensus", "partial_consensus"}
                else set()
            )
        )
        output["abstention_evidence"] = {
            "version": "abstention-evidence/v1",
            "causes": causes,
            "distinct_causes": len(causes),
        }
    output["detail"] = ";".join(str(item["detail"]) for item in outcomes)[:2000]
    if row.get("unresolved_count"):
        output["detail"] += (
            f"|unresolved_full={row.get('unresolved_count')}"
            f"|unresolved_scoring={scoring_unresolved}"
            f"|unresolved_telemetry={row.get('telemetry_unresolved_count', '')}"
        )
    output["outcomes"] = outcomes
    output["score_row_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in output.items()
            if key != "score_row_sha256"
        }
    )
    return output


def _verify_gate_report(report: dict[str, Any]) -> str:
    declared = report.get("gate_report_sha256")
    if not isinstance(declared, str):
        raise ValueError("v3 gate report lacks gate_report_sha256")
    core = dict(report)
    core.pop("gate_report_sha256", None)
    observed = canonical_sha256(core)
    if declared != observed:
        raise ValueError(
            f"gate report hash mismatch: declared {declared}, observed {observed}"
        )
    return declared


def score_gate_report_v3(
    report: dict[str, Any],
    checker: Any,
    *,
    checker_binding: dict[str, Any] | None = None,
    boundary_policy_override: dict[str, Any] | None = None,
    allow_contract_substitution: bool = False,
    contract_substitution_reason: str | None = None,
    allow_early_v3_replay: bool = False,
    early_v3_replay_reason: str | None = None,
) -> dict[str, Any]:
    replay_reason = _validate_early_v3_replay_authorization(
        allow_early_v3_replay=allow_early_v3_replay,
        early_v3_replay_reason=early_v3_replay_reason,
    )
    gate_report_sha256 = _verify_gate_report(report)
    policy_bundle = report.get("policy_bundle")
    if not isinstance(policy_bundle, dict):
        raise ValueError("v3 gate report lacks policy_bundle")
    consensus_policy = policy_bundle.get("consensus")
    if not isinstance(consensus_policy, dict):
        raise ValueError("v3 gate report lacks consensus policy")
    missing_consensus_fields = {
        "allowed_pass_sets",
        "semantics_version",
        "threshold",
        "voted_fields",
    } - set(consensus_policy)
    if missing_consensus_fields and not allow_early_v3_replay:
        raise ValueError(
            "current v3 consensus policy lacks required fields "
            f"{sorted(missing_consensus_fields)}"
        )
    if not allow_early_v3_replay and (
        consensus_policy.get("semantics_version")
        != V3_CONSENSUS_SEMANTICS
        or report.get("consensus_semantics_version")
        != V3_CONSENSUS_SEMANTICS
    ):
        raise ValueError(
            "current v3 gate requires exact consensus semantics version "
            f"{V3_CONSENSUS_SEMANTICS!r}"
        )
    observed_consensus_hash = canonical_sha256(consensus_policy)
    if report.get("consensus_policy_sha256") != observed_consensus_hash:
        raise ValueError(
            "gate report consensus policy binding mismatch: "
            f"declared {report.get('consensus_policy_sha256')}, "
            f"observed {observed_consensus_hash}"
        )
    boundary_policy = policy_bundle.get("boundary")
    if not isinstance(boundary_policy, dict):
        boundary_policy = getattr(checker, "__tgc_boundary_policy__", None)
    declared_boundary_hash = report.get("boundary_policy_sha256")
    # An explicit override follows the same rule as contract substitution
    # below: allowed, but only as an auditable lineage fact, never silent.
    # The gate rows' own bundle keeps travelling in the report untouched.
    boundary_policy_substituted = False
    if boundary_policy_override is not None:
        if not isinstance(boundary_policy_override, dict):
            raise ValueError("boundary policy override must be a mapping")
        boundary_policy_substituted = (
            canonical_sha256(boundary_policy_override) != declared_boundary_hash
        )
        boundary_policy = boundary_policy_override
    if not isinstance(boundary_policy, dict):
        raise ValueError("v3 scoring requires a declarative boundary policy")
    if (
        "required_target" not in boundary_policy
        and not allow_early_v3_replay
    ):
        raise ValueError(
            "current v3 boundary policy lacks explicit required_target"
        )
    gate_required_target = boundary_policy.get("required_target")
    if gate_required_target is not None and (
        not isinstance(gate_required_target, str) or not gate_required_target
    ):
        raise ValueError(
            "boundary policy required_target must be a nonempty string or null"
        )
    observed_boundary_hash = canonical_sha256(boundary_policy)
    if (
        boundary_policy_override is None
        and declared_boundary_hash is not None
        and declared_boundary_hash != observed_boundary_hash
    ):
        raise ValueError(
            "gate report boundary policy binding mismatch: "
            f"declared {declared_boundary_hash}, observed {observed_boundary_hash}"
        )
    effective_checker_binding = getattr(checker, "__tgc_binding__", None)
    if allow_early_v3_replay and isinstance(effective_checker_binding, dict):
        if (
            checker_binding is not None
            and checker_binding != effective_checker_binding
            and (
                "early_v3_interface_assumption" in checker_binding
                or "early_v3_interface_assumption"
                in effective_checker_binding
            )
        ):
            raise ValueError(
                "early-v3 replay checker binding must be the effective "
                "runtime binding carrying the interface assumption"
            )
        binding = effective_checker_binding
    else:
        binding = checker_binding or effective_checker_binding
    if not isinstance(binding, dict):
        raise ValueError("v3 scoring requires a machine-readable checker binding")
    # Validate the checker/contract boundary before executing even one row.
    gate_contract = report.get("contract")
    checker_contract = getattr(checker, "__tgc_contract_binding__", None)
    contract_substituted = not (
        isinstance(gate_contract, dict)
        and isinstance(checker_contract, dict)
        and gate_contract == checker_contract
    )
    if contract_substituted and not allow_contract_substitution:
        raise ValueError(
            "scoring contract does not exactly match the gate contract; "
            "historical replay requires explicit contract-substitution authorization"
        )
    if contract_substituted and (
        not isinstance(contract_substitution_reason, str)
        or not contract_substitution_reason.strip()
    ):
        raise ValueError(
            "authorized contract substitution requires a nonempty replay reason"
        )
    rows = [
        {
            **row,
            **score_consensus_row_v3(
                row,
                checker,
                boundary_policy=boundary_policy,
                allow_early_v3_replay=allow_early_v3_replay,
                early_v3_replay_reason=replay_reason,
            ),
        }
        for row in report.get("rows", [])
    ]
    lane_counts = Counter(row["lane"] for row in rows)
    metric_counts = {
        metric: dict(sorted(Counter(row[metric] for row in rows).items()))
        for metric in METRICS
    }
    # A gate may only be scored against the contract that compiled it. Frozen
    # historical replay under a replacement contract is a distinct operation:
    # it must be explicitly authorized and receipted with a reason.
    substitution = {
        "contract_substituted": contract_substituted,
    }
    if substitution["contract_substituted"]:
        substitution["gate_contract_manifest_sha256"] = (
            gate_contract or {}
        ).get("contract_manifest_sha256")
        substitution["scoring_contract_manifest_sha256"] = (
            checker_contract or {}
        ).get("contract_manifest_sha256")
        substitution["contract_substitution_reason"] = (
            contract_substitution_reason.strip()
        )
    if boundary_policy_substituted:
        substitution["boundary_policy_substituted"] = True
        substitution["gate_boundary_policy_sha256"] = declared_boundary_hash
    replay_receipt: dict[str, Any] = {}
    if allow_early_v3_replay:
        claims = [
            claim
            for row in report.get("rows", [])
            for claim in row.get("agreed_claims", [])
            if isinstance(claim, dict)
        ]
        checker_objects: list[dict[str, Any]] = []
        for claim in claims:
            representative = claim.get("representative_checker_object")
            if isinstance(representative, dict):
                checker_objects.append(representative)
            by_pass = claim.get("checker_objects_by_pass")
            if isinstance(by_pass, dict):
                checker_objects.extend(
                    value for value in by_pass.values()
                    if isinstance(value, dict)
                )
        replay_detail = {
            "receipt_version": "tgc-early-v3-replay-receipt/1.0.0",
            "authorized": True,
            "reason": replay_reason,
            "assumed_checker_input_schema_version": V3_CHECKER_INPUT_VERSION,
            "source_consensus_semantics_version": report.get(
                "consensus_semantics_version"
            ),
            "source_policy_semantics_version": consensus_policy.get(
                "semantics_version"
            ),
            "claims_missing_checker_input_schema_version": sum(
                "checker_input_schema_version" not in claim
                for claim in claims
            ),
            "checker_objects_with_retired_fields": sum(
                set(value) != {"kind", "payload"}
                for value in checker_objects
            ),
            "retired_specificity_sentinel_count": sum(
                value.get("payload")
                in (
                    {"family_only": True},
                    {"unparseable": True},
                )
                for value in checker_objects
            ),
            "rows_missing_scoring_unresolved_count": sum(
                "scoring_unresolved_count" not in row
                for row in report.get("rows", [])
            ),
            "boundary_missing_required_target": (
                "required_target" not in boundary_policy
            ),
        }
        interface_assumption = (
            effective_checker_binding.get("early_v3_interface_assumption")
            if isinstance(effective_checker_binding, dict)
            else None
        )
        if interface_assumption is not None:
            replay_detail["checker_interface_assumption"] = (
                interface_assumption
            )
        replay_receipt = {"early_v3_replay": replay_detail}
    result = {
        "score_report_version": "tgc-score-report/3.0.0",
        "lineage": {
            "gate_report_sha256": gate_report_sha256,
            "run_contract_sha256": report["run_contract_sha256"],
            **substitution,
            **replay_receipt,
            "consensus_policy_sha256": report[
                "consensus_policy_sha256"
            ],
            "boundary_policy": boundary_policy,
            "boundary_policy_sha256": canonical_sha256(boundary_policy),
            "checker_binding": binding,
            "checker_binding_sha256": canonical_sha256(binding),
            "scoring_policy": SCORING_POLICY,
            "scoring_policy_sha256": canonical_sha256(SCORING_POLICY),
            # Completes the provenance chain: contract, checker bundle and policies were all
            # hash-covered, but the engine source that canonicalises and scores was not.
            "engine_implementation_sha256": engine_implementation_sha256(),
        },
        "session_count": len(rows),
        "lane_counts": dict(sorted(lane_counts.items())),
        "metric_counts": metric_counts,
        "rows": rows,
    }
    result["score_report_sha256"] = canonical_sha256(result)
    return result
