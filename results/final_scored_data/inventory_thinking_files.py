#!/usr/bin/env python3
"""Inventory every file whose name contains 'thinking' under PRT test-sessions.

Scans known New-PRT-Benchmark result roots, walks each root's test-sessions/
tree, and writes one CSV row per matching file (full absolute path).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

ROOTS: list[Path] = [
    Path(r"results\schema-test-A-new-system-tests"),
    Path(r"results\schema-test-A-tests"),
    Path(r"results\schema-test-B-new-system-tests"),
    Path(r"results\schema-test-B-tests"),
    Path(r"results\test-01-kernel-tests"),
    Path(r"results\test-02-completion-tests-nat-lex"),
    Path(r"results\test-03-completion-tests-ordinal"),
    Path(r"results\test-04-measure-verification-tests"),
    Path(r"results\test-05-candidate-class-reasoning-tests"),
    Path(r"results\test-06-branch-realism-tests"),
]

OUT_DIR = Path(r"results\ai_scored_final_2026-07-25")
OUT_CSV = OUT_DIR / "thinking_files_inventory.csv"

FIELDNAMES = [
    "full_path",
    "test_suite",
    "test_suite_root",
    "session_folder",
    "session_path",
    "file_name",
    "relative_to_suite",
    "file_size_bytes",
]


def is_thinking_file(path: Path) -> bool:
    return path.is_file() and "thinking" in path.name.lower()


def inventory_root(root: Path) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    sessions_dir = root / "test-sessions"
    if not sessions_dir.is_dir():
        return rows

    suite = root.name
    for path in sessions_dir.rglob("*"):
        if not is_thinking_file(path):
            continue
        # session folder = first path component under test-sessions
        try:
            rel = path.relative_to(sessions_dir)
        except ValueError:
            continue
        session_folder = rel.parts[0] if rel.parts else ""
        session_path = sessions_dir / session_folder
        rows.append(
            {
                "full_path": str(path.resolve()),
                "test_suite": suite,
                "test_suite_root": str(root.resolve()),
                "session_folder": session_folder,
                "session_path": str(session_path.resolve()),
                "file_name": path.name,
                "relative_to_suite": str(path.relative_to(root)).replace("\\", "/"),
                "file_size_bytes": path.stat().st_size,
            }
        )
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str | int]] = []
    per_suite: list[tuple[str, int, bool]] = []

    for root in ROOTS:
        exists = root.is_dir()
        rows = inventory_root(root) if exists else []
        all_rows.extend(rows)
        per_suite.append((root.name, len(rows), exists))

    # Stable order: suite name, then session, then file name
    all_rows.sort(
        key=lambda r: (
            str(r["test_suite"]),
            str(r["session_folder"]),
            str(r["file_name"]),
            str(r["full_path"]),
        )
    )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"wrote {OUT_CSV}")
    print(f"total_thinking_files={len(all_rows)}")
    print(f"generated_utc={datetime.now(timezone.utc).isoformat()}")
    print("per_suite:")
    for name, n, exists in per_suite:
        flag = "ok" if exists else "MISSING"
        print(f"  {name}: {n} ({flag})")


if __name__ == "__main__":
    main()
