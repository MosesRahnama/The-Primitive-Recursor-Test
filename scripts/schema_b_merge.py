"""Merge Schema B single-round extraction + validation into the final grid.

- Combines extraction slice CSVs into one grid (one row per session).
- Applies validation: verdict=clean -> extraction row is final; needs_adjudication -> take the
  resolved row from adjudication/ if present, else mark status=pending_adjudication.
- Backstop: re-checks every quote is a literal substring of the session response.txt.
Writes final_SCHEMA_B_grid.csv + merge_report.md. Tolerant of empty validation/adjudication
(produces a provisional grid from extraction alone).

Usage: python scripts/schema_b_merge.py
"""
import csv, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS = os.path.join(ROOT, "results", "schema-test-B-tests", "test-sessions")
SR = os.path.join(ROOT, "results", "schema-test-B-tests", "extraction", "single-round")
METHODS = ["A", "B", "C", "D", "E"]
FIELDS = ["session_slug"]
for m in METHODS:
    FIELDS += [f"method_{m}_terminates", f"method_{m}_in_boundary",
               f"method_{m}_terminates_quote", f"method_{m}_in_boundary_quote"]
FIELDS += ["both_methods", "final_selection_quote", "confidence", "extraction_notes"]
QUOTE_FIELDS = [f"method_{m}_{ax}_quote" for m in METHODS for ax in ("terminates", "in_boundary")] + ["final_selection_quote"]


def load_dir(sub):
    out = {}
    for p in glob.glob(os.path.join(SR, sub, "*.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            s = r.get("session_slug", "").strip()
            if s:
                out[s] = r
    return out


def response_of(slug):
    p = os.path.join(SESS, slug, "response.txt")
    return open(p, encoding="utf-8-sig", errors="replace").read() if os.path.exists(p) else ""


def main():
    extraction = load_dir("extraction")
    validation = load_dir("validation")
    adjud = load_dir("adjudication")
    final_rows, pending, quote_fail, dup = [], [], [], []

    for slug, ext in extraction.items():
        v = validation.get(slug)
        row = dict(ext)
        status = "final"
        if v and v.get("verdict", "").strip() == "needs_adjudication":
            if slug in adjud:
                row = {**ext, **{k: val for k, val in adjud[slug].items() if val != ""}}
                status = "adjudicated"
            else:
                status = "pending_adjudication"
                pending.append(slug)
        elif not v:
            status = "unvalidated"
        resp = response_of(slug)
        for qf in QUOTE_FIELDS:
            q = (row.get(qf) or "").strip()
            if q and q not in resp:
                quote_fail.append((slug, qf))
        row["_status"] = status
        final_rows.append(row)

    out = os.path.join(SR, "final_SCHEMA_B_grid.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + ["_status"], extrasaction="ignore")
        w.writeheader(); w.writerows(final_rows)

    nval = sum(1 for s in extraction if s in validation)
    nclean = sum(1 for s, v in validation.items() if v.get("verdict", "").strip() == "clean")
    rep = ["# Schema B merge report", "",
           "- Extraction rows: %d" % len(extraction),
           "- Validated: %d (clean %d, needs_adjudication %d)" % (nval, nclean, nval - nclean),
           "- Adjudicated applied: %d" % sum(1 for r in final_rows if r["_status"] == "adjudicated"),
           "- Pending adjudication: %d %s" % (len(pending), pending[:10]),
           "- Unvalidated (extraction only): %d" % sum(1 for r in final_rows if r["_status"] == "unvalidated"),
           "- Quote substring failures: %d %s" % (len(quote_fail), quote_fail[:10]), ""]
    open(os.path.join(SR, "merge_report.md"), "w", encoding="utf-8").write("\n".join(rep))
    print("merged %d rows -> %s" % (len(final_rows), out))
    print("  validated=%d clean=%d pending_adjud=%d quote_fail=%d" % (nval, nclean, len(pending), len(quote_fail)))
    if quote_fail:
        print("  first quote failures:", quote_fail[:5])


if __name__ == "__main__":
    main()
