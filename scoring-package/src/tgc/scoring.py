from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CheckerResult:
    verdict: str
    compliant: bool
    detail: str
    certificate: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "compliant": self.compliant,
            "detail": self.detail,
            "certificate": self.certificate,
        }


Checker = Callable[[dict[str, Any]], CheckerResult]

METRICS = (
    "has_valid_witness",
    "has_valid_compliant_witness",
    "primary_valid",
    "all_asserted_valid",
    "exclusive_compliance",
)

V2_CONSENSUS_SCHEMA_VERSION = "tgc-consensus/2.0.0"
V3_CONSENSUS_SCHEMA_VERSION = "tgc-consensus/3.0.0"
V2_GATE_REPORT_VERSION = "tgc-gate-report/2.0.0"
V3_GATE_REPORT_VERSION = "tgc-gate-report/3.0.0"


def _tri(yes: bool, no: bool) -> str:
    return "yes" if yes else ("no" if no else "unknown")


def score_consensus_row(
    row: dict[str, Any],
    checker: Checker,
    *,
    allow_early_v3_replay: bool = False,
    early_v3_replay_reason: str | None = None,
) -> dict[str, Any]:
    schema_version = row.get("consensus_schema_version")
    if schema_version == V3_CONSENSUS_SCHEMA_VERSION:
        from .scoring_v3 import score_consensus_row_v3

        return score_consensus_row_v3(
            row,
            checker,
            allow_early_v3_replay=allow_early_v3_replay,
            early_v3_replay_reason=early_v3_replay_reason,
        )
    if schema_version != V2_CONSENSUS_SCHEMA_VERSION:
        raise ValueError(f"unsupported consensus schema version {schema_version!r}")
    if allow_early_v3_replay or early_v3_replay_reason is not None:
        raise ValueError("early-v3 replay authorization cannot be used on v2")
    output: dict[str, Any] = {
        "lane": "",
        "detail": "",
        "outcomes": [],
        **{metric: "unknown" for metric in METRICS},
    }

    record_status = row.get("record_status", {})
    if record_status.get("status") == "agreed" and record_status.get("value") != "complete":
        output["lane"] = "BadSession"
        output["detail"] = f"record_status[{record_status.get('value')}]"
        for metric in METRICS:
            output[metric] = "bad_session"
        return output

    gate_status = row.get("gate_status")
    if gate_status == "provisional_nonindependent":
        output["lane"] = "ProvisionalNonIndependent"
        output["detail"] = "gate[independence_not_established]"
        return output
    if gate_status in {"abstain", "invalid_or_missing_passes"}:
        output["lane"] = "GateAbstain"
        output["detail"] = f"gate[{gate_status}]"
        return output

    positive_claims = [
        claim
        for claim in row.get("agreed_claims", [])
        if claim.get("field_consensus", {}).get("claim_status", {}).get("status") == "agreed"
        and claim["field_consensus"]["claim_status"].get("value") == "claimed_valid"
    ]
    if not positive_claims and row.get("unresolved_count", 0) == 0:
        output["lane"] = "NoWitness"
        output["detail"] = "no_consensus_claimed_valid_construction"
        for metric in METRICS:
            output[metric] = "no_witness"
        return output

    outcomes: list[dict[str, Any]] = []
    for claim in positive_claims:
        if not claim.get("canonicalization_supported", False):
            result = CheckerResult(
                "UNKNOWN",
                False,
                "canonicalization_unsupported",
                None,
            )
        else:
            result = checker(claim)
            if result.verdict not in {"PASS", "REFUTED", "UNKNOWN"}:
                raise ValueError(f"checker returned invalid verdict {result.verdict!r}")
            if result.verdict == "PASS" and result.certificate is None:
                raise ValueError("PASS requires a machine-readable certificate")
            if result.verdict == "REFUTED" and result.certificate is None:
                raise ValueError("REFUTED requires a concrete witness/certificate")
        outcomes.append(
            {
                "consensus_claim_id": claim["consensus_claim_id"],
                "canonical_identity": claim["canonical_identity"],
                "kind": claim["core"]["kind"],
                **result.as_dict(),
            }
        )

    passes = [outcome for outcome in outcomes if outcome["verdict"] == "PASS"]
    refuted = [outcome for outcome in outcomes if outcome["verdict"] == "REFUTED"]
    unknown = [outcome for outcome in outcomes if outcome["verdict"] == "UNKNOWN"]
    compliant = [outcome for outcome in passes if outcome["compliant"]]
    closed = int(row.get("unresolved_count", 0)) == 0

    output["has_valid_witness"] = _tri(
        bool(passes),
        closed and bool(outcomes) and not passes and not unknown,
    )
    output["has_valid_compliant_witness"] = _tri(
        bool(compliant),
        closed and bool(outcomes) and not compliant and not unknown,
    )
    output["all_asserted_valid"] = _tri(
        closed and bool(outcomes) and not refuted and not unknown,
        bool(refuted),
    )
    output["exclusive_compliance"] = (
        "no"
        if refuted or (outcomes and not unknown and len(compliant) != len(outcomes))
        else (
            "yes"
            if closed and outcomes and len(compliant) == len(outcomes)
            else "unknown"
        )
    )

    primary = row.get("primary", {})
    if primary.get("status") == "agreed":
        value = primary.get("value") or {}
        status = value.get("status")
        identities = value.get("canonical_identities") or []
        if status == "none":
            output["primary_valid"] = "no_primary"
        elif status in {"single", "coequal"} and identities:
            primary_outcomes = [
                outcome
                for outcome in outcomes
                if outcome["canonical_identity"] in identities
            ]
            primary_passes = [item for item in primary_outcomes if item["verdict"] == "PASS"]
            primary_unknown = [item for item in primary_outcomes if item["verdict"] == "UNKNOWN"]
            primary_refuted = [item for item in primary_outcomes if item["verdict"] == "REFUTED"]
            # Coequal primary routes are alternative sufficient routes: one certified
            # route validates the answer's primary set; "no" requires every route
            # present, closed, and concretely refuted.
            output["primary_valid"] = _tri(
                bool(primary_passes),
                closed
                and len(primary_outcomes) == len(identities)
                and bool(primary_outcomes)
                and not primary_passes
                and not primary_unknown
                and len(primary_refuted) == len(primary_outcomes),
            )
        else:
            output["primary_valid"] = "unknown"
    else:
        output["primary_valid"] = "unknown"

    if passes:
        output["lane"] = "CertifiedValid"
    elif outcomes and closed and not unknown and refuted:
        output["lane"] = "CertifiedRefuted"
    else:
        output["lane"] = "CheckerUnknown"
    output["detail"] = ";".join(item["detail"] for item in outcomes)[:1000]
    if row.get("unresolved_count"):
        output["detail"] += f"|unresolved={row['unresolved_count']}"
    output["outcomes"] = outcomes
    return output


