r"""Write results\test-07-propagation-fac-tests\RUN_MANIFEST_ROSTER_EXPANSION.csv.

Per instructions\ROSTER-EXPANSION-RUN-INSTRUCTIONS.md, battery 1. Columns:
    session_slug, model, provider, arm, status, response_chars, followup_chars,
    followup2_chars, thinking_saved

Scoped to the five expansion models ONLY. The Test 07 surface also holds 180 sessions from
earlier batteries indexed by other manifests; this file must not describe them, and
RUN_MANIFEST_ARMS_CDE_2026-07-26.csv is never read or written here.

Arm comes from the session's own manifest.json. Falling back to the folder name needs care:
"-armC__" is a prefix collision with "-armC2__", and the fac arm carries no suffix at all, so
the suffix table below is ordered longest-first and fac is the default.

Reads only.
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
OUT = DOCS / "RUN_MANIFEST_ROSTER_EXPANSION.csv"

# kimi-k2.6 was replaced by minimax-m3 on this battery: on the Test 07 prompts kimi spends
# its whole output budget reasoning and returns empty content at any budget below ~56k
# tokens, and Moonshot exposes no reasoning-budget parameter (only thinking on/off).
# kimi remains complete on the payload arms, where the shorter prompts never trigger it.
MODELS = ("gemini-3.5-flash", "gpt-5.6-terra", "minimax-m3", "qwen3.7-max",
          "mistral-large-latest")
ARM_SUFFIXES = ("-armC2", "-armC", "-armD", "-armE", "-armF")   # longest-first; fac has none
HEADER = ["session_slug", "model", "provider", "arm", "status", "response_chars",
          "followup_chars", "followup2_chars", "thinking_saved"]


def chars(p: Path) -> int:
    return len(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else 0


def arm_from_name(name: str) -> str:
    head = name.split("__")[0]
    for s in ARM_SUFFIXES:
        if head.endswith(s):
            return s[1:]
    return "fac"


def model_from_name(name: str) -> str:
    head = name.split("__")[0]
    for s in ARM_SUFFIXES:
        if head.endswith(s):
            return head[: -len(s)]
    return head


def main() -> int:
    if not SESSIONS.is_dir():
        print("no session directory: %s" % SESSIONS)
        return 1

    rows = []
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        if model_from_name(d.name) not in MODELS:
            continue
        man = {}
        if (d / "manifest.json").exists():
            try:
                man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            except Exception:
                man = {}
        r1 = (d / "response.txt").read_text(encoding="utf-8", errors="replace") \
            if (d / "response.txt").exists() else ""
        status = "failed" if (not r1.strip() or r1.startswith("[ERROR]")) else "ok"
        rows.append([d.name,
                     man.get("model") or model_from_name(d.name),
                     man.get("provider") or "",
                     man.get("arm") or arm_from_name(d.name),
                     status, len(r1),
                     chars(d / "followup_response.txt"),
                     chars(d / "followup2_response.txt"),
                     "yes" if (d / "thinking.txt").exists() else "no"])

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    arms = ("fac", "armC", "armC2", "armD", "armE", "armF")
    cell = {}
    for r in rows:
        cell.setdefault((r[1], r[3]), []).append(r)
    print("%-24s %s" % ("model", "  ".join("%-11s" % a for a in arms)))
    print("-" * (24 + 13 * len(arms)))
    for m in MODELS:
        out = []
        for a in arms:
            v = cell.get((m, a), [])
            ok = sum(1 for r in v if r[4] == "ok")
            out.append("%d/%d%s" % (ok, len(v), "" if ok == len(v) else " BAD"))
        print("%-24s %s" % (m, "  ".join("%-11s" % c for c in out)))
    print("-" * (24 + 13 * len(arms)))
    print("TOTAL rows=%d  ok=%d  turn2=%d  turn3=%d  thinking=%d"
          % (len(rows), sum(1 for r in rows if r[4] == "ok"),
             sum(1 for r in rows if r[6]), sum(1 for r in rows if r[7]),
             sum(1 for r in rows if r[8] == "yes")))
    print("CSV: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
