"""Reproducible launcher: Test 04 - measure verification.

Full roster, 4 sessions per model, Claude Fable 5 excluded (no placeholder). The
roster is ordered slow-first, so GLM and GPT-Pro start in pass 1. Bounded + resumable:
re-run any time to top up only the sessions still missing.

    python scripts/runners/run_test-04.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import corpus_run

if __name__ == "__main__":
    corpus_run.run("test-04", runs=4)
