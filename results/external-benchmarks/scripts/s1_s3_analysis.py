"""Studies 1 and 3 on MR-GSM8K and PRM800K.

Study 1: among correct-answer solutions, the decisive-condition statement (E1) against the solution label
         (correct / wrong = the correct-answer, wrong-solution cell). Fisher two-sided, Clopper-Pearson intervals.
Study 3: the misread-of-the-given code (E8) against the labeled first error: presence in wrong and in correct
         solutions, and where E8 lands relative to the labeled first error step.
Inputs: data/merged_<corpus>.csv (merge.py <corpus> single), data/labels_<corpus>.csv, data/keys_<corpus>.csv;
reader agreement uses data/merged_<corpus>_two_readers.csv (merge.py <corpus>) when it is present.
Output: tables/s1_s3_<corpus>.csv, tables/reader_agreement_<corpus>.csv, printed summary.
"""
import io, os, csv, sys
from collections import Counter, defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, TABLES, fisher, clopper_pearson, pct

def readcsv(p): return list(csv.DictReader(io.open(p, encoding="utf-8-sig", newline="")))

def kappa(pairs):
    pairs = [(a, b) for a, b in pairs if a and b]
    if not pairs: return float("nan"), 0
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan"), n

def toint(s):
    try: return int(float(s))
    except Exception: return None

