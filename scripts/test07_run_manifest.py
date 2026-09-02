"""Write the Test 07 battery RUN_MANIFEST CSV required by
results/test-07-propagation-fac-tests/BATTERY_RUN_INSTRUCTIONS_2026-07-26.md.

One row per session:
    session_slug, model, provider, arm, status, response_chars, thinking_saved

Everything is read from each session folder itself (manifest.json + the files actually on
disk), so the CSV can never claim a status or a saved thinking trace the folder does not
contain. Reads only; never edits a session file.

    python scripts/test07_run_manifest.py
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
OUT = DOCS / "RUN_MANIFEST_2026-07-26.csv"
HEADER = ["session_slug", "model", "provider", "arm", "status",
          "response_chars", "thinking_saved"]


def main() -> int:
    if not SESSIONS.is_dir():
        print(f"no sessions dir: {SESSIONS}", file=sys.stderr)
        return 1
    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        # arms C-F share this sessions folder but belong to RUN_MANIFEST_ARMS_CDE; this CSV
        # is the fac/nonce battery's manifest, so listing them here would double-count them.
        if any(f"-{a}__" in d.name for a in ("armC", "armD", "armE", "armF")):
            continue
        mf, rf = d / "manifest.json", d / "response.txt"
        m = {}
        if mf.exists():
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                m = {}
        text = rf.read_text(encoding="utf-8", errors="replace") if rf.exists() else ""
        failed = (not text.strip()) or text.startswith("[ERROR]")
        rows.append([
            d.name,
            m.get("model") or d.name.split("__")[0].removesuffix("-nonce"),
            m.get("provider") or "",
            m.get("arm") or ("nonce" if "-nonce__" in d.name else "fac"),
            "failed" if failed else "ok",
            len(text),
            "yes" if (d / "thinking.txt").exists() else "no",
        ])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    per = {}
    for r in rows:
        per.setdefault((r[1], r[3]), {"ok": 0, "failed": 0})[r[4]] += 1
    print(f"{'model':26s} {'arm':7s} {'ok':>4s} {'failed':>7s}")
    print("-" * 48)
    for (model, arm) in sorted(per):
        c = per[(model, arm)]
        print(f"{model:26s} {arm:7s} {c['ok']:>4d} {c['failed']:>7d}")
    ok = sum(1 for r in rows if r[4] == "ok")
    th = sum(1 for r in rows if r[6] == "yes")
    print("-" * 48)
    print(f"TOTAL rows={len(rows)}  ok={ok}  failed={len(rows)-ok}  thinking_saved={th}")
    print(f"CSV: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
