#!/usr/bin/env python3
"""Inventory every file whose name contains 'thinking' under KO7 4.test-sessions.

Scans known old-corpus result roots, walks each root's 4.test-sessions/
tree, and writes one CSV row per matching file (full absolute path).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

ROOTS: list[Path] = [
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
    Path(r"<manuscript repository, not distributed>"),
]

SESSIONS_DIRNAME = "4.test-sessions"

OUT_DIR = Path(r"results\ai_scored_final_2026-07-25")
OUT_CSV = OUT_DIR / "thinking_files_inventory_ko7_corpus.csv"

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
    sessions_dir = root / SESSIONS_DIRNAME
    if not sessions_dir.is_dir():
        return rows

    suite = root.name
    for path in sessions_dir.rglob("*"):
        if not is_thinking_file(path):
            continue
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
    per_suite: list[tuple[str, int, bool, bool]] = []

    for root in ROOTS:
        exists = root.is_dir()
        sessions_ok = (root / SESSIONS_DIRNAME).is_dir() if exists else False
        rows = inventory_root(root) if exists else []
        all_rows.extend(rows)
        per_suite.append((root.name, len(rows), exists, sessions_ok))

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
    for name, n, exists, sessions_ok in per_suite:
        if not exists:
            flag = "MISSING_ROOT"
        elif not sessions_ok:
            flag = f"MISSING_{SESSIONS_DIRNAME}"
        else:
            flag = "ok"
        print(f"  {name}: {n} ({flag})")


if __name__ == "__main__":
    main()
