"""Write RUN_MANIFEST_ARMS_CDE_2026-07-26.csv required by
results/test-07-propagation-fac-tests/BATTERY_ARMS_CDE_INSTRUCTIONS_2026-07-26.md.

One row per armC/armD/armE/armF session:
    session_slug, model, provider, arm, status, response_chars, followup_chars, thinking_saved

Every field is read from the session folder itself, so the CSV cannot report a status,
a follow-up, or a thinking trace the folder does not actually contain. Reads only.
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
OUT = DOCS / "RUN_MANIFEST_ARMS_CDE_2026-07-26.csv"
ARMS = ("armC", "armD", "armE", "armF")
HEADER = ["session_slug", "model", "provider", "arm", "status",
          "response_chars", "followup_chars", "thinking_saved"]


def main() -> int:
    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        arm = next((a for a in ARMS if f"-{a}__" in d.name), None)
        if arm is None:                      # fac / nonce sessions belong to the other manifest
            continue
        m = {}
        if (d / "manifest.json").exists():
            try:
                m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            except Exception:
                m = {}
        rf, ff = d / "response.txt", d / "followup_response.txt"
        text = rf.read_text(encoding="utf-8", errors="replace") if rf.exists() else ""
        ftext = ff.read_text(encoding="utf-8", errors="replace") if ff.exists() else ""
        failed = (not text.strip()) or text.startswith("[ERROR]")
        rows.append([d.name,
                     m.get("model") or d.name.split(f"-{arm}__")[0],
                     m.get("provider") or "",
                     m.get("arm") or arm,
                     "failed" if failed else "ok",
                     len(text), len(ftext),
                     "yes" if (d / "thinking.txt").exists() else "no"])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    per = {}
    for r in rows:
        cell = per.setdefault((r[1], r[3]), {"ok": 0, "failed": 0, "fu": 0})
        cell[r[4]] += 1
        cell["fu"] += 1 if r[6] else 0
    models = sorted({r[1] for r in rows})
    print(f"{'model':26s} " + " ".join(f"{a:>10s}" for a in ARMS))
    print("-" * 72)
    for mdl in models:
        cells = []
        for a in ARMS:
            c = per.get((mdl, a), {"ok": 0, "failed": 0})
            cells.append(f"{c['ok']}/4" + (f" ({c['failed']}f)" if c["failed"] else ""))
        print(f"{mdl:26s} " + " ".join(f"{c:>10s}" for c in cells))
    ok = sum(1 for r in rows if r[4] == "ok")
    fu = sum(1 for r in rows if r[6] > 0)
    th = sum(1 for r in rows if r[7] == "yes")
    print("-" * 72)
    print(f"TOTAL rows={len(rows)}  ok={ok}  failed={len(rows)-ok}  "
          f"with_followup={fu}  thinking_saved={th}")
    print(f"CSV: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
