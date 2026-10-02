from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .common import canonical_sha256, content_id

V2_COMPILED_SCHEMA_VERSION = "tgc-compiled-record/2.0.0"
V3_COMPILED_SCHEMA_VERSION = "tgc-compiled-record/3.0.0"


def _compiled_schema_version(records: list[dict[str, Any]]) -> str:
    if not records:
        raise ValueError("consensus requires at least one compiled record")
    versions = {record.get("compiled_schema_version") for record in records}
    if len(versions) != 1:
        rendered = sorted(repr(version) for version in versions)
        raise ValueError(
            "cannot mix compiled record schema versions in one consensus input: "
            f"{rendered}"
        )
    version = next(iter(versions))
    if version not in {V2_COMPILED_SCHEMA_VERSION, V3_COMPILED_SCHEMA_VERSION}:
        raise ValueError(f"unsupported compiled record schema version {version!r}")
    return version


def _threshold(pass_count: int) -> int:
    if pass_count not in {2, 3}:
        raise ValueError(f"consensus requires exactly 2 or 3 passes, found {pass_count}")
    return 2


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


def _claim_key(claim: dict[str, Any]) -> tuple[str, int]:
    return claim["canonical_identity"], int(claim["occurrence"])


def _primary_vote_value(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": record["primary"]["status"],
        "canonical_identities": sorted(record["primary"]["canonical_identities"]),
    }


