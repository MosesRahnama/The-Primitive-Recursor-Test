r"""Write results\payload-scaling-tests\RUN_MANIFEST.csv per instructions\PAYLOAD-SCALING-RUN-INSTRUCTIONS.md.

Columns: session_slug, model, provider, arm, status, response_chars, response_2_chars,
         thinking_saved

Every field is read from the session folder itself. Reads only; rewrites the CSV from disk, so
a session on disk can never be missing from the index.

Storage contract for this battery (see run_battery.run_session, "t1_response"):
response.txt is the TURN-1 reply and response_2.txt is the turn-2 reply. status is "skipped"
when turn 1 came back empty and turn 2 was therefore never sent, "failed" when turn 1 errored,
otherwise "ok".
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "results" / "payload-scaling-tests"
DOCS = ROOT / "results" / "results-docs" / "payload-scaling"
SESSIONS = SURFACE / "test-sessions"
OUT = DOCS / "RUN_MANIFEST.csv"
HEADER = ["session_slug", "model", "provider", "arm", "status",
          "response_chars", "response_2_chars", "thinking_saved"]
ARMS = ("k2", "k4", "k8")


def text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def main() -> int:
    if not SESSIONS.is_dir():
        print("no session directory: %s" % SESSIONS)
        return 1

    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir() or not any("-%s__" % a in d.name for a in ARMS):
            continue
        man, sess = {}, {}
        for name, into in (("manifest.json", "man"), ("session.json", "sess")):
            if (d / name).exists():
                try:
                    blob = json.loads((d / name).read_text(encoding="utf-8"))
                except Exception:
                    blob = {}
                if into == "man":
                    man = blob
                else:
                    sess = blob

        r1, r2 = text(d / "response.txt"), text(d / "response_2.txt")
        arm = man.get("arm") or next((a for a in ARMS if "-%s__" % a in d.name), "")
        if not r1.strip() or r1.startswith("[ERROR]"):
            status = "skipped" if sess.get("turn2_status") == "skipped_empty_turn1" else "failed"
        elif not r2.strip() or r2.startswith("[ERROR]"):
            status = "failed"
        else:
            status = "ok"

        rows.append([d.name,
                     man.get("model") or d.name.split("-%s__" % arm)[0],
                     man.get("provider") or sess.get("provider") or "",
                     arm, status, len(r1), len(r2),
                     "yes" if (d / "thinking.txt").exists() else "no"])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    cells = {}
    for r in rows:
        cells.setdefault((r[1], r[3]), []).append(r[4])
    models = sorted({k[0] for k in cells})
    print("%-24s %s" % ("model", "  ".join("%-14s" % a for a in ARMS)))
    print("-" * (24 + 16 * len(ARMS)))
    for mdl in models:
        cs = []
        for a in ARMS:
            v = cells.get((mdl, a), [])
            ok = sum(1 for s in v if s == "ok")
            bad = len(v) - ok
            cs.append("%d ok%s" % (ok, (" /%d bad" % bad) if bad else ""))
        print("%-24s %s" % (mdl, "  ".join("%-14s" % c for c in cs)))
    print("-" * (24 + 16 * len(ARMS)))
    print("TOTAL rows=%d  ok=%d  failed=%d  skipped=%d  thinking=%d"
          % (len(rows), sum(1 for r in rows if r[4] == "ok"),
             sum(1 for r in rows if r[4] == "failed"),
             sum(1 for r in rows if r[4] == "skipped"),
             sum(1 for r in rows if r[7] == "yes")))
    print("CSV: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
