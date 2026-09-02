"""Build the Schema B single-round extraction worklist and agent slices.

Scans test-sessions for usable sessions (response.txt present and not an [ERROR]
placeholder), writes worklist.csv, and splits the slugs into extraction slice files
(one per agent). Run AFTER the corpus run is complete.

Usage: python scripts/schema_b_make_worklist.py [slice_size]   (default 16)
"""
import csv, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS = os.path.join(ROOT, "results", "schema-test-B-tests", "test-sessions")
SR = os.path.join(ROOT, "results", "schema-test-B-tests", "extraction", "single-round")
SLICE_DIR = os.path.join(SR, "extraction", "_slices")


def usable(d):
    r = os.path.join(d, "response.txt")
    if not (os.path.exists(os.path.join(d, "session.json")) and os.path.exists(r)):
        return False
    return not open(r, encoding="utf-8", errors="replace").read(8).startswith("[ERROR]")


def main():
    slice_size = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    os.makedirs(SLICE_DIR, exist_ok=True)
    rows = []
    for d in sorted(glob.glob(os.path.join(SESS, "*__*"))):
        if not os.path.isdir(d) or not usable(d):
            continue
        slug = os.path.basename(d)
        variant = "control" if "-control__" in slug else "regular"
        rows.append({"session_slug": slug, "variant": variant,
                     "response_path": os.path.join(SESS, slug, "response.txt")})
    with open(os.path.join(SR, "worklist.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["session_slug", "variant", "response_path"])
        w.writeheader(); w.writerows(rows)
    # slices: balanced, keep variants interleaved (already interleaved by sort)
    n_slices = -(-len(rows) // slice_size)
    for k in range(n_slices):
        chunk = rows[k * slice_size:(k + 1) * slice_size]
        lines = ["# Schema B extraction slice %d of %d (%d sessions)" % (k + 1, n_slices, len(chunk)),
                 "# Read each response.txt in full; follow SINGLE_ROUND_EXTRACTION_DISPATCH.md.", ""]
        for r in chunk:
            lines.append("%s\t%s" % (r["session_slug"], r["response_path"]))
        open(os.path.join(SLICE_DIR, "slice_%02d.txt" % (k + 1)), "w", encoding="utf-8").write("\n".join(lines))
    nreg = sum(1 for r in rows if r["variant"] == "regular")
    print("worklist: %d sessions (%d regular, %d control) -> %d slices of <=%d" % (
        len(rows), nreg, len(rows) - nreg, n_slices, slice_size))


if __name__ == "__main__":
    main()
