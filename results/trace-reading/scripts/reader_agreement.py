"""Inter-reader agreement per arm and field, before adjudication: raw agreement, Cohen's kappa, containment failures.

Reads data/extraction_merged.csv, writes tables/reader_agreement.csv and prints it.
"""
import csv, io, os
from collections import Counter
from common import DATA, TABLES, FIELDS, ARM_OF

def kappa(pairs):
    n = len(pairs)
    if n == 0: return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[v] * cb[v] for v in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")

def main():
    R = list(csv.DictReader(io.open(os.path.join(DATA, "extraction_merged.csv"), encoding="utf-8", newline="")))
    out = []
    arms = sorted(set(ARM_OF.get(r["file"].split("/")[0], r["file"].split("/")[0]) for r in R))
    for arm in arms:
        S = [r for r in R if ARM_OF.get(r["file"].split("/")[0], "") == arm and r["in_A"] == "yes" and r["in_B"] == "yes"]
        for k in FIELDS:
            pairs = [(r[k + "_A"], r[k + "_B"]) for r in S]
            agree = sum(1 for a, b in pairs if a == b)
            fa = sum(1 for r in S if r[k + "_A_contain"] == "FAIL"); fb = sum(1 for r in S if r[k + "_B_contain"] == "FAIL")
            out.append({"arm": arm, "field": k, "n_double_read": len(S), "agree": agree,
                        "agree_rate": "%.3f" % (agree / len(S)) if S else "", "kappa": "%.3f" % kappa(pairs) if S else "",
                        "quote_fail_A": fa, "quote_fail_B": fb})
    os.makedirs(TABLES, exist_ok=True)
    with io.open(os.path.join(TABLES, "reader_agreement.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    for o in out:
        print("%-8s %-24s n=%3d agree=%s kappa=%s failA=%d failB=%d" % (o["arm"], o["field"], o["n_double_read"], o["agree_rate"], o["kappa"], o["quote_fail_A"], o["quote_fail_B"]))

if __name__ == "__main__":
    main()
