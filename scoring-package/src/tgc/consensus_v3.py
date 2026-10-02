from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any

from .common import (
    V3_CHECKER_INPUT_VERSION,
    V3_CONSENSUS_SEMANTICS_VERSION,
    canonical_sha256,
    content_id,
    project_v3_checker_input,
)

V3_COMPILED = "tgc-compiled-record/3.0.0"
V3_CONSENSUS = "tgc-consensus/3.0.0"
V3_GATE_REPORT = "tgc-gate-report/3.0.0"
# Consensus SEMANTICS version, published on every row and gate report. The wire
# schema versions above name the shape a reader must parse; this names what
# AGREEMENT MEANS. 3.2.0 = refinement-join merge of payload-fragmented
# same-kind claims (below) + scoring-core-only gating. 3.3.0 extends the same
# lattice to the CHECKER-INPUT channel and stops counting a checker-input
# dispute on a contract-derived kind as verdict-bearing. 3.3.1 applies that
# same verdict-irrelevance rule to registry-derived frame-only kinds, whose
# pinned outcome is NO_CONCRETE_WITNESS regardless of their free-text note. The
# wire versions are
# deliberately NOT bumped: `scoring.py` dispatches v3 rows and v3 gate reports
# on those exact strings, and every old artifact already carries its own
# consensus_policy_sha256, so nothing needs a back-compat flag.
V3_CONSENSUS_SEMANTICS = V3_CONSENSUS_SEMANTICS_VERSION
DEFAULT_VOTED_FIELDS = (
    "specificity",
    "claimed_target",
    "claim_status",
    "answer_role",
)
POLAR_STATUSES = {"claimed_valid", "claimed_invalid"}
TELEMETRY_STATUSES = {"hypothetical", "mentioned", "unclear"}

# ---------------------------------------------------------------------------
# Refinement lattice (consensus semantics 3.2.0)
#
# Two honest extractors reading one construction routinely transcribe it at
# different levels of detail: one writes the tuple order, the other leaves the
# optional field out. Hashing the payload makes those two readings different
# mathematical objects, so both fall below threshold and the session abstains
# on a construction nobody actually disagreed about. Offline replay over five
# frozen rounds measured this class at 29/101 of all disputes.
#
# The repair is a partial order rather than a similarity score: BOTTOM is
# absent information in each of its encodings, and the JOIN of two payloads is
# their least upper bound. A join exists only when the two readings are
# refinements of one object; any disagreement is CONFLICT and fails closed, so
# a merge can add detail but can never overwrite a stated value.
# ---------------------------------------------------------------------------

CONFLICT: Any = object()
BOTTOM_STRINGS = frozenset({"", "unspecified", "unknown", "not_stated"})


def is_bottom(value: Any) -> bool:
    """Absent information, in any of the encodings the schemas produce."""
    if isinstance(value, (dict, list)):
        return len(value) == 0
    if isinstance(value, str):
        return value in BOTTOM_STRINGS
    return value is None


def _conflict(
    path: str, reason: str, conflicts: list[dict[str, str]] | None
) -> Any:
    if conflicts is not None:
        conflicts.append({"path": path or "/", "reason": reason})
    return CONFLICT


def refinement_join(
    left: Any,
    right: Any,
    path: str = "",
    bottom_fills: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, str]] | None = None,
) -> Any:
    """Least upper bound of two payloads in the refinement lattice, or CONFLICT.

    bottom join x = x; dicts join over the union of keys (a missing key is
    bottom); lists join elementwise and require equal length; scalars join iff
    they are equal or one side is bottom. Everything else is CONFLICT and the
    caller must NOT merge.
    """
    left_bottom, right_bottom = is_bottom(left), is_bottom(right)
    if left_bottom and right_bottom:
        return right if isinstance(left, (dict, list)) else left
    if left_bottom:
        if bottom_fills is not None:
            bottom_fills.append(
                {"path": path or "/", "value": deepcopy(right), "side": "left"}
            )
        return right
    if right_bottom:
        if bottom_fills is not None:
            bottom_fills.append(
                {"path": path or "/", "value": deepcopy(left), "side": "right"}
            )
        return left
    if isinstance(left, dict) and isinstance(right, dict):
        joined: dict[str, Any] = {}
        for key in sorted(set(left) | set(right)):
            value = refinement_join(
                left.get(key),
                right.get(key),
                f"{path}/{key}",
                bottom_fills,
                conflicts,
            )
            if value is CONFLICT:
                return CONFLICT
            joined[key] = value
        return joined
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return _conflict(f"{path}[]", "list-length", conflicts)
        joined_items: list[Any] = []
        for index in range(len(left)):
            value = refinement_join(
                left[index],
                right[index],
                f"{path}[{index}]",
                bottom_fills,
                conflicts,
            )
            if value is CONFLICT:
                return CONFLICT
            joined_items.append(value)
        return joined_items
    if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
        return _conflict(path, "type-mismatch", conflicts)
    if isinstance(left, bool) != isinstance(right, bool):
        return _conflict(path, "type-mismatch", conflicts)
    if left == right:
        return left
    return _conflict(path, "scalar-disagreement", conflicts)


def refinement_join_all(
    values: list[Any],
) -> tuple[Any, list[dict[str, Any]]]:
    """Fold ``refinement_join`` left to right, collecting the bottom fills."""
    bottom_fills: list[dict[str, Any]] = []
    if not values:
        return None, bottom_fills
    joined = values[0]
    for value in values[1:]:
        step: list[dict[str, Any]] = []
        joined = refinement_join(joined, value, "", step)
        if joined is CONFLICT:
            return CONFLICT, bottom_fills
        bottom_fills.extend(step)
    return joined, bottom_fills


def _refinement_path_value(value: Any, path: str) -> Any:
    """Read one refinement-receipt path from a checker core.

    Receipt paths use slash-separated mapping keys and zero-based ``[i]``
    list selectors. A missing or malformed path is bottom (``None``).
    """

    if path in {"", "/"}:
        return value
    current = value
    for segment in path.lstrip("/").split("/"):
        bracket = segment.find("[")
        key = segment if bracket < 0 else segment[:bracket]
        rest = "" if bracket < 0 else segment[bracket:]
        if key:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        while rest:
            if not rest.startswith("[") or "]" not in rest:
                return None
            end = rest.find("]")
            token = rest[1:end]
            if not token.isdigit() or not isinstance(current, list):
                return None
            index = int(token)
            if index >= len(current):
                return None
            current = current[index]
            rest = rest[end + 1 :]
    return current


