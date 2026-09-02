"""Write RUN_MANIFEST_ARMC2_2026-07-26.csv per ARMC2_RUN_GUIDE_2026-07-26.md.

Columns: session_slug, model, provider, arm, status, response_chars, followup_chars,
         followup2_chars, thinking_saved

A separate CSV rather than appended rows, which the guide explicitly allows: the arms C-F
manifest has no followup2_chars column, so appending armC2 rows there would either lose that
field or force a schema change on 80 already-written rows.

Every field is read from the session folder itself. Reads only.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "results" / "test-07-propagation-fac-tests"
DOCS = ROOT / "results" / "results-docs" / "test-07-propagation-fac"
SESSIONS = SURFACE / "test-sessions"
OUT = DOCS / "RUN_MANIFEST_ARMC2_2026-07-26.csv"
HEADER = ["session_slug", "model", "provider", "arm", "status", "response_chars",
          "followup_chars", "followup2_chars", "thinking_saved"]


def chars(p: Path) -> int:
    return len(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else 0


def main() -> int:
    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir() or "-armC2__" not in d.name:
            continue
        m = {}
        if (d / "manifest.json").exists():
            try:
                m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            except Exception:
                m = {}
        text = (d / "response.txt").read_text(encoding="utf-8", errors="replace") \
            if (d / "response.txt").exists() else ""
        failed = (not text.strip()) or text.startswith("[ERROR]")
        rows.append([d.name, m.get("model") or d.name.split("-armC2__")[0],
                     m.get("provider") or "", m.get("arm") or "armC2",
                     "failed" if failed else "ok", len(text),
                     chars(d / "followup_response.txt"),
                     chars(d / "followup2_response.txt"),
                     "yes" if (d / "thinking.txt").exists() else "no"])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    per = {}
    for r in rows:
        c = per.setdefault(r[1], {"ok": 0, "failed": 0, "t2": 0, "t3": 0})
        c[r[4]] += 1
        c["t2"] += 1 if r[6] else 0
        c["t3"] += 1 if r[7] else 0
    print(f"{'model':26s} {'ok':>5s} {'failed':>7s} {'turn2':>7s} {'turn3':>7s}")
    print("-" * 56)
    for mdl in sorted(per):
        c = per[mdl]
        print(f"{mdl:26s} {c['ok']:>4d}/4 {c['failed']:>7d} {c['t2']:>7d} {c['t3']:>7d}")
    print("-" * 56)
    print(f"TOTAL rows={len(rows)}  ok={sum(1 for r in rows if r[4]=='ok')}  "
          f"turn2={sum(1 for r in rows if r[6])}  turn3={sum(1 for r in rows if r[7])}  "
          f"thinking={sum(1 for r in rows if r[8]=='yes')}")
    print(f"CSV: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
