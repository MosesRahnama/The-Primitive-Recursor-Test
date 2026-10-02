from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import (
    canonical_sha256,
    engine_implementation_sha256,
    read_json,
    sha256_file,
    sha256_text,
    write_json_atomic,
    write_text_atomic,
)

AUDIT_VERSION = "tgc-permutation-stability-audit/1.1.0"
POLICY_VERSION = "tgc-permutation-stability-policy/1.1.0"
GATE_REPORT_VERSION = "tgc-gate-report/3.0.0"
SCORE_REPORT_VERSION = "tgc-score-report/3.0.0"

# This is the scoring engine's existing decided-lane boundary.  The audit does
# not reinterpret or widen it: scoring_v3 attaches abstention evidence to every
# other lane.
DECIDED_LANES = frozenset({"CertifiedValid", "CertifiedRefuted", "NoWitness"})
EXPECTED_PAIRS = ((1, 2), (1, 3), (2, 3))
TRIPLE = (1, 2, 3)

AUDIT_POLICY = {
    "policy_version": POLICY_VERSION,
    "decided_lanes": sorted(DECIDED_LANES),
    "pair_abstained_or_partial": (
        "pair gate_status is not full_consensus or pair score lane is not a decided lane"
    ),
    "extraction_unstable": (
        "at least one pair gate_status is not full_consensus or pair score lanes differ"
    ),
    "decision_unstable": (
        "at least one pair score lane is not a decided lane or pair score lanes differ"
    ),
    "pairwise_lane_divergence": "the three pair score lanes are not identical",
    "triple_pair_divergence": "the triple score lane differs from at least one pair lane",
    "flag": (
        "a pair or triple gate is non-full, a pair or triple score is non-decided, "
        "or any pair/triple lanes differ"
    ),
    "effect": "audit telemetry only; never changes a gate, score, lane, or consensus object",
}

CSV_COLUMNS = (
    "session_slug",
    "triple_gate_status",
    "triple_lane",
    "triple_resolved",
    "triple_gate_nonfull",
    "triple_score_nondecided",
    "p1_p2_gate_status",
    "p1_p2_lane",
    "p1_p3_gate_status",
    "p1_p3_lane",
    "p2_p3_gate_status",
    "p2_p3_lane",
    "any_pair_gate_nonfull",
    "any_pair_score_nondecided",
    "any_pair_abstained_or_partial",
    "pairwise_lanes_differ",
    "triple_lane_differs_from_pairs",
    "extraction_unstable",
    "decision_unstable",
    "pairwise_unstable",
    "flagged",
    "flag_reasons",
    "row_sha256",
)


@dataclass(frozen=True)
class _LoadedReport:
    report: dict[str, Any]
    report_sha256: str
    file_sha256: str
    rows: dict[str, dict[str, Any]]
    pass_numbers: tuple[int, ...]


@dataclass(frozen=True)
class _ReportBundle:
    gate: _LoadedReport
    score: _LoadedReport


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _verify_hash_closed(value: dict[str, Any], hash_field: str, label: str) -> str:
    declared = value.get(hash_field)
    if not isinstance(declared, str) or not declared:
        raise ValueError(f"{label} lacks {hash_field}")
    core = dict(value)
    core.pop(hash_field, None)
    observed = canonical_sha256(core)
    if declared != observed:
        raise ValueError(f"{label} hash mismatch: declared {declared}, observed {observed}")
    return declared


def _verify_embedded_binding(
    container: dict[str, Any], object_field: str, hash_field: str, label: str
) -> str:
    value = _require_mapping(container.get(object_field), f"{label} {object_field}")
    declared = container.get(hash_field)
    observed = canonical_sha256(value)
    if declared != observed:
        raise ValueError(f"{label} {hash_field} mismatch: declared {declared}, observed {observed}")
    return observed


def _session_slug(row: dict[str, Any], label: str) -> str:
    session = row.get("session")
    if not isinstance(session, dict):
        raise ValueError(f"{label} lacks a session object")
    slug = session.get("session_slug")
    if not isinstance(slug, str) or not slug:
        raise ValueError(f"{label} lacks session.session_slug")
    return slug