def refinement_field_supporting_passes(
    values_by_pass: dict[Any, Any], joined_value: Any, path: str
) -> list[Any]:
    """Passes that state a non-bottom value compatible with the joined field.

    Checker-identity multiplicity is deliberately irrelevant here: two passes
    may independently state the same field while differing elsewhere in their
    checker cores. A pass counts only when its value refines to the winning
    joined value, so an excluded pass that states a conflicting value cannot
    manufacture replication.
    """

    target = _refinement_path_value(joined_value, path)
    if is_bottom(target):
        return []
    supporting: list[Any] = []
    for pass_number, value in values_by_pass.items():
        stated = _refinement_path_value(value, path)
        if is_bottom(stated):
            continue
        combined = refinement_join(stated, target)
        if combined is not CONFLICT and canonical_sha256(combined) == canonical_sha256(
            target
        ):
            supporting.append(pass_number)
    return supporting


def _claim_kind(claim: dict[str, Any]) -> str:
    core = claim.get("mathematical_core")
    if isinstance(core, dict) and core.get("kind") is not None:
        return str(core["kind"])
    return str(claim.get("kind"))


def _evidence_spans(claim: dict[str, Any]) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for bound in claim.get("evidence") or []:
        start = bound.get("start")
        end = bound.get("end")
        if isinstance(start, int) and isinstance(end, int):
            spans.append((str(bound.get("source_id")), start, end))
    return spans


def _span_overlap_chars(
    left: list[tuple[str, int, int]],
    right: list[tuple[str, int, int]],
) -> int:
    """Widest overlap in characters over span pairs sharing a source_id."""
    widest = 0
    for left_source, left_start, left_end in left:
        for right_source, right_start, right_end in right:
            if (
                left_source == right_source
                and left_start < right_end
                and right_start < left_end
            ):
                widest = max(
                    widest,
                    min(left_end, right_end) - max(left_start, right_start),
                )
    return widest


class _ClaimUnit:
    """A candidate consensus claim: at most one transcription per pass."""

    __slots__ = (
        "claims",
        "merged",
        "bottom_fills",
        "joined_payload",
        "span_overlap_chars",
    )

    def __init__(self, claims: dict[int, dict[str, Any]]) -> None:
        self.claims = dict(claims)
        self.merged = False
        self.bottom_fills: list[dict[str, Any]] = []
        self.joined_payload: Any = None
        self.span_overlap_chars = 0

    def passes(self) -> set[int]:
        return set(self.claims)

    def representative(self) -> dict[str, Any]:
        return self.claims[min(self.claims)]

    def kinds(self) -> set[str]:
        return {_claim_kind(claim) for claim in self.claims.values()}

    def spans(self) -> list[tuple[str, int, int]]:
        spans: list[tuple[str, int, int]] = []
        for claim in self.claims.values():
            spans.extend(_evidence_spans(claim))
        return spans

    def mathematical_core(self) -> dict[str, Any]:
        if not self.merged:
            return self.representative()["mathematical_core"]
        return {
            "kind": sorted(self.kinds())[0],
            "payload": self.joined_payload,
        }

    def joined_checker_core(self) -> tuple[Any, list[dict[str, Any]]]:
        """Least upper bound of this unit's per-pass CHECKER cores.

        Same lattice as the mathematical core, applied to the object the
        checker actually consumes. Returns ``(CONFLICT, fills)`` when the
        readings contradict each other, so the caller fails closed.
        """
        return refinement_join_all(
            [
                self.claims[pass_number].get("checker_core")
                for pass_number in sorted(self.claims)
            ]
        )

    def mathematical_identity(self) -> str:
        if not self.merged:
            return str(self.representative()["mathematical_identity"])
        return canonical_sha256(self.mathematical_core())

    def construction_key(self) -> dict[str, Any]:
        representative = self.representative()
        return {
            "source_id": str(representative["source_id"]),
            "mathematical_identity": self.mathematical_identity(),
            "source_occurrence": int(representative["source_occurrence"]),
        }

    def order_key(self) -> tuple[str, str, int]:
        key = self.construction_key()
        return (
            key["source_id"],
            key["mathematical_identity"],
            key["source_occurrence"],
        )

    def merge_key(self) -> tuple[tuple[int, str, str, int], ...]:
        return tuple(
            sorted(
                (
                    pass_number,
                    str(claim["source_id"]),
                    str(claim["mathematical_identity"]),
                    int(claim["source_occurrence"]),
                )
                for pass_number, claim in self.claims.items()
            )
        )

    def merge_receipt(self) -> dict[str, Any]:
        return {
            "merged_from": sorted(
                {
                    str(claim["mathematical_identity"])
                    for claim in self.claims.values()
                }
            ),
            "merged_from_construction_keys": [
                deepcopy(self.claims[pass_number]["construction_key"])
                for pass_number in sorted(self.claims)
            ],
            "bottom_fills": deepcopy(self.bottom_fills),
            "joined_passes": sorted(self.claims),
            "span_overlap_chars": self.span_overlap_chars,
        }


def _merge_evidence(
    left: _ClaimUnit, right: _ClaimUnit
) -> dict[str, Any] | None:
    """Return merge evidence for two units, or None if they do not mate.

    Merge-mates need disjoint passes (a merged claim never double-counts one
    reader), an IDENTICAL kind (family and candidate-set matching is out of
    scope: `lpo` and `rpo` are different mathematics, not one object seen
    twice), at least one overlapping evidence span on the same source, and a
    payload join that does not conflict.
    """
    if left.passes() & right.passes():
        return None
    kinds = left.kinds() | right.kinds()
    if len(kinds) != 1:
        return None
    overlap = _span_overlap_chars(left.spans(), right.spans())
    if overlap <= 0:
        return None
    claims = {**left.claims, **right.claims}
    ordered = [claims[pass_number] for pass_number in sorted(claims)]
    payload, bottom_fills = refinement_join_all(
        [claim["mathematical_core"].get("payload") for claim in ordered]
    )
    if payload is CONFLICT:
        return None
    return {
        "claims": claims,
        "payload": payload,
        "bottom_fills": bottom_fills,
        "span_overlap_chars": overlap,
    }


def _merge_claim_units(units: list[_ClaimUnit]) -> list[_ClaimUnit]:
    """Deterministic agglomeration: widest span overlap first, then key order."""
    working = list(units)
    while True:
        best: tuple[Any, int, int, dict[str, Any]] | None = None
        for left_index in range(len(working)):
            for right_index in range(left_index + 1, len(working)):
                evidence = _merge_evidence(
                    working[left_index], working[right_index]
                )
                if evidence is None:
                    continue
                rank = (
                    -evidence["span_overlap_chars"],
                    working[left_index].merge_key(),
                    working[right_index].merge_key(),
                )
                if best is None or rank < best[0]:
                    best = (rank, left_index, right_index, evidence)
        if best is None:
            return working
        _, left_index, right_index, evidence = best
        left, right = working[left_index], working[right_index]
        merged = _ClaimUnit(evidence["claims"])
        merged.merged = True
        merged.joined_payload = evidence["payload"]
        merged.bottom_fills = evidence["bottom_fills"]
        merged.span_overlap_chars = max(
            left.span_overlap_chars,
            right.span_overlap_chars,
            int(evidence["span_overlap_chars"]),
        )
        working = [
            unit
            for index, unit in enumerate(working)
            if index not in (left_index, right_index)
        ]
        working.append(merged)
        working.sort(key=lambda unit: unit.merge_key())


