"""Question-cluster bootstrap for the E8 difference among correct final answers, as cited in the paper:
rate(E8 yes | labeled-wrong solution) - rate(E8 yes | labeled-correct solution), resampling distinct question texts
(10,000 draws, seed 20260906). Run after `merge.py <corpus> single`. Usage: python cluster_ci.py"""
import io, os, csv, json, random, sys
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, TABLES

def readcsv(p): return list(csv.DictReader(io.open(p, encoding="utf-8-sig", newline="")))
out_rows = []

for corpus in ("mrgsm8k", "prm800k"):
    m = {r["id"]: r for r in readcsv(os.path.join(DATA, "merged_%s.csv" % corpus))}
    lab = {r["id"]: r for r in readcsv(os.path.join(DATA, "labels_%s.csv" % corpus))}
    q = {json.loads(l)["id"]: json.loads(l)["question"] for l in io.open(os.path.join(DATA, "reader_%s.jsonl" % corpus), encoding="utf-8") if l.strip()}
    rows = [(q[i], lab[i]["solution_correct"], m[i]["E8"] == "yes") for i in lab
            if i in m and lab[i]["answer_correct"] == "correct" and lab[i]["solution_correct"] in ("correct", "wrong") and m[i]["E8"] in ("yes", "no")]
    by_q = defaultdict(list)
    for qt, sol, e8 in rows: by_q[qt].append((sol, e8))
    keys = list(by_q)
    def diff(groups):
        w = [e for g in groups for s, e in g if s == "wrong"]; c = [e for g in groups for s, e in g if s == "correct"]
        return 100.0 * (sum(w) / len(w) - sum(c) / len(c)) if w and c else None
    obs = diff([by_q[k] for k in keys])
    rng = random.Random(20260906); vals = []
    for _ in range(10000):
        d = diff([by_q[rng.choice(keys)] for _ in keys])
        if d is not None: vals.append(d)
    vals.sort()
    w = [e for _, s, e in rows if s == "wrong"]; c = [e for _, s, e in rows if s == "correct"]
    print("%s: wrong %d/%d, correct %d/%d, %d distinct questions; difference %.1f points, 95%% cluster interval [%.1f, %.1f]"
          % (corpus, sum(w), len(w), sum(c), len(c), len(keys), obs, vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]))
    out_rows.append({"corpus": corpus, "wrong_with_e8": sum(w), "wrong": len(w), "correct_with_e8": sum(c), "correct": len(c),
                     "distinct_questions": len(keys), "difference_points": round(obs, 1),
                     "interval_lo": round(vals[int(0.025 * len(vals))], 1), "interval_hi": round(vals[int(0.975 * len(vals))], 1),
                     "draws": 10000, "seed": 20260906})

with io.open(os.path.join(TABLES, "cluster_intervals.csv"), "w", encoding="utf-8", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()), lineterminator="\n"); wr.writeheader(); wr.writerows(out_rows)
