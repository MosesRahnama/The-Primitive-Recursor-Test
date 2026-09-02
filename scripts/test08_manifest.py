"""Write RUN_MANIFEST_TEST08_2026-07-27.csv per
results/test-08-surface-transport/RUN_GUIDE_2026-07-27.md.

Columns: session_slug, model, provider, arm, status, response_chars, followup_chars,
         followup2_chars, thinking_saved

Every field is read from the session folder itself, so the CSV cannot claim a turn or a
thinking trace the folder does not contain. Reads only; never edits a session file.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "results" / "test-08-surface-transport"
DOCS = ROOT / "results" / "results-docs" / "test-08-surface-transport"
SESSIONS = SURFACE / "test-sessions"
OUT = DOCS / "RUN_MANIFEST_TEST08_2026-07-27.csv"
ARMS = ("stB1", "stB2", "stB3", "stE1", "stE2", "stE3")
MODELS = ("claude-sonnet-5", "gpt-5.6-sol", "gemini-3.1-pro-preview",
          "deepseek-v4-pro", "grok-4.5")
HEADER = ["session_slug", "model", "provider", "arm", "status", "response_chars",
          "followup_chars", "followup2_chars", "thinking_saved"]


def chars(p: Path) -> int:
    return len(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else 0


def main() -> int:
    if not SESSIONS.is_dir():
        print(f"no sessions dir: {SESSIONS}", file=sys.stderr)
        return 1
    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        arm = next((a for a in ARMS if f"-{a}__" in d.name), None)
        if arm is None:
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
        rows.append([d.name, m.get("model") or d.name.split(f"-{arm}__")[0],
                     m.get("provider") or "", m.get("arm") or arm,
                     "failed" if failed else "ok", len(text),
                     chars(d / "followup_response.txt"),
                     chars(d / "followup2_response.txt"),
                     "yes" if (d / "thinking.txt").exists() else "no"])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    grid = {}
    for r in rows:
        c = grid.setdefault((r[1], r[3]), {"ok": 0, "failed": 0, "t2": 0, "t3": 0})
        c[r[4]] += 1
        c["t2"] += 1 if r[6] else 0
        c["t3"] += 1 if r[7] else 0
    print(f"{'model':26s} " + " ".join(f"{a:>6s}" for a in ARMS))
    print("-" * 72)
    for mdl in MODELS:
        cells = []
        for a in ARMS:
            c = grid.get((mdl, a))
            cells.append(f"{c['ok']}/2" + ("!" if c and c["failed"] else "") if c else "-")
        print(f"{mdl:26s} " + " ".join(f"{c:>6s}" for c in cells))
    print("-" * 72)
    print(f"TOTAL rows={len(rows)}  ok={sum(1 for r in rows if r[4]=='ok')}  "
          f"failed={sum(1 for r in rows if r[4]=='failed')}  "
          f"turn2={sum(1 for r in rows if r[6])}  turn3={sum(1 for r in rows if r[7])}  "
          f"thinking={sum(1 for r in rows if r[8]=='yes')}")
    print(f"CSV: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
