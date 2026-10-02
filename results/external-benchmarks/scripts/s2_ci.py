"""Study 2 uncertainty, as cited in the paper: bootstrap interval for the paired AUROC over PRMBench pairs
(10,000 draws, seed 20260908) and the sign test on untied pairs. Scores as in s2_analysis.py. Run after
`merge.py prmbench single`. Usage: python s2_ci.py"""
import io, os, csv, sys, random
from math import lgamma, exp
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, TABLES, clopper_pearson

def readcsv(p): return list(csv.DictReader(io.open(p, encoding="utf-8-sig", newline="")))
merged = {r["id"]: r for r in readcsv(os.path.join(DATA, "merged_prmbench.csv"))}
pairs = readcsv(os.path.join(DATA, "labels_prmbench.csv"))

def score(r):
    if r["dropped"] == "yes": return 0.5 if r["confidence"] == "low" else 1.0
    if r["dropped"] == "no": return 0.0
    return None

vals = []
for p in pairs:
    o, m = merged.get(p["original_id"]), merged.get(p["modified_id"])
    if not o or not m: continue
    so, sm = score(o), score(m)
    if so is None or sm is None: continue
    vals.append(1.0 if sm > so else (0.5 if sm == so else 0.0))
n = len(vals); auc = sum(vals) / n
print("pairs %d, AUROC %.3f (wins %d ties %d losses %d)" % (n, auc, vals.count(1.0), vals.count(0.5), vals.count(0.0)))
rng = random.Random(20260908)
b = sorted(sum(rng.choice(vals) for _ in range(n)) / n for _ in range(10000))
print("bootstrap 95%% CI %.3f to %.3f" % (b[250], b[9750]))
w, l = vals.count(1.0), vals.count(0.0); nt = w + l
def lch(N, k): return lgamma(N + 1) - lgamma(k + 1) - lgamma(N - k + 1)
p2 = 2 * sum(exp(lch(nt, k) - nt * 0.6931471805599453) for k in range(w, nt + 1))
lo, hi = clopper_pearson(w, nt)
print("untied pairs %d: %d rank the modified process higher (%.1f%%, 95%% CI %.1f to %.1f), sign test p = %.3g" % (nt, w, 100.0 * w / nt, 100 * lo, 100 * hi, min(1.0, p2)))
row = {"pairs": n, "auroc": round(auc, 3), "wins": w, "ties": vals.count(0.5), "losses": l, "auroc_lo": round(b[250], 3), "auroc_hi": round(b[9750], 3),
       "bootstrap_draws": 10000, "seed": 20260908, "untied_right_pct": round(100.0 * w / nt, 1), "untied_right_lo": round(100 * lo, 1),
       "untied_right_hi": round(100 * hi, 1), "sign_test_p": "%.3g" % min(1.0, p2)}
with io.open(os.path.join(TABLES, "s2_uncertainty.csv"), "w", encoding="utf-8", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(row.keys()), lineterminator="\n"); wr.writeheader(); wr.writerow(row)
