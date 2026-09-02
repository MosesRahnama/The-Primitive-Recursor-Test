"""Reproducible launcher: rebuttal-window arms (design of record:
<manuscript repository, not distributed>).

Five-model roster fixed by the operator (2026-07-24). 8 sessions per model per
arm. Bounded + resumable: re-run any time to top up only the missing sessions.

    python scripts/runners/run_window_arms.py               # ARM-A (kernel + fruit, tools ON)
    python scripts/runners/run_window_arms.py --arm nonce   # ARM-C (isolation)
    python scripts/runners/run_window_arms.py --arm context # ARM-B (isolation)
    python scripts/runners/run_window_arms.py --arm all     # A then C then B
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import corpus_run

ROSTER_FIVE = ["gpt-5.6-sol", "claude-opus-4.8", "gemini-3.5-flash",
               "grok-4.5", "deepseek-v4-pro"]

ARMS = {
    "tools":   ["test-01-tools", "test-01-fruit-tools"],
    "nonce":   ["schema-a-nonce"],
    "context": ["test-01-context"],
}


def skip_all_but_five():
    roster = json.load(open(corpus_run.ROSTER, encoding="utf-8"))
    live = [slug for slug, e in roster.items() if e.get("live")]
    missing = [m for m in ROSTER_FIVE if m not in live]
    if missing:
        raise SystemExit("roster slugs not live/present: %s" % missing)
    return tuple(sorted(set(live) - set(ROSTER_FIVE)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="tools", choices=[*ARMS, "all"])
    a = ap.parse_args()
    skip = skip_all_but_five()
    keys = [k for arm in (ARMS if a.arm == "all" else {a.arm: ARMS[a.arm]}).values() for k in arm]
    rc = 0
    for key in keys:
        have, target = corpus_run.run(key, runs=8, skip=skip)
        if have < target:
            rc = 2
    sys.exit(rc)
