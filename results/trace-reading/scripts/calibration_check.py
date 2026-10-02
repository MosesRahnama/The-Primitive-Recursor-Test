"""Re-check the 43 hand-coded calibration rows: every quote must be contained in its trace.

Reads data/calibration_rows.csv, resolves each session against the Schema A trace folder, prints failures (none expected).
"""
import csv, io, os
from common import DATA, EVENTS, norm, read_trace

def main():
    rows = list(csv.DictReader(io.open(os.path.join(DATA, "calibration_rows.csv"), encoding="utf-8", newline="")))
    fails = 0
    for r in rows:
        ref = "schema-test-A-tests/test-sessions/%s/%s" % (r["session_slug"], r["file"])
        text = read_trace(ref)
        for e in EVENTS:
            q = r.get(e + "_quote", "")
            if q and norm(q) not in text:
                fails += 1; print("FAIL", r["session_slug"], e, repr(q[:80]))
    print("calibration rows", len(rows), "containment failures", fails)

if __name__ == "__main__":
    main()