def gate_records(
    records: list[dict[str, Any]],
    *,
    require_independence: bool = True,
) -> dict[str, Any]:
    schema_version = _compiled_schema_version(records)
    if schema_version == V3_COMPILED_SCHEMA_VERSION:
        from .consensus_v3 import gate_records_v3

        return gate_records_v3(
            records, require_independence=require_independence
        )
    records_by_pass: dict[int, dict[str, Any]] = {}
    for record in records:
        pass_number = record["extractor"]["pass_number"]
        if pass_number in records_by_pass:
            raise ValueError(f"duplicate pass number {pass_number}")
        records_by_pass[pass_number] = record
    pass_numbers = sorted(records_by_pass)
    if pass_numbers not in ([1, 2], [1, 2, 3]):
        raise ValueError(f"expected pass set [1,2] or [1,2,3], found {pass_numbers}")
    threshold = _threshold(len(records))

    first = records[0]
    for record in records[1:]:
        if record["contract"] != first["contract"]:
            raise ValueError("contract bindings differ across passes")
        if record["session"] != first["session"]:
            raise ValueError("session bindings differ across passes")

    extractor_ids = [record["extractor"]["extractor_id"] for record in records]
    run_ids = [record["extractor"]["run_id"] for record in records]
    independence_warnings: list[str] = []
    if len(set(extractor_ids)) != len(extractor_ids):
        independence_warnings.append("extractor_id_reused_across_passes")
    if len(set(run_ids)) != len(run_ids):
        independence_warnings.append("run_id_reused_across_passes")
    if not all(record["extractor"]["independence_attestation"] for record in records):
        independence_warnings.append("one_or_more_passes_lack_independence_attestation")

    record_status = field_vote(
        {pass_number: record["record_status"] for pass_number, record in records_by_pass.items()},
        threshold,
    )

    grouped: dict[tuple[str, int], dict[int, dict[str, Any]]] = defaultdict(dict)
    for pass_number, record in records_by_pass.items():
        for claim in record["claims"]:
            grouped[_claim_key(claim)][pass_number] = claim

    agreed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for key in sorted(grouped):
        occurrence_by_pass = grouped[key]
        support_count = len(occurrence_by_pass)
        representative = occurrence_by_pass[min(occurrence_by_pass)]
        source_claim_ids = {
            str(pass_number): claim["claim_id"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        evidence_by_pass = {
            str(pass_number): claim["evidence"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        field_evidence_by_pass = {
            str(pass_number): claim["field_evidence"]
            for pass_number, claim in sorted(occurrence_by_pass.items())
        }
        base = {
            "consensus_claim_id": content_id(
                "consensus",
                {"identity": key[0], "occurrence": key[1]},
            ),
            "canonical_identity": key[0],
            "checker_equivalence_identity": representative["checker_equivalence_identity"],
            "occurrence": key[1],
            "core": representative["core"],
            "checker_core": representative["checker_core"],
            "representative_checker_object": representative["checker_object"],
            "canonicalization_supported": all(
                claim["canonicalization"]["supported"]
                for claim in occurrence_by_pass.values()
            ),
            "support_count": support_count,
            "supporting_passes": sorted(occurrence_by_pass),
            "source_claim_ids": source_claim_ids,
            "evidence_by_pass": evidence_by_pass,
            "field_evidence_by_pass": field_evidence_by_pass,
            "canonicalization_by_pass": {
                str(pass_number): claim["canonicalization"]
                for pass_number, claim in sorted(occurrence_by_pass.items())
            },
        }
        if support_count < threshold:
            unresolved.append(
                {
                    **base,
                    "field_values_by_pass": {
                        str(pass_number): {
                            "claim_status": claim["claim_status"],
                            "answer_role": claim["answer_role"],
                        }
                        for pass_number, claim in sorted(occurrence_by_pass.items())
                    },
                    "reason": "core_below_consensus_threshold",
                }
            )
            continue
        claim_status = field_vote(
            {
                pass_number: claim["claim_status"]
                for pass_number, claim in occurrence_by_pass.items()
            },
            threshold,
        )
        answer_role = field_vote(
            {
                pass_number: claim["answer_role"]
                for pass_number, claim in occurrence_by_pass.items()
            },
            threshold,
        )
        agreed.append(
            {
                **base,
                "field_consensus": {
                    "claim_status": claim_status,
                    "answer_role": answer_role,
                },
            }
        )

    primary = field_vote(
        {
            pass_number: _primary_vote_value(record)
            for pass_number, record in records_by_pass.items()
        },
        threshold,
    )

    unresolved_fields = sum(
        1
        for claim in agreed
        for field in claim["field_consensus"].values()
        if field["status"] != "agreed"
    )
    unresolved_count = (
        len(unresolved)
        + unresolved_fields
        + int(primary["status"] != "agreed")
        + int(record_status["status"] != "agreed")
    )
    if require_independence and independence_warnings:
        gate_status = "provisional_nonindependent"
    elif unresolved_count == 0:
        valid_claims = [
            claim
            for claim in agreed
            if claim["field_consensus"]["claim_status"].get("value") == "claimed_valid"
        ]
        gate_status = "no_claims" if not valid_claims else "full_consensus"
    elif agreed:
        gate_status = "partial_consensus"
    else:
        gate_status = "abstain"

    return {
        "consensus_schema_version": "tgc-consensus/2.0.0",
        "contract": first["contract"],
        "session": first["session"],
        "pass_numbers": pass_numbers,
        "threshold": threshold,
        "pass_provenance": [
            {
                "pass_number": pass_number,
                "extractor_id": record["extractor"]["extractor_id"],
                "run_id": record["extractor"]["run_id"],
                "compiled_record_id": record["compiled_record_id"],
                "independence_attestation": record["extractor"]["independence_attestation"],
            }
            for pass_number, record in sorted(records_by_pass.items())
        ],
        "independence_warnings": independence_warnings,
        "record_status": record_status,
        "agreed_claims": agreed,
        "unresolved_claims": unresolved,
        "primary": primary,
        "unresolved_count": unresolved_count,
        "gate_status": gate_status,
        "tiebreak_required": len(records) == 2 and unresolved_count > 0,
    }


def gate_dataset(compiled_records: list[dict[str, Any]]) -> dict[str, Any]:
    schema_version = _compiled_schema_version(compiled_records)
    if schema_version == V3_COMPILED_SCHEMA_VERSION:
        from .consensus_v3 import gate_dataset_v3

        return gate_dataset_v3(compiled_records)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in compiled_records:
        grouped[record["session"]["session_slug"]].append(record)
    rows: list[dict[str, Any]] = []
    for slug, records in sorted(grouped.items()):
        passes = sorted(record["extractor"]["pass_number"] for record in records)
        if passes not in ([1, 2], [1, 2, 3]):
            rows.append(
                {
                    "consensus_schema_version": "tgc-consensus/2.0.0",
                    "session": records[0]["session"],
                    "pass_numbers": passes,
                    "gate_status": "invalid_or_missing_passes",
                    "unresolved_count": 1,
                    "tiebreak_required": False,
                    "reason": "valid pass set must be [1,2] or [1,2,3]",
                    "agreed_claims": [],
                    "unresolved_claims": [],
                }
            )
            continue
        rows.append(gate_records(records))
    counts = Counter(row["gate_status"] for row in rows)
    return {
        "gate_report_version": "tgc-gate-report/2.0.0",
        "record_count": len(compiled_records),
        "session_count": len(rows),
        "gate_status_counts": dict(sorted(counts.items())),
        "unresolved_total": sum(row["unresolved_count"] for row in rows),
        "tiebreak_session_slugs": [
            row["session"]["session_slug"]
            for row in rows
            if row.get("tiebreak_required")
        ],
        "rows": rows,
    }
