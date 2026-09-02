#!/usr/bin/env python3
"""Incrementally consolidate one available extractor into final fields.

The source inventory is read from ``temp-files-list.md``. Targets are derived from
each source filename in the same directory and round; this deliberately avoids
cross-family and round-order typos in the temporary instruction document.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / "temp-files-list.md"
REPORT_DIR = ROOT / "data-audit" / "reports"
REPORT_CSV = REPORT_DIR / "incremental_single_extractor_consolidation.csv"
REPORT_MD = REPORT_DIR / "incremental_single_extractor_consolidation.md"
SOURCE_PATTERN = re.compile(r"^(?P<prefix>.+)_extractor_(?P<number>01|02)\.csv$")


@dataclass
class PairResult:
    test: str
    round_name: str
    source: Path
    target: Path
    extractor: str
    source_rows: int
    target_rows: int
    candidate_rows: int
    updated_rows: int
    already_exact_rows: int
    preserved_existing_rows: int
    existing_source_drift_rows: int
    empty_source_rows: int
    status: str
    row_unit: str = "test_session_by_extraction_round"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {path}")
        rows = list(reader)
        return list(reader.fieldnames), rows


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def listed_sources() -> list[Path]:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    sources: list[Path] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().rstrip(";")
        candidate = Path(line)
        if SOURCE_PATTERN.match(candidate.name):
            sources.append(candidate)
    if not sources:
        raise ValueError(f"No extractor CSV paths found in {INSTRUCTIONS}")
    if len(sources) != len(set(sources)):
        raise ValueError("Duplicate extractor paths in temp-files-list.md")
    return sources


def target_for(source: Path) -> tuple[Path, str]:
    match = SOURCE_PATTERN.match(source.name)
    if match is None:
        raise ValueError(f"Unsupported extractor filename: {source}")
    target = source.with_name(f"{match.group('prefix')}_consolidation.csv")
    extractor = "extractor1" if match.group("number") == "01" else "extractor2"
    return target, extractor


def test_name(path: Path) -> str:
    parts = path.parts
    try:
        return parts[parts.index("results") + 1]
    except (ValueError, IndexError):
        return path.parent.name


def round_name(path: Path) -> str:
    match = re.search(r"_(r\d+)_extractor_", path.name)
    return match.group(1) if match else "unknown"


def all_blank(row: dict[str, str], fields: list[str]) -> bool:
    return all((row.get(field) or "") == "" for field in fields)


def exact_values(
    target_row: dict[str, str], target_fields: list[str], source_row: dict[str, str], source_fields: list[str]
) -> bool:
    return all((target_row.get(dst) or "") == (source_row.get(src) or "")
               for dst, src in zip(target_fields, source_fields, strict=True))


def preflight_pair(source: Path) -> tuple[Path, str, list[str], list[dict[str, str]], list[str], list[dict[str, str]]]:
    target, extractor = target_for(source)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not target.is_file():
        raise FileNotFoundError(target)

    source_header, source_rows = read_csv(source)
    target_header, target_rows = read_csv(target)
    if not source_header or source_header[0] != "session_slug":
        raise ValueError(f"Source must start with session_slug: {source}")
    if not target_header or target_header[0] != "session_slug":
        raise ValueError(f"Target must start with session_slug: {target}")

    source_fields = source_header[1:]
    extractor_fields = [f"{extractor}_{field}" for field in source_fields]
    final_fields = [f"final_{field}" for field in source_fields]
    missing = [field for field in extractor_fields + final_fields if field not in target_header]
    if missing:
        raise ValueError(f"Target header mismatch in {target}: missing {missing}")

    source_slugs = [row["session_slug"] for row in source_rows]
    target_slugs = [row["session_slug"] for row in target_rows]
    if len(source_slugs) != len(set(source_slugs)):
        raise ValueError(f"Duplicate source slugs: {source}")
    if len(target_slugs) != len(set(target_slugs)):
        raise ValueError(f"Duplicate target slugs: {target}")
    if set(source_slugs) != set(target_slugs):
        missing = sorted(set(target_slugs) - set(source_slugs))
        extra = sorted(set(source_slugs) - set(target_slugs))
        raise ValueError(
            f"Slug set mismatch: {source} -> {target}; missing={missing[:5]}, extra={extra[:5]}"
        )

    return target, extractor, source_header, source_rows, target_header, target_rows


def consolidate_pair(source: Path, apply: bool) -> PairResult:
    target, extractor, source_header, source_rows, target_header, target_rows = preflight_pair(source)
    source_fields = source_header[1:]
    extractor_fields = [f"{extractor}_{field}" for field in source_fields]
    final_fields = [f"final_{field}" for field in source_fields]

    original_rows = [dict(row) for row in target_rows]
    candidate_rows = 0
    updated_rows = 0
    already_exact_rows = 0
    preserved_existing_rows = 0
    existing_source_drift_rows = 0
    empty_source_rows = 0

    source_by_slug = {row["session_slug"]: row for row in source_rows}
    source_rows_in_target_order = [source_by_slug[row["session_slug"]] for row in target_rows]

    for source_row, target_row in zip(source_rows_in_target_order, target_rows, strict=True):
        source_empty = all_blank(source_row, source_fields)
        extractor_blank = all_blank(target_row, extractor_fields)
        final_blank = all_blank(target_row, final_fields)
        extractor_exact = exact_values(target_row, extractor_fields, source_row, source_fields)
        final_exact = exact_values(target_row, final_fields, source_row, source_fields)

        if source_empty:
            empty_source_rows += 1
            continue
        if extractor_blank and final_blank:
            candidate_rows += 1
            if apply:
                for source_field, extractor_field, final_field in zip(
                    source_fields, extractor_fields, final_fields, strict=True
                ):
                    value = source_row.get(source_field) or ""
                    target_row[extractor_field] = value
                    target_row[final_field] = value
                updated_rows += 1
            continue
        if extractor_exact and final_exact:
            already_exact_rows += 1
            continue

        preserved_existing_rows += 1
        if not extractor_exact:
            existing_source_drift_rows += 1

    if apply and updated_rows:
        for before, after in zip(original_rows, target_rows, strict=True):
            changed = [field for field in target_header if before.get(field, "") != after.get(field, "")]
            if changed:
                permitted = set(extractor_fields + final_fields)
                if not set(changed).issubset(permitted):
                    raise AssertionError(f"Unexpected changed columns in {target}: {changed}")
        write_csv_atomic(target, target_header, target_rows)

        check_header, check_rows = read_csv(target)
        if check_header != target_header or len(check_rows) != len(target_rows):
            raise AssertionError(f"Post-write shape drift: {target}")
        for source_row, before, after in zip(
            source_rows_in_target_order, original_rows, check_rows, strict=True
        ):
            was_candidate = (
                not all_blank(source_row, source_fields)
                and all_blank(before, extractor_fields)
                and all_blank(before, final_fields)
            )
            if was_candidate:
                if not exact_values(after, extractor_fields, source_row, source_fields):
                    raise AssertionError(f"Extractor copy validation failed: {target} / {after['session_slug']}")
                if not exact_values(after, final_fields, source_row, source_fields):
                    raise AssertionError(f"Final copy validation failed: {target} / {after['session_slug']}")
            else:
                if after != before:
                    raise AssertionError(f"Pre-existing row changed: {target} / {after['session_slug']}")

    status = "applied" if apply else "dry-run"
    return PairResult(
        test=test_name(source),
        round_name=round_name(source),
        source=source,
        target=target,
        extractor=extractor,
        source_rows=len(source_rows),
        target_rows=len(target_rows),
        candidate_rows=candidate_rows,
        updated_rows=updated_rows,
        already_exact_rows=already_exact_rows,
        preserved_existing_rows=preserved_existing_rows,
        existing_source_drift_rows=existing_source_drift_rows,
        empty_source_rows=empty_source_rows,
        status=status,
    )


def write_reports(results: list[PairResult], apply: bool) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    columns = list(PairResult.__dataclass_fields__)
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for result in results:
            row = result.__dict__.copy()
            row["source"] = str(result.source)
            row["target"] = str(result.target)
            writer.writerow(row)

    total_candidates = sum(result.candidate_rows for result in results)
    total_updates = sum(result.updated_rows for result in results)
    sessions_by_test: dict[str, set[str]] = {}
    for result in results:
        _, source_rows = read_csv(result.source)
        sessions_by_test.setdefault(result.test, set()).update(row["session_slug"] for row in source_rows)
    unique_test_sessions = sum(len(slugs) for slugs in sessions_by_test.values())
    lines = [
        "# Incremental Single-Extractor Consolidation",
        "",
        f"Mode: `{'apply' if apply else 'dry-run'}`",
        "",
        "## Mapping rule",
        "",
        "Each extractor path is read from `temp-files-list.md`. Its consolidation target is derived from",
        "the same directory, test prefix, and round by replacing `_extractor_01.csv` or",
        "`_extractor_02.csv` with `_consolidation.csv`. This prevents the document's Schema A",
        "cross-family path typo and its out-of-order Schema A New System/Test 03 target lists from",
        "mixing tests or rounds.",
        "",
        "## Guard",
        "",
        "A row is copied only when the selected extractor block and every `final_*` field are blank.",
        "The source values are copied into both blocks. Existing rows and adjudications are preserved.",
        "",
        f"Unique benchmark sessions: `{unique_test_sessions}`.",
        "",
        f"Files checked: `{len(results)}`. Candidate session-by-round rows: `{total_candidates}`. "
        f"Session-by-round rows updated: `{total_updates}`.",
        "",
        "A benchmark session appears once in each extraction-round file for its test. Therefore the",
        "session-by-round update count is intentionally larger than the unique-session count; it does",
        "not represent appended or duplicated benchmark sessions.",
        "",
        "| test | round | extractor | rows | candidates | updated | already exact | preserved existing | source drift preserved | empty source | status |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            f"| {result.test} | {result.round_name} | {result.extractor} | {result.source_rows} | "
            f"{result.candidate_rows} | {result.updated_rows} | {result.already_exact_rows} | "
            f"{result.preserved_existing_rows} | {result.existing_source_drift_rows} | "
            f"{result.empty_source_rows} | {result.status} |"
        )
    lines.extend([
        "",
        "`source drift preserved` means a previously populated extractor block differs from the current",
        "source CSV. It is reported but never overwritten by this incremental operation.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def load_report_results() -> list[PairResult]:
    with REPORT_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    numeric_fields = {
        "source_rows", "target_rows", "candidate_rows", "updated_rows", "already_exact_rows",
        "preserved_existing_rows", "existing_source_drift_rows", "empty_source_rows",
    }
    results: list[PairResult] = []
    for row in rows:
        values: dict[str, object] = dict(row)
        values["source"] = Path(row["source"])
        values["target"] = Path(row["target"])
        for field in numeric_fields:
            values[field] = int(row[field])
        if not values.get("row_unit"):
            values["row_unit"] = "test_session_by_extraction_round"
        results.append(PairResult(**values))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--refresh-report", action="store_true")
    args = parser.parse_args()

    if args.refresh_report:
        results = load_report_results()
        write_reports(results, apply=all(result.status == "applied" for result in results))
        print(f"report refreshed: {REPORT_MD}")
        print(f"ledger refreshed: {REPORT_CSV}")
        return 0

    sources = listed_sources()
    # Preflight every pair before allowing any write.
    for source in sources:
        preflight_pair(source)

    results = [consolidate_pair(source, apply=args.apply) for source in sources]
    write_reports(results, apply=args.apply)
    for result in results:
        print(
            f"{result.test}/{result.round_name}: candidates={result.candidate_rows} "
            f"updated={result.updated_rows} preserved={result.preserved_existing_rows}"
        )
    print(f"report: {REPORT_MD}")
    print(f"ledger: {REPORT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
