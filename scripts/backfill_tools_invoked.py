"""Recompute the DERIVED tool-usage fields in tools-arm session manifests from each
session's own archived response.txt.

Why this exists: `tools_invoked` / `tools_call_blocks` / `tools_result_blocks` are derived
metadata, not observations -- the observation is the archived trace in response.txt. Early
2026-07-24 sessions were written while the derivation keyed on [TOOL-CALL ...] alone, which
reports a Gemini session that ran google_search (grounding surfaces only as a RESULT block,
never a CALL) as tool-free. This rewrites the derived fields to agree with the archive.

It NEVER edits response.txt and never invents a tool the archive does not contain.

    python scripts/backfill_tools_invoked.py            # dry run
    python scripts/backfill_tools_invoked.py --apply
"""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
TOOL_EVENT_RE = re.compile(r"\[TOOL-(CALL|RESULT) ([A-Za-z0-9_]+)\]")


def derive(text):
    ev = TOOL_EVENT_RE.findall(text or "")
    return {"tools_invoked": sorted({n for _, n in ev}),
            "tools_call_blocks": sum(1 for k, _ in ev if k == "CALL"),
            "tools_result_blocks": sum(1 for k, _ in ev if k == "RESULT")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    changed = scanned = 0
    for folder in sorted(os.listdir(RESULTS)):
        sdir = os.path.join(RESULTS, folder, "test-sessions")
        if not os.path.isdir(sdir):
            continue
        for name in sorted(os.listdir(sdir)):
            mf = os.path.join(sdir, name, "session.json")
            rf = os.path.join(sdir, name, "response.txt")
            if not (os.path.exists(mf) and os.path.exists(rf)):
                continue
            meta = json.load(open(mf, encoding="utf-8"))
            if not meta.get("tools_enabled"):
                continue
            scanned += 1
            new = derive(open(rf, encoding="utf-8").read())
            old = {k: meta.get(k) for k in new}
            if old == new:
                continue
            meta.pop("tools_invoked_count", None)          # superseded by the two block counts
            meta.update(new)
            changed += 1
            print("  %s\n     %s -> %s" % (name, old, new))
            if a.apply:
                json.dump(meta, open(mf, "w", encoding="utf-8"), indent=1)
    print("\n%s: %d tools-arm session(s) scanned, %d manifest(s) %s"
          % ("APPLIED" if a.apply else "DRY RUN", scanned, changed,
             "rewritten" if a.apply else "would change"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
