"""Append the `followup2_status` column (ok|failed|skipped) to the existing Test 07 run
manifest CSVs, per FOLLOWUP2_RUN_INSTRUCTIONS_2026-07-26.md.

Status is derived from each session folder, never asserted:
  ok      -> followup2_response.txt exists and is non-empty
  skipped -> the session had no usable first response (nothing to follow up on)
  failed  -> had a usable first response but no followup2 landed

Idempotent: re-running refreshes the column rather than appending a duplicate.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "results" / "test-07-propagation-fac-tests"
DOCS = ROOT / "results" / "results-docs" / "test-07-propagation-fac"
SESSIONS = SURFACE / "test-sessions"
CSVS = [DOCS / "RUN_MANIFEST_2026-07-26.csv",
        DOCS / "RUN_MANIFEST_ARMS_CDE_2026-07-26.csv"]
COL = "followup2_status"


def status_for(slug: str) -> str:
    d = SESSIONS / slug
    rf = d / "response.txt"
    if not rf.exists():
        return "skipped"
    t = rf.read_text(encoding="utf-8", errors="replace")
    if not t.strip() or t.startswith("[ERROR]"):
        return "skipped"
    f2 = d / "followup2_response.txt"
    return "ok" if (f2.exists() and f2.read_text(encoding="utf-8", errors="replace").strip()) else "failed"


def main() -> int:
    for path in CSVS:
        if not path.exists():
            print(f"  MISSING {path.name} -- skipped")
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        header, data = rows[0], rows[1:]
        if COL in header:
            i = header.index(COL)
        else:
            header.append(COL)
            i = len(header) - 1
            data = [r + [""] for r in data]
        counts = {"ok": 0, "failed": 0, "skipped": 0}
        for r in data:
            while len(r) < len(header):
                r.append("")
            s = status_for(r[0])
            r[i] = s
            counts[s] += 1
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\r\n")
            w.writerow(header)
            w.writerows(data)
        print(f"  {path.name:38s} rows={len(data):4d}  ok={counts['ok']} "
              f"failed={counts['failed']} skipped={counts['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
