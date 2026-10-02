"""Reserve unprocessed suspect sessions and maintain cumulative coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .common import canonical_sha256, read_json, sha256_file, write_json_atomic, write_text_atomic
from .prt_selective import (
    PACKAGE,
    SELECTION_FIELDS,
    SURFACES,
    _csv_rows,
    _csv_text,
    _validated_selection,
    prepare_selection,
    score_selection,
    source_path,
)

COVERAGE_FIELDS = SELECTION_FIELDS + ("status", "source", "evidence", "evidence_sha256")
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "site-packages",
    ".venv",
    "venv",
    "build",
    "test-sessions",
    "final_scored_data",
    "normalized_data",
    "final_extracted_data",
}


def history_files(repo: Path, package: Path) -> list[Path]:
    """Read prior engine results and reservations, excluding ordinary corpus labels."""
    paths = []
    for root in (repo / "results", package):
        for parent, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("release-"))
            for name in sorted(names):
                path = Path(parent) / name
                if path.suffix.lower() not in {".json", ".csv"}:
                    continue
                if "score" in name.lower() or name in {"RUN_MANIFEST.json", "SELECTION.json"}:
                    paths.append(path)
    return sorted(set(paths))


def _matched_slugs(value: Any, slugs: set[str]) -> set[str]:
    """Identify reserved IDs even in older manifests with string lists or keyed rows."""
    if isinstance(value, str):
        return {value} if value in slugs else set()
    if isinstance(value, list):
        return set().union(*(_matched_slugs(v, slugs) for v in value))
    if isinstance(value, dict):
        return (set(value) & slugs) | set().union(
            *(_matched_slugs(v, slugs) for v in value.values())
        )
    return set()


def inventory(repo: Path, package: Path = PACKAGE) -> tuple[list[dict[str, str]], dict[str, Any]]:
    selected = package / "selected"
    candidates = _csv_rows(selected / "candidates.csv")
    _validated_selection(candidates, repo)
    by_slug: dict[str, list[tuple[str, str]]] = {}
    for row in candidates:
        by_slug.setdefault(row["session_slug"], []).append((row["surface"], row["session_slug"]))
    evidence: dict[tuple[str, str], list[tuple[str, str]]] = {}
    hash_evidence = {}
    candidate_hashes = {r["source_sha256"] for r in candidates}
    scanned = []
    for path in history_files(repo, package):
        try:
            data = _csv_rows(path) if path.suffix == ".csv" else read_json(path)
        except (ValueError, UnicodeError) as error:
            raise ValueError(
                f"unreadable history; cannot certify fresh selection: {path}"
            ) from error
        digest = sha256_file(path)
        hits = _matched_slugs(data, set(by_slug))
        for source_hash in _matched_slugs(data, candidate_hashes):
            hash_evidence.setdefault(source_hash, (str(path), digest))
        scanned.append({"path": str(path), "sha256": digest, "candidate_hits": len(hits)})
        for slug in hits:
            for pair in by_slug[slug]:
                evidence.setdefault(pair, []).append((str(path), digest))

    # The ledger retains reservations after an operator archives their entire deployment.
    previous = {}
    if (selected / "coverage.csv").exists():
        previous = {
            (r["surface"], r["session_slug"]): r for r in _csv_rows(selected / "coverage.csv")
        }
    pending = selected / "pending"
    pending_pairs = set()
    if (pending / "SELECTION.json").exists():
        pending_pairs = {
            (r["surface"], r["session_slug"]) for r in read_json(pending / "SELECTION.json")["rows"]
        }
    current_scores = {}
    for stage in (selected, selected / "reconstruction", pending):
        path = stage / "scores.json"
        if not path.exists():
            continue
        report = read_json(path)
        core = {k: v for k, v in report.items() if k != "report_sha256"}
        if canonical_sha256(core) != report.get("report_sha256"):
            raise ValueError(f"score report hash mismatch: {path}")
        for row in report["rows"]:
            current_scores[(row["surface"], row["session_slug"])] = (row, path)

    rows = []
    for candidate in candidates:
        pair = (candidate["surface"], candidate["session_slug"])
        prior = previous.get(pair, {})
        status, reference, digest = "available", "", ""
        if evidence.get(pair):
            # Prefer a score artifact over a mere reservation as the evidence reference.
            reference, digest = min(
                evidence[pair],
                key=lambda e: ("score" not in Path(e[0]).name.lower(), len(e[0]), e[0]),
            )
            status = "prior_engine_record"
        elif candidate["source_sha256"] in hash_evidence:
            reference, digest = hash_evidence[candidate["source_sha256"]]
            status = "duplicate_source"
        elif prior.get("status") not in {None, "available"}:
            status = "prior_reservation"
            reference, digest = prior["evidence"], prior["evidence_sha256"]
        if pair in pending_pairs:
            status = "pending_extraction"
            reference = str(pending / "SELECTION.json")
            digest = sha256_file(Path(reference))
        if pair in current_scores:
            scored, path = current_scores[pair]
            if scored["source_sha256"] != candidate["source_sha256"]:
                raise ValueError(f"previously scored source changed: {pair}")
            status = (
                "scored_unknown"
                if "Unknown"
                in (scored["method_mathematical_validity"], scored["method_correct_and_admissible"])
                else "scored_decided"
            )
            reference, digest = str(path), sha256_file(path)
        rows.append(
            {
                **candidate,
                "status": status,
                "source": str(source_path(repo, *pair)),
                "evidence": reference,
                "evidence_sha256": digest,
            }
        )
    # An identical response under another session ID is not new material.
    used_hashes = {r["source_sha256"] for r in rows if r["status"] != "available"}
    for row in rows:
        if row["status"] == "available" and row["source_sha256"] in used_hashes:
            other = next(
                r
                for r in rows
                if r["status"] != "available" and r["source_sha256"] == row["source_sha256"]
            )
            row.update(
                status="duplicate_source",
                evidence=other["evidence"],
                evidence_sha256=other["evidence_sha256"],
            )
    return rows, {
        "candidate_sha256": sha256_file(selected / "candidates.csv"),
        "history_scan": scanned,
        "status_counts": dict(Counter(r["status"] for r in rows)),
    }


def choose(rows: list[dict[str, str]], quotas: dict[str, int]) -> list[dict[str, str]]:
    """Select by stable ID hashes, never by historical verdicts or checker coverage."""
    chosen, hashes = [], set()
    for surface, count in quotas.items():
        if (
            surface not in SURFACES
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise ValueError("invalid surface quota")
        eligible = sorted(
            (r for r in rows if r["surface"] == surface and r["status"] == "available"),
            key=lambda r: hashlib.sha256((surface + "\0" + r["session_slug"]).encode()).hexdigest(),
        )
        taken = 0
        for row in eligible:
            if taken == count:
                break
            if row["source_sha256"] not in hashes:
                chosen.append({k: row[k] for k in SELECTION_FIELDS})
                hashes.add(row["source_sha256"])
                taken += 1
        if taken != count:
            raise ValueError(f"not enough unprocessed suspects for {surface}: {taken} < {count}")
    if not chosen:
        raise ValueError("empty selection")
    return chosen


def refresh(repo: Path, package: Path = PACKAGE) -> dict[str, Any]:
    rows, audit = inventory(repo, package)
    write_text_atomic(package / "selected/coverage.csv", _csv_text(rows, COVERAGE_FIELDS))
    return {"candidates": len(rows), **audit["status_counts"]}


def prepare(repo: Path, package: Path = PACKAGE) -> dict[str, Any]:
    work = package / "selected/pending"
    if work.exists() and any(work.iterdir()):
        raise ValueError(
            "pending is occupied; preserve and archive the completed stage before reuse"
        )
    rows, audit = inventory(repo, package)
    chosen = choose(rows, {"schema_a": 6, "schema_a_new_system": 6, "test01": 8})
    selection = work / "selection.csv"
    write_text_atomic(selection, _csv_text(chosen, SELECTION_FIELDS))
    # The ordinary deployer supplies all hash-bound contracts, manifests and blank passes.
    prepare_selection(selection, repo, work)
    audit.update(
        {
            "version": "prt-incremental-eligibility/1",
            "selection_sha256": sha256_file(selection),
            "selection_rule": "6/6/8 by SHA256(surface + NUL + session_slug), excluding history and duplicate source hashes",
            "excluded_scope": "Engine outputs and reservations, including Unknowns; ordinary published corpus labels are not exclusions.",
            "selected_sessions": len(chosen),
            "prior_overlap": 0,
        }
    )
    write_json_atomic(work / "ELIGIBILITY.json", audit)
    return {
        "selected": len(chosen),
        "blank_records": 2 * len(chosen),
        "coverage": refresh(repo, package),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "refresh", "score"))
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(PACKAGE.parent)
        elif args.command == "score":
            report = score_selection(PACKAGE / "selected/pending")
            result = {
                "session_count": report["session_count"],
                "unknown_count": report["unknown_count"],
                "coverage": refresh(PACKAGE.parent),
            }
        else:
            result = refresh(PACKAGE.parent)
        print(json.dumps(result, indent=2))
        return 1 if result.get("unknown_count", 0) else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