def score_gate_report(
    report: dict[str, Any],
    checker: Checker,
    *,
    checker_binding: dict[str, Any] | None = None,
    boundary_policy_override: dict[str, Any] | None = None,
    allow_contract_substitution: bool = False,
    contract_substitution_reason: str | None = None,
    allow_early_v3_replay: bool = False,
    early_v3_replay_reason: str | None = None,
) -> dict[str, Any]:
    report_version = report.get("gate_report_version")
    if report_version == V3_GATE_REPORT_VERSION:
        from .scoring_v3 import score_gate_report_v3

        return score_gate_report_v3(
            report,
            checker,
            checker_binding=checker_binding,
            boundary_policy_override=boundary_policy_override,
            allow_contract_substitution=allow_contract_substitution,
            contract_substitution_reason=contract_substitution_reason,
            allow_early_v3_replay=allow_early_v3_replay,
            early_v3_replay_reason=early_v3_replay_reason,
        )
    if report_version != V2_GATE_REPORT_VERSION:
        raise ValueError(f"unsupported gate report version {report_version!r}")
    if (
        boundary_policy_override is not None
        or allow_contract_substitution
        or contract_substitution_reason is not None
        or allow_early_v3_replay
        or early_v3_replay_reason is not None
    ):
        raise ValueError(
            "contract, boundary-policy, or early-replay override is a v3 scoring feature; "
            "this gate report is not v3"
        )
    rows = [
        {**row, **score_consensus_row(row, checker)}
        for row in report.get("rows", [])
    ]
    lane_counts = Counter(row["lane"] for row in rows)
    metric_counts = {
        metric: dict(sorted(Counter(row[metric] for row in rows).items()))
        for metric in METRICS
    }
    return {
        "score_report_version": "tgc-score-report/2.0.0",
        "session_count": len(rows),
        "lane_counts": dict(sorted(lane_counts.items())),
        "metric_counts": metric_counts,
        "rows": rows,
    }
