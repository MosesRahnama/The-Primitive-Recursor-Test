"""Master corpus runner: runs EVERY PRT test in sequence through the one shared engine
(corpus_run). Each test is bounded + resumable, so finished tests are skipped instantly on
re-run. Controls run right after their base test.

    python scripts/run_corpus.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus_run

ORDER = [
    ("test-01-kernel", 4),
    ("test-01-fruit", 4),
    ("schema-a", 4),
    ("schema-a-new-system", 4),
    ("schema-b", 4),
    ("schema-b-control", 4),
    ("schema-b-new-system", 4),
    ("schema-b-new-system-control", 4),
    ("test-02", 4),
    ("test-03", 4),
    ("test-04", 4),
    ("test-05", 4),
    ("test-06", 4)
]

if __name__ == "__main__":
    summary = []
    for key, runs in ORDER:
        have, target = corpus_run.run(key, runs=runs)
        summary.append((key, have, target))
    print("\n==== CORPUS SUMMARY ====")
    for key, have, target in summary:
        print("  %-32s %d/%d" % (key, have, target))
