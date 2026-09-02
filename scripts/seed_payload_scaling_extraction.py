"""Seed the payload-scaling extraction layer AFTER sessions are collected.
Scans results/payload-scaling-tests/test-sessions, writes PAYLOAD_LEDGER.csv
(slug + cell, sorted), and seeds the two blank dual-pass extractor CSVs.
Refuses to overwrite non-empty extraction files. Run before dispatching
extractors; rerun to APPEND newly collected sessions to the ledger and seeds
(existing filled rows preserved).
"""
import csv
import io
import os
import re
import sys

R = r"results\payload-scaling-tests"
EX = os.path.join(R, "extraction")
HDR = ["session_slug", "verdict", "method_primary",
       "gauge_declared", "gauge_quote", "b_dependent_claim", "b_dependent_quote",
       "wrapper_obligation", "wrapper_quote", "t2_verdict_change",
       "t2_method_change", "t2_justification_change", "t2_independence",
       "t2_quote", "extraction_notes"]
CELL_RE = re.compile(r"-(b(?:1|3|7|15|31|63)[cr])$")

slugs = sorted(d for d in os.listdir(os.path.join(R, "test-sessions"))
               if os.path.isdir(os.path.join(R, "test-sessions", d)))
bad = [s for s in slugs if not CELL_RE.search(s)]
if bad:
    sys.exit("REFUSED: slugs without a -b<N><c|r> cell suffix: " + ", ".join(bad[:5]))

with io.open(os.path.join(EX, "PAYLOAD_LEDGER.csv"), "w", encoding="utf-8",
             newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["session_slug", "cell"])
    for s in slugs:
        w.writerow([s, CELL_RE.search(s).group(1)])

for ext in ("01", "02"):
    path = os.path.join(EX, f"PAYLOAD_r1_extractor_{ext}.csv")
    existing = {}
    if os.path.exists(path):
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            existing = {r["session_slug"]: r for r in csv.DictReader(f)}
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HDR, lineterminator="\n")
        w.writeheader()
        for s in slugs:
            w.writerow(existing.get(s, {"session_slug": s,
                                        **{c: "" for c in HDR[1:]}}))
print(f"ledger + 2 extractor seeds written for {len(slugs)} sessions "
      f"({len(existing)} previously filled rows preserved in extractor_{ext})")