def _index_rows(
    report: dict[str, Any],
    *,
    row_hash_field: str,
    label: str,
    verify_row_hash: bool = True,
    require_row_hash: bool = True,
) -> dict[str, dict[str, Any]]:
    raw_rows = report.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError(f"{label} lacks a rows array")
    if report.get("session_count") != len(raw_rows):
        raise ValueError(f"{label} session_count does not match its rows array")
    rows: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(raw_rows):
        row = _require_mapping(raw_row, f"{label} row {index}")
        slug = _session_slug(row, f"{label} row {index}")
        if slug in rows:
            raise ValueError(f"{label} contains duplicate session {slug}")
        declared_row_hash = row.get(row_hash_field)
        if require_row_hash and (not isinstance(declared_row_hash, str) or not declared_row_hash):
            raise ValueError(f"{label} row {slug} lacks {row_hash_field}")
        if verify_row_hash and isinstance(declared_row_hash, str):
            _verify_hash_closed(row, row_hash_field, f"{label} row {slug}")
        rows[slug] = row
    if not rows:
        raise ValueError(f"{label} contains no sessions")
    return rows


def _pass_set(rows: Iterable[dict[str, Any]], label: str) -> tuple[int, ...]:
    observed: set[tuple[int, ...]] = set()
    for row in rows:
        raw = row.get("pass_numbers")
        if (
            not isinstance(raw, list)
            or not raw
            or any(not isinstance(item, int) or isinstance(item, bool) for item in raw)
        ):
            raise ValueError(f"{label} has invalid pass_numbers")
        passes = tuple(sorted(raw))
        if len(set(passes)) != len(passes):
            raise ValueError(f"{label} has duplicate pass_numbers")
        observed.add(passes)
    if len(observed) != 1:
        raise ValueError(f"{label} mixes pass sets: {sorted(observed)}")
    return next(iter(observed))


def _load_gate(path: Path) -> _LoadedReport:
    report = _require_mapping(read_json(path), f"gate report {path}")
    if report.get("gate_report_version") != GATE_REPORT_VERSION:
        raise ValueError(f"gate report {path} must be {GATE_REPORT_VERSION}")
    report_hash = _verify_hash_closed(report, "gate_report_sha256", f"gate report {path}")
    policy_bundle = _require_mapping(
        report.get("policy_bundle"), f"gate report {path} policy_bundle"
    )
    consensus_policy = _require_mapping(
        policy_bundle.get("consensus"), f"gate report {path} consensus policy"
    )
    if report.get("consensus_policy_sha256") != canonical_sha256(consensus_policy):
        raise ValueError(f"gate report {path} consensus policy binding differs")
    boundary_policy = _require_mapping(
        policy_bundle.get("boundary"), f"gate report {path} boundary policy"
    )
    if report.get("boundary_policy_sha256") != canonical_sha256(boundary_policy):
        raise ValueError(f"gate report {path} boundary policy binding differs")
    rows = _index_rows(
        report,
        row_hash_field="consensus_row_sha256",
        label=f"gate report {path}",
    )
    return _LoadedReport(
        report=report,
        report_sha256=report_hash,
        file_sha256=sha256_file(path),
        rows=rows,
        pass_numbers=_pass_set(rows.values(), f"gate report {path}"),
    )


def _load_score(path: Path) -> _LoadedReport:
    report = _require_mapping(read_json(path), f"score report {path}")
    if report.get("score_report_version") != SCORE_REPORT_VERSION:
        raise ValueError(f"score report {path} must be {SCORE_REPORT_VERSION}")
    report_hash = _verify_hash_closed(report, "score_report_sha256", f"score report {path}")
    lineage = _require_mapping(report.get("lineage"), f"score report {path} lineage")
    for object_field, hash_field in (
        ("boundary_policy", "boundary_policy_sha256"),
        ("checker_binding", "checker_binding_sha256"),
        ("scoring_policy", "scoring_policy_sha256"),
    ):
        _verify_embedded_binding(
            lineage,
            object_field,
            hash_field,
            f"score report {path} lineage",
        )
    rows = _index_rows(
        report,
        row_hash_field="score_row_sha256",
        label=f"score report {path}",
        # score_row_sha256 closes the scorer-produced projection before it is
        # merged with the gate row.  The enclosing score_report_sha256 closes
        # the final rows, while consensus_row_sha256 binds each one to its gate.
        verify_row_hash=False,
        require_row_hash=False,
    )
    return _LoadedReport(
        report=report,
        report_sha256=report_hash,
        file_sha256=sha256_file(path),
        rows=rows,
        pass_numbers=_pass_set(rows.values(), f"score report {path}"),
    )