def _joined_checker_object(
    unit: _ClaimUnit, core: dict[str, Any]
) -> dict[str, Any] | None:
    """Return the closed v3 checker input represented by the joined core."""
    try:
        return project_v3_checker_input(core)
    except ValueError:
        return None


def _checker_input_consensus(
    unit: _ClaimUnit, threshold: int
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Consensus on the object the CHECKER consumes, over two stages.

    Consensus semantics 3.3.0. Stage one is the historical exact-identity
    majority vote: `threshold` passes hashed the same checker core. Stage two
    is the refinement lattice already used for the mathematical core, applied
    to the same channel: two honest readers routinely transcribe one
    construction at different levels of detail, and hashing the free-text
    checker payload made those two readings different checker INPUTS even
    after they had agreed on the mathematical object. A frozen out-of-sample
    round measured 12 of 45 agreed claims failing here with an otherwise empty
    dispute set.

    The join is a strict fallback, so nothing that agrees today can change:
    a conflicting concrete value anywhere fails closed and the claim stays
    uncertifiable, exactly as before. A merged claim keeps its 3.2.0 rule
    (join only): its identity IS the join, so its checker input must be the
    join or nothing.

    Returns ``(vote, representative_object, receipt)``. The receipt names the
    basis and records every bottom-filled field and the pass that witnessed
    it, exactly like ``merge_receipt``; ``single_witness_fields`` is the
    subset of the joined object that only ONE pass transcribed.
    """
    claims = dict(sorted(unit.claims.items()))
    identities = {
        pass_number: claim["checker_input_identity"]
        for pass_number, claim in claims.items()
    }
    votes = {
        str(pass_number): identity
        for pass_number, identity in sorted(identities.items())
    }
    joined_from = sorted({str(identity) for identity in identities.values()})

    if not unit.merged:
        vote = field_vote(identities, threshold)
        if vote["status"] == "agreed":
            winning_identity = vote["value"]
            representative_object = next(
                project_v3_checker_input(claim["checker_core"])
                for claim in claims.values()
                if claim["checker_input_identity"] == winning_identity
            )
            return (
                {**vote, "basis": "exact_identity"},
                representative_object,
                {
                    "basis": "exact_identity",
                    "joined_from": joined_from,
                    "joined_passes": sorted(claims),
                    "bottom_fills": [],
                    "single_witness_fields": [],
                },
            )

    core: Any = CONFLICT
    bottom_fills: list[dict[str, Any]] = []
    joined_passes = sorted(claims)
    conflicting_passes: list[int] = []
    basis = "refinement_join"
    if len(claims) >= threshold:
        core, bottom_fills = unit.joined_checker_core()
    if not isinstance(core, dict) and len(claims) > threshold:
        # Consensus semantics 3.4.0: a full-join CONFLICT with MORE readers
        # than the threshold retries over subsets, exactly as every field
        # vote already resolves 2-of-3. Threshold readers whose checker cores
        # join cleanly ARE the consensus the policy defines; the outvoted
        # reading is recorded, never merged. Fail-closed on ambiguity: the
        # subset must be the UNIQUE clean join at the largest achievable
        # size, or the input stays unresolved. Measured 2026-08-02: two
        # passes transcribed one measure with identical descriptive
        # components while the third wrote the response's shorthand names;
        # the full join conflicted and a decidable row abstained.
        for size in range(len(claims) - 1, threshold - 1, -1):
            clean: list[tuple[tuple[int, ...], Any, list[dict[str, Any]]]] = []
            for subset in itertools.combinations(sorted(claims), size):
                subset_core, subset_fills = refinement_join_all(
                    [claims[pass_number].get("checker_core") for pass_number in subset]
                )
                if isinstance(subset_core, dict):
                    clean.append((subset, subset_core, subset_fills))
            if len(clean) == 1:
                subset, core, bottom_fills = clean[0]
                joined_passes = list(subset)
                conflicting_passes = [
                    pass_number
                    for pass_number in sorted(claims)
                    if pass_number not in subset
                ]
                basis = "refinement_join_majority"
            if clean:
                break
    if not isinstance(core, dict):
        return (
            {
                "status": "unresolved",
                "value": None,
                "support_count": 0,
                "votes": votes,
                "basis": None,
            },
            None,
            None,
        )
    if basis == "refinement_join_majority":
        representative_object = _joined_checker_object(unit, core)
    else:
        representative_object = _joined_checker_object(unit, core)
    return (
        {
            "status": "agreed",
            "value": canonical_sha256(core),
            "support_count": len(joined_passes),
            "votes": votes,
            "basis": basis,
        },
        representative_object,
        {
            "basis": basis,
            "joined_from": joined_from,
            "joined_passes": joined_passes,
            **(
                {"conflicting_passes": conflicting_passes}
                if conflicting_passes
                else {}
            ),
            "bottom_fills": deepcopy(bottom_fills),
            # A field stated by fewer than threshold supporting PASSES. A
            # bottom fill merely proves that one join step supplied the field;
            # it does not prove only one pass stated it. Count the field itself
            # across all supporting pass cores, independent of their complete
            # checker identities, and require compatibility with the joined
            # value so a conflicting pass cannot manufacture replication.
            "single_witness_fields": sorted(
                {
                    path
                    for path in {
                        str(fill.get("path")) for fill in bottom_fills
                    }
                    if len(
                        refinement_field_supporting_passes(
                            {
                                pass_number: claim.get("checker_core")
                                for pass_number, claim in claims.items()
                            },
                            core,
                            path,
                        )
                    )
                    < threshold
                }
            ),
        },
    )


def _status_partition(values: set[str]) -> str:
    if "claimed_valid" in values:
        return "positive_possible"
    if "claimed_invalid" in values:
        return "negative_only"
    if values and values <= TELEMETRY_STATUSES:
        return "telemetry_only"
    return "unclassified"


def _claim_status_values(claims: dict[int, dict[str, Any]]) -> set[str]:
    return {str(claim.get("claim_status")) for claim in claims.values()}


def _allowed_pass_sets(policy: dict[str, Any]) -> set[tuple[int, ...]]:
    if "allowed_pass_sets" not in policy:
        raise ValueError("current v3 consensus policy lacks allowed_pass_sets")
    values = policy["allowed_pass_sets"]
    if not isinstance(values, list) or any(
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(item, int) or isinstance(item, bool)
            for item in value
        )
        for value in values
    ):
        raise ValueError("consensus allowed_pass_sets must be lists of integers")
    result = {tuple(value) for value in values}
    if not result:
        raise ValueError("consensus policy has no allowed pass sets")
    return result


def _threshold(policy: dict[str, Any], pass_count: int) -> int:
    if "threshold" not in policy:
        raise ValueError("current v3 consensus policy lacks threshold")
    value = policy["threshold"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("consensus threshold must be an integer")
    if value < 1 or value > pass_count:
        raise ValueError(
            f"invalid consensus threshold {value} for {pass_count} passes"
        )
    return value


def _voted_fields(policy: dict[str, Any]) -> tuple[str, ...]:
    if "voted_fields" not in policy:
        raise ValueError("current v3 consensus policy lacks voted_fields")
    raw_values = policy["voted_fields"]
    if not isinstance(raw_values, list):
        raise ValueError("consensus voted_fields must be a list")
    values = tuple(raw_values)
    if not values or any(value not in DEFAULT_VOTED_FIELDS for value in values):
        raise ValueError(f"unsupported consensus voted_fields {values!r}")
    return values


def field_vote(values_by_pass: dict[int, Any], threshold: int) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    representatives: dict[str, Any] = {}
    for value in values_by_pass.values():
        key = canonical_sha256(value)
        counts[key] += 1
        representatives[key] = value
    winners = [key for key, count in counts.items() if count >= threshold]
    if len(winners) == 1:
        winner = winners[0]
        return {
            "status": "agreed",
            "value": representatives[winner],
            "support_count": counts[winner],
            "votes": {
                str(pass_number): value
                for pass_number, value in sorted(values_by_pass.items())
            },
        }
    return {
        "status": "unresolved",
        "value": None,
        "support_count": max(counts.values(), default=0),
        "votes": {
            str(pass_number): value
            for pass_number, value in sorted(values_by_pass.items())
        },
    }


# Specificity is the one voted axis that is ORDERED by how much the response is
# credited with having supplied: `concrete` claims a complete checkable object,
# `partial` claims the stated typed fields with content missing, and the two
# non-witness readings claim no object at all. The floor operation itself is
# retained for verdict-irrelevant claims and telemetry, where resolving DOWN
# cannot alter a mathematical lane. It MUST NOT decide a positive,
# payload-bearing claim: removing a PASS can create a false decided NoWitness,
# which is not a conservative abstention. Such a split stays unresolved.
SPECIFICITY_STRENGTH = {
    "concrete": 3,
    "partial": 2,
    "family_only": 1,
    "unparseable": 0,
}


def specificity_floor_vote(vote: dict[str, Any]) -> dict[str, Any]:
    """Resolve an unresolved specificity vote to its weakest observed reading."""

    if vote.get("status") == "agreed":
        return vote
    observed = [
        value
        for value in (vote.get("votes") or {}).values()
        if value in SPECIFICITY_STRENGTH
    ]
    if not observed or len(set(observed)) < 2:
        # Nothing to join (no readable votes, or a single value that simply
        # never reached threshold): stay unresolved, fail-closed.
        return vote
    weakest = min(observed, key=lambda value: SPECIFICITY_STRENGTH[value])
    return {
        **vote,
        "status": "agreed",
        "value": weakest,
        "basis": "specificity_floor",
        "joined_from": sorted(set(observed), key=lambda v: -SPECIFICITY_STRENGTH[v]),
    }


def _claim_key(claim: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(claim["source_id"]),
        str(claim["mathematical_identity"]),
        int(claim["source_occurrence"]),
    )


def _construction_key_sort(value: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(value.get("source_id")),
        str(value.get("mathematical_identity")),
        int(value.get("source_occurrence", 0)),
    )


def _primary_vote_value(
    record: dict[str, Any],
    key_remap: dict[tuple[str, str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    remap = key_remap or {}
    keys = sorted(
        (
            remap.get(_construction_key_sort(value), value)
            for value in record["primary"]["construction_keys"]
        ),
        key=_construction_key_sort,
    )
    return {
        "status": record["primary"]["status"],
        "construction_keys": keys,
    }


def _run_comparison(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": binding["run_id"],
        "run_contract_sha256": binding["run_contract_sha256"],
        "roster_entry_sha256": binding["roster_entry_sha256"],
    }


def _verify_policy_binding(record: dict[str, Any]) -> None:
    bundle = record.get("policy_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("v3 compiled record lacks policy_bundle")
    lineage = record.get("lineage")
    if not isinstance(lineage, dict):
        raise ValueError("v3 compiled record lacks lineage")
    fields = {
        "policy_bundle_sha256": bundle,
        "identity_policy_sha256": bundle.get("identity"),
        "consensus_policy_sha256": bundle.get("consensus"),
        "boundary_policy_sha256": bundle.get("boundary"),
        "lineage_policy_sha256": bundle.get("lineage"),
    }
    for hash_field, value in fields.items():
        if not isinstance(value, dict):
            raise ValueError(
                f"v3 policy bundle lacks object for {hash_field}"
            )
        observed = canonical_sha256(value)
        declared = lineage.get(hash_field)
        if declared != observed:
            raise ValueError(
                f"policy binding mismatch for {hash_field}: "
                f"declared {declared}, observed {observed}"
            )


def _default_input_independent_kinds() -> frozenset[str]:
    """Kinds whose checker evaluates all readings instead of requiring text identity.

    Imported from the checker layer rather than restated here: the fact is a
    property of the decision procedure, and a second copy of the list would
    silently rot the day a route is added. Imported lazily so the gate keeps
    no import-time dependency on the checker bundle.
    """
    from .checkers import CONTRACT_DERIVED_KINDS

    return CONTRACT_DERIVED_KINDS


def gate_records_v3(
    records: list[dict[str, Any]],
    *,
    require_independence: bool = True,
    input_independent_kinds: frozenset[str] | None = None,
) -> dict[str, Any]:
    independent_kinds = (
        _default_input_independent_kinds()
        if input_independent_kinds is None
        else frozenset(input_independent_kinds)
    )

    def checker_input_is_verdict_irrelevant(claim: dict[str, Any]) -> bool:
        """Whether text disagreement is decided inside the registered checker.

        Multi-input routes inspect every reading and return UNKNOWN when their
        decisions differ or a reading is unsupported. Frame-only routes ignore it for a
        different reason: the registry declares that they carry no mathematical
        object, so scoring deterministically returns NO_CONCRETE_WITNESS. The
        compiler stamps that registry fact into each claim; requiring an exact
        True keeps historical compiled records and malformed metadata fail-closed.
        """

        return (
            claim["mathematical_core"]["kind"] in independent_kinds
            or claim.get("frame_only") is True
        )

    def stamped_frame_only(claim: dict[str, Any]) -> bool:
        metadata = claim.get("canonicalization") or {}
        return (
            metadata.get("frame_only") is True
            and metadata.get("identity_fields") == []
            and metadata.get("concrete_required") == []
            and metadata.get("concrete_any_of") == []
        )
    records_by_pass: dict[int, dict[str, Any]] = {}
    for record in records:
        if record.get("compiled_schema_version") != V3_COMPILED:
            raise ValueError("gate_records_v3 received a non-v3 compiled record")
        pass_number = record["extractor"]["pass_number"]
        if pass_number in records_by_pass:
            raise ValueError(f"duplicate pass number {pass_number}")
        records_by_pass[pass_number] = record
    if not records_by_pass:
        raise ValueError("no compiled records supplied")

    for record in records_by_pass.values():
        _verify_policy_binding(record)

    first = records_by_pass[min(records_by_pass)]
    policy_bundle = first.get("policy_bundle")
    if not isinstance(policy_bundle, dict):
        raise ValueError("v3 compiled record lacks policy_bundle")
    consensus_policy = policy_bundle.get("consensus")
    if not isinstance(consensus_policy, dict):
        raise ValueError("v3 compiled record lacks consensus policy")
    pass_numbers = sorted(records_by_pass)
    if tuple(pass_numbers) not in _allowed_pass_sets(consensus_policy):
        raise ValueError(
            f"pass set {pass_numbers} is outside the bound consensus policy"
        )
    threshold = _threshold(consensus_policy, len(records))
    voted_fields = _voted_fields(consensus_policy)

    for record in records_by_pass.values():
        if record["contract"] != first["contract"]:
            raise ValueError("contract bindings differ across passes")
        if record["session"] != first["session"]:
            raise ValueError("session bindings differ across passes")
        if record.get("policy_bundle") != policy_bundle:
            raise ValueError("policy bundles differ across passes")
        if _run_comparison(record["run_binding"]) != _run_comparison(
            first["run_binding"]
        ):
            raise ValueError("run/roster bindings differ across passes")
        for field in (
            "modular_registry_sha256",
            "identity_policy_sha256",
            "consensus_policy_sha256",
            "lineage_policy_sha256",
            "boundary_policy_sha256",
            "run_contract_sha256",
        ):
            if record["lineage"].get(field) != first["lineage"].get(field):
                raise ValueError(f"lineage policy differs across passes: {field}")

    extractor_ids = [
        record["extractor"]["extractor_id"] for record in records
    ]
    extraction_ids = [
        record["extractor"]["extraction_id"] for record in records
    ]
    pass_ids = [record["run_binding"]["pass_id"] for record in records]
    independence_warnings: list[str] = []
    if len(set(extractor_ids)) != len(extractor_ids):
        independence_warnings.append("extractor_id_reused_across_passes")
    if len(set(extraction_ids)) != len(extraction_ids):
        independence_warnings.append("extraction_id_reused_across_passes")
    if len(set(pass_ids)) != len(pass_ids):
        independence_warnings.append("pass_id_reused_across_passes")
    if not all(
        record["extractor"]["independence_attestation"] for record in records
    ):
        independence_warnings.append(
            "one_or_more_passes_lack_independence_attestation"
        )

    record_status = field_vote(
        {
            pass_number: record["record_status"]
            for pass_number, record in records_by_pass.items()
        },
        threshold,
    )
    coverage_status = field_vote(
        {
            pass_number: record["coverage"]["completeness_status"]
            for pass_number, record in records_by_pass.items()
        },
        threshold,
    )

    grouped: dict[
        tuple[str, str, int], dict[int, dict[str, Any]]
    ] = defaultdict(dict)
    for pass_number, record in records_by_pass.items():
        for claim in record["claims"]:
            grouped[_claim_key(claim)][pass_number] = claim

    # Consensus semantics 3.2.0: refinement-join merge. Exact-identity grouping
    # above answers "did two passes hash the same object"; this stage answers
    # "did they read the same object at different levels of detail". Groups
    # from different passes that name one kind over an overlapping span and
    # whose payloads JOIN are folded into a single claim carrying the joined
    # core; a payload conflict anywhere leaves both groups exactly where they
    # were, unresolved.
    units = _merge_claim_units(
        [_ClaimUnit(grouped[key]) for key in sorted(grouped)]
    )
    # A merge redefines identity for this session, so every reference to a
    # healed identity has to move with it. The per-pass primary construction
    # keys are the one such reference inside the row: left unmapped they would
    # name a primary that no consensus claim carries, and the primary vote
    # would read as disagreement about which object is primary when both
    # passes named the same one.
    merged_key_remap: dict[tuple[str, str, int], dict[str, Any]] = {}
    for unit in units:
        if not unit.merged:
            continue
        merged_key = unit.construction_key()
        for claim in unit.claims.values():
            merged_key_remap[_claim_key(claim)] = merged_key

    agreed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    below_threshold: list[dict[str, Any]] = []
    minority_rejected: list[dict[str, Any]] = []
    merged_claim_count = 0
    for unit in sorted(units, key=lambda item: item.order_key()):
        occurrence_by_pass = unit.claims
        support_count = len(occurrence_by_pass)
        source_claim_ids = {
            str(pass_number): claim["claim_id"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        evidence_by_pass = {
            str(pass_number): claim["evidence"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        axis_evidence_by_pass = {
            str(pass_number): claim["axis_evidence"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        field_evidence_by_pass = {
            str(pass_number): claim["field_evidence"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        if unit.merged:
            merged_claim_count += 1
        (
            checker_vote,
            checker_representative,
            checker_receipt,
        ) = _checker_input_consensus(unit, threshold)
        merge_receipt = unit.merge_receipt() if unit.merged else None
        construction_key = unit.construction_key()
        status_values = _claim_status_values(occurrence_by_pass)
        status_partition = _status_partition(status_values)
        base = {
            # A merged claim's identity is recomputed from the JOINED core, so
            # its id is derived from that key plus the identities it healed:
            # the joined payload can coincide with an unmerged group's payload
            # and the two must stay separately addressable.
            "consensus_claim_id": (
                content_id(
                    "consensus-v3-merged",
                    {
                        **construction_key,
                        "merged_from": merge_receipt["merged_from"],
                    },
                )
                if merge_receipt is not None
                else content_id("consensus-v3", construction_key)
            ),
            "construction_key": construction_key,
            "source_id": construction_key["source_id"],
            "mathematical_identity": construction_key["mathematical_identity"],
            "source_occurrence": construction_key["source_occurrence"],
            "mathematical_core": unit.mathematical_core(),
            "merged": unit.merged,
            "merge_receipt": merge_receipt,
            "status_partition": status_partition,
            "observed_claim_statuses": sorted(status_values),
            "checker_input_consensus": checker_vote,
            "checker_input_receipt": checker_receipt,
            "representative_checker_object": checker_representative,
            "canonicalization_supported": all(
                claim["canonicalization"]["supported"]
                for claim in occurrence_by_pass.values()
            ),
            # Contract-derived, compiler-stamped property. All supporting
            # passes must carry the same affirmative registry fact; absent or
            # conflicting metadata remains fail-closed.
            "frame_only": all(
                stamped_frame_only(claim)
                for claim in occurrence_by_pass.values()
            ),
            "support_count": support_count,
            "supporting_passes": sorted(occurrence_by_pass),
            "source_claim_ids": source_claim_ids,
            "evidence_by_pass": evidence_by_pass,
            "axis_evidence_by_pass": axis_evidence_by_pass,
            "field_evidence_by_pass": field_evidence_by_pass,
            "assertion_identities_by_pass": {
                str(pass_number): claim["assertion_identity"]
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
            "transcription_identities_by_pass": {
                str(pass_number): claim["transcription_identity"]
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
            "transcription_cores_by_pass": {
                str(pass_number): claim["transcription_core"]
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
            "checker_objects_by_pass": {
                str(pass_number): project_v3_checker_input(claim["checker_core"])
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
            "checker_input_schema_version": V3_CHECKER_INPUT_VERSION,
            "canonicalization_by_pass": {
                str(pass_number): claim["canonicalization"]
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
        }
        if support_count < threshold:
            below_threshold.append(
                {
                    **base,
                    "field_values_by_pass": {
                        str(pass_number): {
                            field: claim[field] for field in voted_fields
                        }
                        for pass_number, claim in sorted(
                            occurrence_by_pass.items()
                        )
                    },
                }
            )
            continue
        field_consensus = {
            field: field_vote(
                {
                    pass_number: claim[field]
                    for pass_number, claim in occurrence_by_pass.items()
                },
                threshold,
            )
            for field in voted_fields
        }
        if (
            "specificity" in field_consensus
            and (
                status_partition != "positive_possible"
                or base["mathematical_core"]["kind"] in independent_kinds
                or base["frame_only"]
            )
        ):
            field_consensus["specificity"] = specificity_floor_vote(
                field_consensus["specificity"]
            )
        agreed.append({**base, "field_consensus": field_consensus})

    # Engine 3.1.5 (three-pass tiebreak round): partition below-threshold
    # claims by MAJORITY OMISSION with span-cluster protection. A claim
    # transcribed by too few passes is OUTVOTED once at least `threshold`
    # passes read the same sources and did not transcribe its identity —
    # UNLESS its evidence anchors overlap those of below-threshold claims
    # from other passes such that the overlapping cluster spans >= threshold
    # passes. That cluster is one disputed passage read as different
    # mathematical kinds (a real object with fractured transcription, e.g.
    # counter_projection vs call_measure for the same argument), and it must
    # stay UNRESOLVED, fail-closed: rejecting it can flip a row to a false
    # decided verdict when the disputed passage contains the session's valid
    # construction. With two passes nothing is ever rejected (a 1-1 split is
    # the tie the tiebreak pass exists to break).
    def _claim_spans(item: dict[str, Any]) -> list[tuple[str, int, int]]:
        spans = []
        for anchors in (item.get("evidence_by_pass") or {}).values():
            for bound in anchors or []:
                start = bound.get("start")
                end = bound.get("end")
                if isinstance(start, int) and isinstance(end, int):
                    spans.append((str(bound.get("source_id")), start, end))
        return spans

    def _spans_overlap(
        left: list[tuple[str, int, int]],
        right: list[tuple[str, int, int]],
    ) -> bool:
        return any(
            ls == rs and lstart < rend and rstart < lend
            for ls, lstart, lend in left
            for rs, rstart, rend in right
        )

    cluster_ids = list(range(len(below_threshold)))

    def _find(index: int) -> int:
        while cluster_ids[index] != index:
            cluster_ids[index] = cluster_ids[cluster_ids[index]]
            index = cluster_ids[index]
        return index

    all_spans = [_claim_spans(item) for item in below_threshold]
    for i in range(len(below_threshold)):
        for j in range(i + 1, len(below_threshold)):
            if _spans_overlap(all_spans[i], all_spans[j]):
                cluster_ids[_find(i)] = _find(j)
    cluster_passes: dict[int, set[int]] = {}
    for i, item in enumerate(below_threshold):
        cluster_passes.setdefault(_find(i), set()).update(
            item.get("supporting_passes") or []
        )
    for i, item in enumerate(below_threshold):
        outvoted = (
            len(records_by_pass) - item["support_count"] >= threshold
        )
        contested_span = len(cluster_passes[_find(i)]) >= threshold
        if outvoted and not contested_span:
            minority_rejected.append(
                {
                    **item,
                    "reason": "mathematical_core_outvoted_by_majority",
                }
            )
        elif outvoted:
            unresolved.append(
                {
                    **item,
                    "reason": "kind_disagreement_same_span_across_majority",
                }
            )
        else:
            unresolved.append(
                {
                    **item,
                    "reason": "mathematical_core_below_consensus_threshold",
                }
            )

    primary = field_vote(
        {
            pass_number: _primary_vote_value(record, merged_key_remap)
            for pass_number, record in records_by_pass.items()
        },
        threshold,
    )

    # Preserve complete transcription disagreement, but separate it from the
    # subset that can change witness scoring. The first live v3 round showed
    # that mentioned/hypothetical/failed-contrast breadth was turning telemetry
    # into gate abstention. V3.1 publishes both views instead of discarding one.
    unresolved_fields = sum(
        1
        for claim in agreed
        for field in claim["field_consensus"].values()
        if field["status"] != "agreed"
    )
    checker_disagreements = sum(
        claim["checker_input_consensus"]["status"] != "agreed"
        for claim in agreed
    )
    # Consensus semantics 3.3.0. The subset of that raw count that CANNOT move
    # a verdict. For a contract-derived kind the pinned decision consumes only
    # the contract's structured rule table. For a frame-only kind the registry
    # declares that no mathematical object was stated and scoring always emits
    # NO_CONCRETE_WITNESS. In either case a free-text checker dispute cannot
    # move the outcome. The raw count above is still published and still
    # carried by `full_unresolved_count`; only the power to GATE is removed.
    checker_disagreements_verdict_irrelevant = sum(
        claim["checker_input_consensus"]["status"] != "agreed"
        and checker_input_is_verdict_irrelevant(claim)
        for claim in agreed
    )
    unsupported_claims = sum(
        not claim["canonicalization_supported"] for claim in agreed
    )
    full_unresolved_count = (
        len(unresolved)
        + unresolved_fields
        + checker_disagreements
        + int(primary["status"] != "agreed")
        + int(record_status["status"] != "agreed")
        + int(coverage_status["status"] != "agreed")
    )

    unresolved_positive_cores = sum(
        claim["status_partition"] == "positive_possible" for claim in unresolved
    )
    unresolved_negative_cores = sum(
        claim["status_partition"] == "negative_only" for claim in unresolved
    )
    unresolved_telemetry_cores = sum(
        claim["status_partition"] == "telemetry_only" for claim in unresolved
    )
    unresolved_unclassified_cores = (
        len(unresolved)
        - unresolved_positive_cores
        - unresolved_negative_cores
        - unresolved_telemetry_cores
    )

    positive_agreed: list[dict[str, Any]] = []
    positive_axis_unresolved = 0
    positive_checker_input_unresolved = 0
    positive_checker_input_verdict_irrelevant = 0
    open_positive_nonconcrete = 0
    open_positive_checker_unsupported = 0
    polar_axis_unresolved = 0
    telemetry_axis_unresolved = 0
    role_target_unresolved = 0
    for claim in agreed:
        field_consensus = claim["field_consensus"]
        status_vote = field_consensus["claim_status"]
        statuses = set(claim["observed_claim_statuses"])
        is_positive_agreed = (
            status_vote["status"] == "agreed"
            and status_vote["value"] == "claimed_valid"
        )
        if is_positive_agreed:
            positive_agreed.append(claim)
            specificity_vote = field_consensus["specificity"]
            if specificity_vote["status"] != "agreed":
                positive_axis_unresolved += 1
            elif specificity_vote["value"] != "concrete":
                open_positive_nonconcrete += 1
            elif claim["checker_input_consensus"]["status"] != "agreed":
                if checker_input_is_verdict_irrelevant(claim):
                    positive_checker_input_verdict_irrelevant += 1
                else:
                    positive_checker_input_unresolved += 1
            if not claim["canonicalization_supported"]:
                open_positive_checker_unsupported += 1
        elif "claimed_valid" in statuses:
            # Same mathematical core, but commitment itself is disputed.
            positive_axis_unresolved += 1

        if statuses & POLAR_STATUSES:
            polar_axis_unresolved += sum(
                vote["status"] != "agreed"
                for field, vote in field_consensus.items()
                if field in {"claim_status", "specificity"}
            )
        else:
            telemetry_axis_unresolved += sum(
                vote["status"] != "agreed"
                for vote in field_consensus.values()
            )
        role_target_unresolved += sum(
            field_consensus[field]["status"] != "agreed"
            for field in ("answer_role", "claimed_target")
            if field in field_consensus
        )

    infrastructure_unresolved = (
        int(record_status["status"] != "agreed")
        + int(coverage_status["status"] != "agreed")
    )
    scoring_unresolved_count = (
        unresolved_positive_cores
        + positive_axis_unresolved
        + positive_checker_input_unresolved
        + infrastructure_unresolved
    )
    behavior_unresolved_count = (
        unresolved_positive_cores
        + unresolved_negative_cores
        + polar_axis_unresolved
        + infrastructure_unresolved
    )
    telemetry_unresolved_count = (
        unresolved_telemetry_cores + telemetry_axis_unresolved
    )
    # Consensus semantics 3.2.0, scoring-core gating: ONLY the scoring core
    # decides whether a session is open. A below-threshold core that no pass
    # ever claimed valid (negative_only) and one that no pass asserted at all
    # (telemetry_only) cannot change a witness verdict, so by themselves they
    # must not abstain the row and must not spend a tiebreak pass. They stay
    # recorded in `unresolved_claims` and in every published count; only their
    # power to GATE is removed. Everything a resolved reading could still move
    # (positive cores, field votes on agreed claims, checker input, primary,
    # record and coverage status) keeps its full gating weight, and an
    # `unclassified` partition keeps it too, fail-closed.
    #
    # 3.3.0 adds one member to that same class: a checker-input dispute on a
    # contract-derived or registry-frame-only kind. A third pass could resolve
    # the free text and the verdict would not move, so it must not spend a
    # tiebreak pass either.
    tiebreak_unresolved_count = (
        full_unresolved_count
        - unresolved_negative_cores
        - unresolved_telemetry_cores
        - checker_disagreements_verdict_irrelevant
    )

    if require_independence and independence_warnings:
        gate_status = "provisional_nonindependent"
    elif not positive_agreed:
        gate_status = "abstain" if scoring_unresolved_count else "no_claims"
    elif scoring_unresolved_count:
        gate_status = "partial_consensus"
    else:
        gate_status = "full_consensus"

    result = {
        "consensus_schema_version": V3_CONSENSUS,
        "consensus_semantics_version": V3_CONSENSUS_SEMANTICS,
        "contract": first["contract"],
        "policy_bundle": policy_bundle,
        "run_binding": _run_comparison(first["run_binding"]),
        "session": first["session"],
        "lineage": {
            "modular_registry_sha256": first["lineage"][
                "modular_registry_sha256"
            ],
            "identity_policy_sha256": first["lineage"][
                "identity_policy_sha256"
            ],
            "consensus_policy_sha256": first["lineage"][
                "consensus_policy_sha256"
            ],
            "boundary_policy_sha256": first["lineage"][
                "boundary_policy_sha256"
            ],
            "run_contract_sha256": first["lineage"][
                "run_contract_sha256"
            ],
            "compiled_record_ids": [
                record["compiled_record_id"]
                for _, record in sorted(records_by_pass.items())
            ],
        },
        "pass_numbers": pass_numbers,
        "threshold": threshold,
        "voted_fields": list(voted_fields),
        "pass_provenance": [
            {
                "pass_number": pass_number,
                "pass_id": record["run_binding"]["pass_id"],
                "extractor_id": record["extractor"]["extractor_id"],
                "extraction_id": record["extractor"]["extraction_id"],
                "compiled_record_id": record["compiled_record_id"],
                "raw_record_sha256": record["lineage"]["raw_record_sha256"],
                "independence_attestation": record["extractor"][
                    "independence_attestation"
                ],
            }
            for pass_number, record in sorted(records_by_pass.items())
        ],
        "independence_warnings": independence_warnings,
        "record_status": record_status,
        "coverage_status": coverage_status,
        "agreed_claims": agreed,
        "unresolved_claims": unresolved,
        "minority_rejected_claims": minority_rejected,
        "minority_rejected_count": len(minority_rejected),
        "primary": primary,
        # Backward-compatible full-fidelity count. It includes telemetry, role,
        # target, and primary disagreements and is never hidden.
        "unresolved_count": full_unresolved_count,
        "full_unresolved_count": full_unresolved_count,
        # Verdict-bearing witness consensus. This is the only count used for
        # the gate lane and mathematical row closure.
        "scoring_unresolved_count": scoring_unresolved_count,
        "behavior_unresolved_count": behavior_unresolved_count,
        "telemetry_unresolved_count": telemetry_unresolved_count,
        # Tiebreak-relevant fidelity: the full count minus the unresolved cores
        # that cannot move a verdict. Published beside the full count so the
        # difference is always auditable, never inferred.
        "tiebreak_unresolved_count": tiebreak_unresolved_count,
        "role_target_unresolved_count": role_target_unresolved,
        "primary_unresolved_count": int(primary["status"] != "agreed"),
        "unresolved_positive_core_count": unresolved_positive_cores,
        "unresolved_negative_core_count": unresolved_negative_cores,
        "unresolved_telemetry_core_count": unresolved_telemetry_cores,
        "unresolved_unclassified_core_count": unresolved_unclassified_cores,
        # Checker-input channel, published raw and decomposed: the total number
        # of agreed claims whose checker input did not reach consensus, and the
        # subset of those whose kind is contract-derived or frame-only and
        # therefore cannot change a verdict. Nothing is hidden; the second
        # number is exactly the amount by which scoring and tiebreak counts
        # were reduced. Each agreed claim publishes its `frame_only` fact.
        "checker_input_unresolved_count": checker_disagreements,
        "checker_input_verdict_irrelevant_count": (
            checker_disagreements_verdict_irrelevant
        ),
        "positive_checker_input_unresolved_count": (
            positive_checker_input_unresolved
        ),
        "positive_checker_input_verdict_irrelevant_count": (
            positive_checker_input_verdict_irrelevant
        ),
        "positive_agreed_claim_count": len(positive_agreed),
        "merged_claim_count": merged_claim_count,
        "open_positive_nonconcrete_count": open_positive_nonconcrete,
        "open_positive_checker_unsupported_count": open_positive_checker_unsupported,
        "unsupported_agreed_claim_count": unsupported_claims,
        "transcription_status": (
            "full_consensus" if full_unresolved_count == 0
            else "partial_consensus" if agreed
            else "abstain"
        ),
        "gate_status": gate_status,
        "tiebreak_required": len(records) == 2 and scoring_unresolved_count > 0,
        "full_tiebreak_recommended": (
            len(records) == 2 and tiebreak_unresolved_count > 0
        ),
    }
    result["consensus_row_sha256"] = canonical_sha256(result)
    return result


def gate_dataset_v3(
    compiled_records: list[dict[str, Any]],
    *,
    input_independent_kinds: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not compiled_records:
        raise ValueError("no compiled records supplied")
    contracts = {
        canonical_sha256(record["contract"]) for record in compiled_records
    }
    runs = {
        record["run_binding"]["run_contract_sha256"]
        for record in compiled_records
    }
    policies = {
        canonical_sha256(record.get("policy_bundle"))
        for record in compiled_records
    }
    if len(contracts) != 1:
        raise ValueError("dataset contains multiple contract bindings")
    if len(runs) != 1:
        raise ValueError("dataset contains multiple run contracts")
    if len(policies) != 1:
        raise ValueError("dataset contains multiple policy bundles")

    first = compiled_records[0]
    policy_bundle = first["policy_bundle"]
    consensus_policy = policy_bundle["consensus"]
    allowed = _allowed_pass_sets(consensus_policy)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in compiled_records:
        grouped[record["session"]["session_slug"]].append(record)
    rows: list[dict[str, Any]] = []
    for slug, records in sorted(grouped.items()):
        passes = sorted(
            record["extractor"]["pass_number"] for record in records
        )
        if tuple(passes) not in allowed:
            row = {
                "consensus_schema_version": V3_CONSENSUS,
                "consensus_semantics_version": V3_CONSENSUS_SEMANTICS,
                "contract": records[0]["contract"],
                "policy_bundle": policy_bundle,
                "run_binding": _run_comparison(records[0]["run_binding"]),
                "session": records[0]["session"],
                "pass_numbers": passes,
                "gate_status": "invalid_or_missing_passes",
                "unresolved_count": 1,
                "full_unresolved_count": 1,
                "scoring_unresolved_count": 1,
                "behavior_unresolved_count": 1,
                "telemetry_unresolved_count": 0,
                "tiebreak_unresolved_count": 1,
                "role_target_unresolved_count": 0,
                "primary_unresolved_count": 0,
                "unresolved_positive_core_count": 0,
                "unresolved_negative_core_count": 0,
                "unresolved_telemetry_core_count": 0,
                "unresolved_unclassified_core_count": 0,
                "checker_input_unresolved_count": 0,
                "checker_input_verdict_irrelevant_count": 0,
                "positive_checker_input_unresolved_count": 0,
                "positive_checker_input_verdict_irrelevant_count": 0,
                "positive_agreed_claim_count": 0,
                "merged_claim_count": 0,
                "open_positive_nonconcrete_count": 0,
                "open_positive_checker_unsupported_count": 0,
                "tiebreak_required": False,
                "full_tiebreak_recommended": False,
                "reason": "pass set is outside the bound consensus policy",
                "agreed_claims": [],
                "unresolved_claims": [],
            }
            row["consensus_row_sha256"] = canonical_sha256(row)
            rows.append(row)
            continue
        rows.append(
            gate_records_v3(
                records, input_independent_kinds=input_independent_kinds
            )
        )
    counts = Counter(row["gate_status"] for row in rows)
    report = {
        "gate_report_version": V3_GATE_REPORT,
        "consensus_semantics_version": V3_CONSENSUS_SEMANTICS,
        "contract": first["contract"],
        "policy_bundle": policy_bundle,
        "run_contract_sha256": next(iter(runs)),
        "consensus_policy_sha256": canonical_sha256(consensus_policy),
        "boundary_policy_sha256": canonical_sha256(
            policy_bundle["boundary"]
        ),
        "input_compiled_record_ids": sorted(
            record["compiled_record_id"] for record in compiled_records
        ),
        "record_count": len(compiled_records),
        "session_count": len(rows),
        "gate_status_counts": dict(sorted(counts.items())),
        "unresolved_total": sum(row["unresolved_count"] for row in rows),
        "full_unresolved_total": sum(row["full_unresolved_count"] for row in rows),
        "scoring_unresolved_total": sum(
            row["scoring_unresolved_count"] for row in rows
        ),
        "behavior_unresolved_total": sum(
            row["behavior_unresolved_count"] for row in rows
        ),
        "telemetry_unresolved_total": sum(
            row["telemetry_unresolved_count"] for row in rows
        ),
        "tiebreak_unresolved_total": sum(
            row["tiebreak_unresolved_count"]
            for row in rows
        ),
        "merged_claim_total": sum(
            row["merged_claim_count"] for row in rows
        ),
        "checker_input_unresolved_total": sum(
            row["checker_input_unresolved_count"] for row in rows
        ),
        "checker_input_verdict_irrelevant_total": sum(
            row["checker_input_verdict_irrelevant_count"]
            for row in rows
        ),
        "tiebreak_session_slugs": [
            row["session"]["session_slug"]
            for row in rows
            if row["tiebreak_required"]
        ],
        "full_tiebreak_recommended_session_slugs": [
            row["session"]["session_slug"]
            for row in rows
            if row["full_tiebreak_recommended"]
        ],
        "rows": rows,
    }
    report["gate_report_sha256"] = canonical_sha256(report)
    return report
