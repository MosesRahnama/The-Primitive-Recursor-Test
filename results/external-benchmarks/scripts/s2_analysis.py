"""Study 2: reader sensitivity to a dropped condition on the PRMBench missing_condition pairs.

Each pair has an original process and a modified twin in which a condition was dropped; the readers saw each
process alone under a random id, twins in different batches. Score per process: dropped=yes -> 1 (confidence
high) or 0.5 (confidence low), no -> 0. Paired AUROC = P(score_mod > score_orig) + 0.5 P(tie).
Also: sensitivity (dropped=yes on the modified twin), flags on the unmodified twin (dropped=yes on the original), and whether the
reader's step falls at or after the first injected error step.
Inputs: data/merged_prmbench.csv, data/labels_prmbench.csv. Output: tables/s2_prmbench.csv.
"""
import io, os, csv, json, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, TABLES, clopper_pearson, pct

def readcsv(p): return list(csv.DictReader(io.open(p, encoding="utf-8-sig", newline="")))
merged = {r["id"]: r for r in readcsv(os.path.join(DATA, "merged_prmbench.csv"))}
pairs = readcsv(os.path.join(DATA, "labels_prmbench.csv"))

def score(r):
    if r["dropped"] == "yes": return 0.5 if r["confidence"] == "low" else 1.0
    if r["dropped"] == "no": return 0.0
    return None
def toint(s):
    try: return int(float(s))
    except Exception: return None

rows_out = []
def out(population, measure, k, n, note=""):
    lo, hi = clopper_pearson(k, n)
    rows_out.append({"study": "S2", "corpus": "PRMBench missing_condition", "population": population, "measure": measure, "numerator": k, "denominator": n,
                     "rate_pct": round(100.0 * k / n, 2) if n else "", "cp_lo": round(100 * lo, 1) if n else "", "cp_hi": round(100 * hi, 1) if n else "", "note": note})

wins = ties = losses = 0; sens = fa = 0; n_pairs = 0; step_pos = Counter(); qdiff = Counter()
for p in pairs:
    o, m = merged.get(p["original_id"]), merged.get(p["modified_id"])
    if not o or not m: continue
    so, sm = score(o), score(m)
    if so is None or sm is None: continue
    n_pairs += 1
    if sm > so: wins += 1
    elif sm == so: ties += 1
    else: losses += 1
    sens += m["dropped"] == "yes"; fa += o["dropped"] == "yes"
    qdiff[(p["question_differs"], m["dropped"] == "yes")] += 1
    if m["dropped"] == "yes":
        st = toint(m["step"]); errs = json.loads(p["error_steps"]) if p["error_steps"] else []
        first = min(errs) if errs else None
        if st is None or first is None: step_pos["unknown"] += 1
        else: step_pos["before" if st < first else ("at" if st == first else "after")] += 1
auc = (wins + 0.5 * ties) / n_pairs if n_pairs else float("nan")
print("pairs scored %d; paired AUROC %.3f (wins %d ties %d losses %d)" % (n_pairs, auc, wins, ties, losses))
print("sensitivity (dropped=yes on modified) %s; flags on the unmodified twin (dropped=yes on original) %s" % (pct(sens, n_pairs), pct(fa, n_pairs)))
print("reader step vs first injected error step:", dict(step_pos))
print("detection by whether the question text itself differs:", {("question differs" if k[0] == "True" else "same question", k[1]): v for k, v in qdiff.items()})
if n_pairs:
    out("pairs with both twins coded", "paired AUROC x 100", round(auc * n_pairs), n_pairs, "wins %d ties %d losses %d" % (wins, ties, losses))
# single-twin state: how many processes of each kind have been coded so far, and the flag rate on each
kind = {p["original_id"]: "original" for p in pairs}; kind.update({p["modified_id"]: "modified" for p in pairs})
c = Counter((kind.get(i, "?"), r["dropped"]) for i, r in merged.items() if r["dropped"] in ("yes", "no"))
for k in ("original", "modified"):
    n = c[(k, "yes")] + c[(k, "no")]
    if n:
        print("%s twins coded so far: dropped=yes %s" % (k, pct(c[(k, "yes")], n)))
        out("%s twins coded so far" % k, "dropped condition coded yes", c[(k, "yes")], n)
out("modified twins", "dropped condition coded yes (sensitivity)", sens, n_pairs)
out("original twins", "dropped condition coded yes (flag on the unmodified twin)", fa, n_pairs)
for k in ("before", "at", "after", "unknown"):
    out("modified twins coded yes", "reader step %s the first injected error step" % k, step_pos[k], sum(step_pos.values()))
for (q, d), v in qdiff.items():
    out("modified twins, question %s" % ("differs" if q == "True" else "same"), "coded yes" if d else "coded no", v, sum(x for (qq, _), x in qdiff.items() if qq == q))
# agreement where both readers read
pairs_ab = [(r["dropped_A"], r["dropped_B"]) for r in merged.values() if r["dropped_A"] and r["dropped_B"]]
if pairs_ab:
    ag = sum(a == b for a, b in pairs_ab)
    print("reader agreement on dropped: %s" % pct(ag, len(pairs_ab)))
    out("processes read by both readers", "readers agree on dropped", ag, len(pairs_ab))
with io.open(os.path.join(TABLES, "s2_prmbench.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys())); w.writeheader(); w.writerows(rows_out)