def _bind(gate: _LoadedReport, score: _LoadedReport, label: str) -> _ReportBundle:
    lineage = _require_mapping(score.report.get("lineage"), f"{label} score lineage")
    if lineage.get("gate_report_sha256") != gate.report_sha256:
        raise ValueError(f"{label} score is not bound to its gate report")
    if score.pass_numbers != gate.pass_numbers:
        raise ValueError(f"{label} gate and score pass sets differ")
    if set(score.rows) != set(gate.rows):
        raise ValueError(f"{label} gate and score session sets differ")
    if lineage.get("run_contract_sha256") != gate.report.get("run_contract_sha256"):
        raise ValueError(f"{label} score and gate run contracts differ")
    if lineage.get("consensus_policy_sha256") != gate.report.get("consensus_policy_sha256"):
        raise ValueError(f"{label} score and gate consensus policies differ")
    for slug in sorted(gate.rows):
        gate_row = gate.rows[slug]
        score_row = score.rows[slug]
        if score_row.get("consensus_row_sha256") != gate_row.get("consensus_row_sha256"):
            raise ValueError(f"{label} session {slug} score is not bound to its gate row")
        if score_row.get("gate_status") != gate_row.get("gate_status"):
            raise ValueError(f"{label} session {slug} gate_status differs in score")
        if canonical_sha256(score_row.get("session")) != canonical_sha256(gate_row.get("session")):
            raise ValueError(f"{label} session {slug} source binding differs in score")
        lane = score_row.get("lane")
        if not isinstance(lane, str) or not lane:
            raise ValueError(f"{label} session {slug} lacks a score lane")
    return _ReportBundle(gate=gate, score=score)


def _uniform(values: Sequence[Any], label: str, *, allow_none: bool = False) -> Any:
    if not allow_none and any(value is None for value in values):
        raise ValueError(f"{label} is missing from at least one report")
    hashes = {canonical_sha256(value) for value in values}
    if len(hashes) != 1:
        raise ValueError(f"{label} differs across reports")
    return values[0]


def _lineage_entry(bundle: _ReportBundle) -> dict[str, Any]:
    score_lineage = bundle.score.report["lineage"]
    return {
        "pass_numbers": list(bundle.gate.pass_numbers),
        "gate": {
            "file_sha256": bundle.gate.file_sha256,
            "gate_report_sha256": bundle.gate.report_sha256,
            "gate_report_version": bundle.gate.report["gate_report_version"],
        },
        "score": {
            "file_sha256": bundle.score.file_sha256,
            "score_report_sha256": bundle.score.report_sha256,
            "score_report_version": bundle.score.report["score_report_version"],
            "gate_report_sha256": score_lineage["gate_report_sha256"],
            "engine_implementation_sha256": score_lineage.get("engine_implementation_sha256"),
        },
    }


def _pair_label(passes: tuple[int, ...]) -> str:
    return "p" + "_p".join(str(item) for item in passes)


