"""Reproducible launcher: Schema Test B - new system, clarified control.

Full roster, 4 sessions per model, Claude Fable 5 excluded (no placeholder). The
roster is ordered slow-first, so GLM and GPT-Pro start in pass 1. Bounded + resumable:
re-run any time to top up only the sessions still missing.

    python scripts/runners/run_schema-b-new-system-control.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import corpus_run

if __name__ == "__main__":
    corpus_run.run("schema-b-new-system-control", runs=4)