for corpus in sys.argv[1:] or ("mrgsm8k", "prm800k"):
    merged = {r["id"]: r for r in readcsv(os.path.join(DATA, "merged_%s.csv" % corpus))}
    labels = {r["id"]: r for r in readcsv(os.path.join(DATA, "labels_%s.csv" % corpus))}
    keys = {r["id"]: r for r in readcsv(os.path.join(DATA, "keys_%s.csv" % corpus))}
    rows_out = []
    def out(study, population, measure, k, n, note=""):
        lo, hi = clopper_pearson(k, n)
        rows_out.append({"study": study, "corpus": corpus, "population": population, "measure": measure, "numerator": k, "denominator": n,
                         "rate_pct": round(100.0 * k / n, 2) if n else "", "cp_lo": round(100 * lo, 1) if n else "", "cp_hi": round(100 * hi, 1) if n else "", "note": note})
    ids = [i for i in labels if i in merged]
    coded = [i for i in ids if merged[i]["E1"] in ("yes", "no")]
    print("=== %s: labeled %d, merged %d, E1 decided %d" % (corpus, len(labels), len(ids), len(coded)))
    # ---- Study 1 ----
    def s1(pop_ids, label, extra=""):
        c = Counter((labels[i]["solution_correct"], merged[i]["E1"]) for i in pop_ids if merged[i]["E1"] in ("yes", "no"))
        a, b = c[("correct", "yes")], c[("correct", "no")]; cc, d = c[("wrong", "yes")], c[("wrong", "no")]
        p = fisher(a, b, cc, d)
        print("  S1 %-40s E1 | correct solution %s | wrong solution %s | Fisher p=%.3g" % (label, pct(a, a + b), pct(cc, cc + d), p))
        out("S1", "%s, correct answer, correct solution" % label, "E1 decisive-condition statement", a, a + b, "Fisher p=%.3g vs wrong solution%s" % (p, extra))
        out("S1", "%s, correct answer, wrong solution" % label, "E1 decisive-condition statement", cc, cc + d)
        # E8 in the same cell
        c8 = Counter((labels[i]["solution_correct"], merged[i]["E8"]) for i in pop_ids if merged[i]["E8"] in ("yes", "no"))
        a8, b8, c8w, d8 = c8[("correct", "yes")], c8[("correct", "no")], c8[("wrong", "yes")], c8[("wrong", "no")]
        p8 = fisher(a8, b8, c8w, d8)
        print("     %-40s E8 | correct solution %s | wrong solution %s | Fisher p=%.3g" % ("", pct(a8, a8 + b8), pct(c8w, c8w + d8), p8))
        out("S1", "%s, correct answer, correct solution" % label, "E8 misread of the given", a8, a8 + b8, "Fisher p=%.3g vs wrong solution" % p8)
        out("S1", "%s, correct answer, wrong solution" % label, "E8 misread of the given", c8w, c8w + d8)
        # E1 and no E8 jointly
        cj = Counter((labels[i]["solution_correct"], merged[i]["E1"] == "yes" and merged[i]["E8"] == "no") for i in pop_ids if merged[i]["E1"] in ("yes", "no") and merged[i]["E8"] in ("yes", "no"))
        aj, bj, cjw, dj = cj[("correct", True)], cj[("correct", False)], cj[("wrong", True)], cj[("wrong", False)]
        print("     %-40s E1 and no E8 | correct %s | wrong %s | p=%.3g" % ("", pct(aj, aj + bj), pct(cjw, cjw + dj), fisher(aj, bj, cjw, dj)))
        out("S1", "%s, correct answer, correct solution" % label, "E1 stated and no E8", aj, aj + bj, "Fisher p=%.3g" % fisher(aj, bj, cjw, dj))
        out("S1", "%s, correct answer, wrong solution" % label, "E1 stated and no E8", cjw, cjw + dj)
    correct_ans = [i for i in ids if labels[i]["answer_correct"] == "correct"]
    s1(correct_ans, "all correct answers")
    both_ok = [i for i in correct_ans if keys.get(i, {}).get("problem_quote_contained") == "ok" and keys.get(i, {}).get("gold_quote_contained") == "ok"]
    s1(both_ok, "correct answers, key quotes contained", " (sensitivity: keys with both quotes contained)")
    if corpus == "mrgsm8k":
        for qt in ("original", "reversed", "POT"):
            s1([i for i in correct_ans if labels[i]["question_type"] == qt], "correct answers, %s" % qt)
    # by condition type
    for ct in sorted(set(keys.get(i, {}).get("condition_type", "") for i in correct_ans)):
        sub = [i for i in correct_ans if keys.get(i, {}).get("condition_type", "") == ct]
        if len(sub) >= 40: s1(sub, "correct answers, condition type %s" % (ct or "none"))
    # ---- Study 3 ----
    wrong = [i for i in ids if labels[i]["solution_correct"] == "wrong" and merged[i]["E8"] in ("yes", "no")]
    right = [i for i in ids if labels[i]["solution_correct"] == "correct" and merged[i]["E8"] in ("yes", "no")]
    kw, kr = sum(merged[i]["E8"] == "yes" for i in wrong), sum(merged[i]["E8"] == "yes" for i in right)
    print("  S3 E8 present | wrong solutions %s | correct solutions %s | Fisher p=%.3g" % (pct(kw, len(wrong)), pct(kr, len(right)), fisher(kw, len(wrong) - kw, kr, len(right) - kr)))
    out("S3", "all wrong solutions", "E8 misread of the given", kw, len(wrong), "Fisher p=%.3g vs correct solutions" % fisher(kw, len(wrong) - kw, kr, len(right) - kr))
    out("S3", "all correct solutions", "E8 misread of the given (on solutions the corpus labels correct)", kr, len(right))
    pos = Counter(); depths = []
    for i in wrong:
        if merged[i]["E8"] != "yes": continue
        e8, fe, n = toint(merged[i]["E8_step"]), toint(labels[i]["first_error_step"]), toint(labels[i]["n_steps"])
        if e8 is None or fe is None: pos["unknown"] += 1; continue
        pos["before" if e8 < fe else ("at" if e8 == fe else "after")] += 1
        if n: depths.append(e8 / n)
    depths.sort()
    print("  S3 E8 step relative to labeled first error (wrong solutions): %s; median E8 relative depth %s" % (dict(pos), ("%.2f" % depths[len(depths) // 2]) if depths else "n/a"))
    for k in ("before", "at", "after", "unknown"):
        out("S3", "wrong solutions with E8", "E8 step %s the labeled first error" % k, pos[k], sum(pos.values()), "median E8 relative depth %s" % (("%.2f" % depths[len(depths) // 2]) if depths else "n/a"))
    kinds = Counter(merged[i]["E8_kind"] for i in wrong if merged[i]["E8"] == "yes")
    print("  S3 E8 kinds (wrong solutions):", dict(kinds))
    for k, v in kinds.items(): out("S3", "wrong solutions with E8", "E8 kind %s" % (k or "unspecified"), v, kw)
    # ---- reader agreement, on the items read twice (two-reader merge) ----
    tp = os.path.join(DATA, "merged_%s_two_readers.csv" % corpus)
    two = {r["id"]: r for r in readcsv(tp)} if os.path.exists(tp) else {}
    agree_rows = []
    for f in ("E1", "E8", "E8_kind"):
        pairs = [(two[i][f + "_A"], two[i][f + "_B"]) for i in ids if i in two]
        kap, n = kappa(pairs); ag = sum(a == b for a, b in pairs if a and b)
        agree_rows.append({"corpus": corpus, "field": f, "n_double_read": n, "agree": ag, "agree_rate": round(ag / n, 3) if n else "", "kappa": round(kap, 3) if n else ""})
        print("  agreement %-8s n=%d agree=%.3f kappa=%.3f" % (f, n, ag / n if n else float("nan"), kap))
    fails = Counter()
    for i in ids:
        for k, v in merged[i].items():
            if k.endswith("_contain") and v == "FAIL": fails[k] += 1
    print("  containment failures:", dict(fails))
    with io.open(os.path.join(TABLES, "s1_s3_%s.csv" % corpus), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys())); w.writeheader(); w.writerows(rows_out)
    with io.open(os.path.join(TABLES, "reader_agreement_%s.csv" % corpus), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agree_rows[0].keys())); w.writeheader(); w.writerows(agree_rows)