def _csv_text(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_COLUMNS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        flattened: dict[str, Any] = {
            "session_slug": row["session_slug"],
            "triple_gate_status": row["triple"]["gate_status"],
            "triple_lane": row["triple"]["lane"],
            "triple_resolved": "yes" if row["triple_resolved"] else "no",
            "triple_gate_nonfull": "yes" if row["triple_gate_nonfull"] else "no",
            "triple_score_nondecided": (
                "yes" if row["triple_score_nondecided"] else "no"
            ),
            "any_pair_gate_nonfull": ("yes" if row["any_pair_gate_nonfull"] else "no"),
            "any_pair_score_nondecided": ("yes" if row["any_pair_score_nondecided"] else "no"),
            "any_pair_abstained_or_partial": (
                "yes" if row["any_pair_abstained_or_partial"] else "no"
            ),
            "pairwise_lanes_differ": ("yes" if row["pairwise_lanes_differ"] else "no"),
            "triple_lane_differs_from_pairs": (
                "yes" if row["triple_lane_differs_from_pairs"] else "no"
            ),
            "extraction_unstable": "yes" if row["extraction_unstable"] else "no",
            "decision_unstable": "yes" if row["decision_unstable"] else "no",
            "pairwise_unstable": "yes" if row["pairwise_unstable"] else "no",
            "flagged": "yes" if row["flagged"] else "no",
            "flag_reasons": "|".join(row["flag_reasons"]),
            "row_sha256": row["row_sha256"],
        }
        for pair in row["pairs"]:
            prefix = _pair_label(tuple(pair["pass_numbers"]))
            flattened[f"{prefix}_gate_status"] = pair["gate_status"]
            flattened[f"{prefix}_lane"] = pair["lane"]
        writer.writerow(flattened)
    return output.getvalue()


def build_permutation_stability_audit(
    *,
    pair_gate_paths: Sequence[Path],
    pair_score_paths: Sequence[Path],
    triple_gate_path: Path,
    triple_score_path: Path,
) -> tuple[dict[str, Any], str]:
    """Build read-only pair-vs-triple stability telemetry.

    The result does not feed back into consensus or scoring.  Inputs are paired
    by the score report's gate hash and then ordered by pass set, so CLI argument
    order cannot affect the output.
    """
    if len(pair_gate_paths) != 3 or len(pair_score_paths) != 3:
        raise ValueError("exactly three --pair-gate and three --pair-score reports are required")

    pair_gates = [_load_gate(Path(path)) for path in pair_gate_paths]
    gate_by_hash = {gate.report_sha256: gate for gate in pair_gates}
    if len(gate_by_hash) != 3:
        raise ValueError("pair gate reports must be distinct")

    pair_bundles: dict[tuple[int, ...], _ReportBundle] = {}
    consumed_gate_hashes: set[str] = set()
    for path in pair_score_paths:
        score = _load_score(Path(path))
        lineage = _require_mapping(score.report.get("lineage"), "pair score lineage")
        gate_hash = lineage.get("gate_report_sha256")
        gate = gate_by_hash.get(gate_hash)
        if gate is None:
            raise ValueError("pair score does not bind to any supplied pair gate")
        if gate_hash in consumed_gate_hashes:
            raise ValueError("multiple pair scores bind to the same pair gate")
        bundle = _bind(gate, score, f"pair {gate.pass_numbers}")
        if bundle.gate.pass_numbers in pair_bundles:
            raise ValueError(f"duplicate pair pass set {bundle.gate.pass_numbers}")
        pair_bundles[bundle.gate.pass_numbers] = bundle
        consumed_gate_hashes.add(gate_hash)
    if set(pair_bundles) != set(EXPECTED_PAIRS):
        raise ValueError(
            f"pair reports must cover {EXPECTED_PAIRS}, observed {sorted(pair_bundles)}"
        )

    triple_bundle = _bind(
        _load_gate(Path(triple_gate_path)),
        _load_score(Path(triple_score_path)),
        "triple",
    )
    if triple_bundle.gate.pass_numbers != TRIPLE:
        raise ValueError(
            f"triple reports must use passes {TRIPLE}, observed {triple_bundle.gate.pass_numbers}"
        )

    ordered_bundles = [pair_bundles[pair] for pair in EXPECTED_PAIRS] + [triple_bundle]
    gates = [bundle.gate.report for bundle in ordered_bundles]
    scores = [bundle.score.report for bundle in ordered_bundles]
    score_lineages = [score["lineage"] for score in scores]

    run_contract_sha256 = _uniform(
        [gate.get("run_contract_sha256") for gate in gates],
        "run_contract_sha256",
    )
    consensus_policy_sha256 = _uniform(
        [gate.get("consensus_policy_sha256") for gate in gates],
        "consensus_policy_sha256",
    )
    gate_boundary_policy_sha256 = _uniform(
        [gate.get("boundary_policy_sha256") for gate in gates],
        "gate boundary_policy_sha256",
    )
    contract_sha256 = _uniform(
        [canonical_sha256(gate.get("contract")) for gate in gates],
        "gate contract",
    )
    checker_binding_sha256 = _uniform(
        [lineage.get("checker_binding_sha256") for lineage in score_lineages],
        "score checker_binding_sha256",
    )
    scoring_policy_sha256 = _uniform(
        [lineage.get("scoring_policy_sha256") for lineage in score_lineages],
        "score scoring_policy_sha256",
    )
    scoring_boundary_policy_sha256 = _uniform(
        [lineage.get("boundary_policy_sha256") for lineage in score_lineages],
        "score boundary_policy_sha256",
    )
    score_engine_implementation_sha256 = _uniform(
        [lineage.get("engine_implementation_sha256") for lineage in score_lineages],
        "score engine_implementation_sha256",
    )

    triple_slugs = set(triple_bundle.gate.rows)
    for pair, bundle in pair_bundles.items():
        if set(bundle.gate.rows) != triple_slugs:
            raise ValueError(f"pair {pair} and triple session sets differ")
        for slug in sorted(triple_slugs):
            pair_session = bundle.gate.rows[slug].get("session")
            triple_session = triple_bundle.gate.rows[slug].get("session")
            if canonical_sha256(pair_session) != canonical_sha256(triple_session):
                raise ValueError(f"pair {pair} session {slug} source binding differs from triple")

    rows: list[dict[str, Any]] = []
    for slug in sorted(triple_slugs):
        triple_gate_row = triple_bundle.gate.rows[slug]
        triple_score_row = triple_bundle.score.rows[slug]
        triple_lane = triple_score_row["lane"]
        triple_resolved = triple_lane in DECIDED_LANES
        triple_gate_nonfull = triple_gate_row["gate_status"] != "full_consensus"
        triple_score_nondecided = not triple_resolved
        pair_rows: list[dict[str, Any]] = []
        reasons: list[str] = []
        pair_lanes: list[str] = []
        for pair in EXPECTED_PAIRS:
            bundle = pair_bundles[pair]
            gate_status = bundle.gate.rows[slug]["gate_status"]
            lane = bundle.score.rows[slug]["lane"]
            gate_nonfull = gate_status != "full_consensus"
            score_nondecided = lane not in DECIDED_LANES
            abstained_or_partial = gate_nonfull or score_nondecided
            label = _pair_label(pair)
            if gate_nonfull:
                reasons.append(f"{label}:gate_status={gate_status}")
            if score_nondecided:
                reasons.append(f"{label}:lane={lane}")
            pair_rows.append(
                {
                    "pass_numbers": list(pair),
                    "gate_status": gate_status,
                    "lane": lane,
                    "gate_nonfull": gate_nonfull,
                    "score_nondecided": score_nondecided,
                    "abstained_or_partial": abstained_or_partial,
                }
            )
            pair_lanes.append(lane)
        any_pair_gate_nonfull = any(item["gate_nonfull"] for item in pair_rows)
        any_pair_score_nondecided = any(item["score_nondecided"] for item in pair_rows)
        any_pair_problem = any_pair_gate_nonfull or any_pair_score_nondecided
        pairwise_lanes_differ = len(set(pair_lanes)) != 1
        triple_lane_differs_from_pairs = any(
            lane != triple_lane for lane in pair_lanes
        )
        if pairwise_lanes_differ:
            reasons.append("pairwise_lane_divergence")
        if triple_gate_nonfull:
            reasons.append(f"triple:gate_status={triple_gate_row['gate_status']}")
        if triple_score_nondecided:
            reasons.append(f"triple:lane={triple_lane}")
        if triple_lane_differs_from_pairs:
            reasons.append("triple_pair_lane_divergence")
        extraction_unstable = (
            any_pair_gate_nonfull
            or triple_gate_nonfull
            or pairwise_lanes_differ
        )
        decision_unstable = (
            any_pair_score_nondecided
            or triple_score_nondecided
            or pairwise_lanes_differ
            or triple_lane_differs_from_pairs
        )
        pairwise_unstable = extraction_unstable or decision_unstable
        flagged = pairwise_unstable
        row = {
            "session_slug": slug,
            "triple": {
                "pass_numbers": list(TRIPLE),
                "gate_status": triple_gate_row["gate_status"],
                "lane": triple_lane,
            },
            "pairs": pair_rows,
            "triple_resolved": triple_resolved,
            "triple_gate_nonfull": triple_gate_nonfull,
            "triple_score_nondecided": triple_score_nondecided,
            "any_pair_gate_nonfull": any_pair_gate_nonfull,
            "any_pair_score_nondecided": any_pair_score_nondecided,
            "any_pair_abstained_or_partial": any_pair_problem,
            "pairwise_lanes_differ": pairwise_lanes_differ,
            "triple_lane_differs_from_pairs": triple_lane_differs_from_pairs,
            "extraction_unstable": extraction_unstable,
            "decision_unstable": decision_unstable,
            "pairwise_unstable": pairwise_unstable,
            "flagged": flagged,
            "flag_reasons": reasons if flagged else [],
        }
        row["row_sha256"] = canonical_sha256(row)
        rows.append(row)

    csv_text = _csv_text(rows)
    report: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "policy": AUDIT_POLICY,
        "policy_sha256": canonical_sha256(AUDIT_POLICY),
        "audit_engine_implementation_sha256": engine_implementation_sha256(),
        "lineage": {
            "pairs": [_lineage_entry(pair_bundles[pair]) for pair in EXPECTED_PAIRS],
            "triple": _lineage_entry(triple_bundle),
            "common": {
                "run_contract_sha256": run_contract_sha256,
                "contract_canonical_sha256": contract_sha256,
                "consensus_policy_sha256": consensus_policy_sha256,
                "gate_boundary_policy_sha256": gate_boundary_policy_sha256,
                "checker_binding_sha256": checker_binding_sha256,
                "scoring_policy_sha256": scoring_policy_sha256,
                "scoring_boundary_policy_sha256": scoring_boundary_policy_sha256,
                "score_engine_implementation_sha256": (
                    score_engine_implementation_sha256
                ),
                "score_engine_implementation_uniform": True,
            },
            "warnings": [],
        },
        "session_count": len(rows),
        "triple_resolved_count": sum(row["triple_resolved"] for row in rows),
        "triple_gate_nonfull_count": sum(row["triple_gate_nonfull"] for row in rows),
        "triple_score_nondecided_count": sum(
            row["triple_score_nondecided"] for row in rows
        ),
        "any_pair_gate_nonfull_count": sum(row["any_pair_gate_nonfull"] for row in rows),
        "any_pair_score_nondecided_count": sum(row["any_pair_score_nondecided"] for row in rows),
        "any_pair_abstained_or_partial_count": sum(
            row["any_pair_abstained_or_partial"] for row in rows
        ),
        "pairwise_lanes_differ_count": sum(row["pairwise_lanes_differ"] for row in rows),
        "triple_lane_differs_from_pairs_count": sum(
            row["triple_lane_differs_from_pairs"] for row in rows
        ),
        "extraction_unstable_count": sum(row["extraction_unstable"] for row in rows),
        "decision_unstable_count": sum(row["decision_unstable"] for row in rows),
        "pairwise_unstable_count": sum(row["pairwise_unstable"] for row in rows),
        "flagged_count": sum(row["flagged"] for row in rows),
        "flagged_session_slugs": [row["session_slug"] for row in rows if row["flagged"]],
        "csv_sha256": sha256_text(csv_text),
        "rows": rows,
    }
    report["audit_report_sha256"] = canonical_sha256(report)
    return report, csv_text


def write_permutation_stability_audit(
    *,
    pair_gate_paths: Sequence[Path],
    pair_score_paths: Sequence[Path],
    triple_gate_path: Path,
    triple_score_path: Path,
    output_json_path: Path,
    output_csv_path: Path,
) -> dict[str, Any]:
    output_json_path = Path(output_json_path)
    output_csv_path = Path(output_csv_path)
    if output_json_path.resolve() == output_csv_path.resolve():
        raise ValueError("JSON and CSV outputs must be different paths")
    existing = [path for path in (output_json_path, output_csv_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "immutable permutation audit output already exists: "
            + ", ".join(str(path) for path in existing)
        )
    report, csv_text = build_permutation_stability_audit(
        pair_gate_paths=pair_gate_paths,
        pair_score_paths=pair_score_paths,
        triple_gate_path=triple_gate_path,
        triple_score_path=triple_score_path,
    )
    write_text_atomic(output_csv_path, csv_text)
    write_json_atomic(output_json_path, report)
    return report
