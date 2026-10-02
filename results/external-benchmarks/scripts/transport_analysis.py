r"""Text features against published error labels on the labeled trace corpora. Reads data/corpus_features.csv
(transport_features.py) and data/corpus_recoded.jsonl (recode_corpora.py); writes tables/transport_results.csv and
prints the tables. The features were fixed before any label was read; no threshold is chosen on the evaluation
corpus, and the logistic model is L2-regularized with a fixed C.
"""
import csv, io, json, math, os, random, re, sys
from collections import defaultdict, Counter
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, TABLES
FEAT = ["hedge_body", "hedge_final", "hedge_collapse", "echo_mass", "novelty_rate", "repeat_streak",
        "verdict_lead", "reflection_count", "confidence_final", "n_steps", "n_chars"]
BASE = ["n_steps", "n_chars"]
OUT = []


def out(table, **k):
    k["table"] = table; OUT.append(k)


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))


def auroc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]; neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg: return float("nan")
    # rank-based with tie handling
    allv = sorted(set(scores)); rank = {}
    xs = sorted(scores); i = 0
    while i < len(xs):
        j = i
        while j < len(xs) and xs[j] == xs[i]: j += 1
        rank[xs[i]] = (i + 1 + j) / 2.0; i = j
    rs = sum(rank[s] for s in pos)
    return (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def avg_precision(scores, labels):
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = 0; ap = 0.0; P = sum(labels)
    if P == 0: return float("nan")
    for k, i in enumerate(order, 1):
        if labels[i]:
            tp += 1; ap += tp / k
    return ap / P


def logistic_fit(X, y, C=1.0, iters=400, lr=0.1):
    mu = X.mean(0); sd = X.std(0) + 1e-9; Z = (X - mu) / sd
    w = np.zeros(Z.shape[1]); b = 0.0; n = len(y)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = Z.T @ (p - y) / n + w / (C * n); gb = (p - y).mean()
        w -= lr * g; b -= lr * gb
    return mu, sd, w, b


def logistic_predict(m, X):
    mu, sd, w, b = m
    return 1 / (1 + np.exp(-(((X - mu) / sd) @ w + b)))


def grouped_cv(rows, feats, groupkey):
    groups = sorted(set(r[groupkey] for r in rows))
    if len(groups) < 3:  # fall back to 5 random folds
        random.seed(20260827); idx = list(range(len(rows))); random.shuffle(idx)
        folds = [set(idx[i::5]) for i in range(5)]
        assign = {i: f for f, s in enumerate(folds) for i in s}
        groups = list(range(5)); gk = lambda i, r: assign[i]
    else:
        gk = lambda i, r: r[groupkey]
    X = np.array([[float(r[f]) for f in feats] for r in rows]); y = np.array([1.0 if r["y"] else 0.0 for r in rows])
    pred = np.zeros(len(rows))
    for g in groups:
        te = np.array([gk(i, r) == g for i, r in enumerate(rows)]); tr = ~te
        if te.sum() == 0 or tr.sum() == 0 or len(set(y[tr])) < 2: continue
        m = logistic_fit(X[tr], y[tr]); pred[te] = logistic_predict(m, X[te])
    return pred, y


def risk_at_coverage(pred, y, cov=0.2):
    order = np.argsort(pred); k = max(1, int(len(pred) * cov))
    low = order[:k]; return y[low].mean(), y.mean()


def main():
    feats = list(csv.DictReader(io.open(os.path.join(DATA, "corpus_features.csv"), encoding="utf-8", newline="")))
    for r in feats:
        r["y"] = r["has_error"] == "True"
        r["fc"] = None if r["final_correct"] in ("", "None") else r["final_correct"] == "True"
    natural = [r for r in feats if r["provenance"] == "natural"]

    # ---------- 1. correct final answers with an annotated reasoning error ----------
    print("=== 1. Correct final answers with an annotated reasoning error ===")
    print("%-14s %-26s %5s %5s %6s   %s" % ("corpus", "split", "n_ok", "error", "%", "Wilson 95%"))
    for (c, s), grp in sorted(defaultdict(list, {k: [r for r in natural if (r["corpus"], r["split"]) == k]
                                                 for k in set((r["corpus"], r["split"]) for r in natural)}).items()):
        ok = [r for r in grp if r["fc"] is True]
        if not ok: continue
        k = sum(1 for r in ok if r["y"]); lo, hi = wilson(k, len(ok))
        print("%-14s %-26s %5d %5d %5.1f%%   [%.1f, %.1f]" % (c, s, len(ok), k, 100 * k / len(ok), lo, hi))
        out("correct_answer_error",corpus=c, split=s, n_correct=len(ok), with_error=k,pct=round(100 * k / len(ok), 1), lo=round(lo, 1), hi=round(hi, 1))
    for c in sorted(set(r["corpus"] for r in natural)):
        ok = [r for r in natural if r["corpus"] == c and r["fc"] is True]
        if ok:
            k = sum(1 for r in ok if r["y"]); lo, hi = wilson(k, len(ok))
            print("%-14s %-26s %5d %5d %5.1f%%   [%.1f, %.1f]" % (c, "ALL", len(ok), k, 100 * k / len(ok), lo, hi))
            out("correct_answer_error",corpus=c, split="ALL", n_correct=len(ok), with_error=k,pct=round(100 * k / len(ok), 1), lo=round(lo, 1), hi=round(hi, 1))
    # the mirror cell: wrong answer with a clean trace
    print("\n   wrong final answer but no annotated error (the mirror cell):")
    for c in sorted(set(r["corpus"] for r in natural)):
        bad = [r for r in natural if r["corpus"] == c and r["fc"] is False]
        if bad:
            k = sum(1 for r in bad if not r["y"])
            print("   %-14s %d / %d" % (c, k, len(bad))); out("mirror_cell", corpus=c, wrong_clean=k, n_wrong=len(bad))

    # ---------- 2. per-feature AUROC ----------
    print("\n=== 2. Per-feature AUROC for has_error, corpora with real negatives (natural errors only) ===")
    corpora = [c for c in sorted(set(r["corpus"] for r in natural)) if 0 < sum(r["y"] for r in natural if r["corpus"] == c) < sum(1 for r in natural if r["corpus"] == c)]
    print("%-18s " % "feature" + " ".join("%12s" % c for c in corpora))
    for f in FEAT:
        vals = []
        for c in corpora:
            grp = [r for r in natural if r["corpus"] == c]
            a = auroc([float(r[f]) for r in grp], [r["y"] for r in grp]); vals.append(a)
            out("feature_auroc", corpus=c, feature=f, auroc=round(a, 3), n=len(grp), positives=sum(r["y"] for r in grp))
        print("%-18s " % f + " ".join("%12.3f" % v for v in vals))

    # ---------- 3. grouped-CV models ----------
    print("\n=== 3. Grouped out-of-fold logistic models: text features with length vs length alone ===")
    print("%-14s %-10s %6s %6s %8s %8s %8s %12s" % ("corpus", "groupby", "n", "prev", "AUC_len", "AUC_all", "AP_all", "risk@20%cov"))
    for c in corpora:
        grp = [r for r in natural if r["corpus"] == c]
        gkey = "generator" if len(set(r["generator"] for r in grp)) >= 3 else "split"
        pl, y = grouped_cv(grp, BASE, gkey); pa, _ = grouped_cv(grp, FEAT, gkey)
        al, aa = auroc(list(pl), list(y)), auroc(list(pa), list(y)); ap = avg_precision(list(pa), list(y))
        r20, base = risk_at_coverage(pa, y)
        print("%-14s %-10s %6d %6.3f %8.3f %8.3f %8.3f %6.3f/%.3f" % (c, gkey, len(grp), y.mean(), al, aa, ap, r20, base))
        out("grouped_cv", corpus=c, groupby=gkey, n=len(grp), prevalence=round(float(y.mean()), 3), auroc_length=round(al, 3),
            auroc_features=round(aa, 3), ap_features=round(ap, 3), risk_at_20pct_coverage=round(float(r20), 3), base_risk=round(float(base), 3))
        # the same comparison among correct-final-answer traces only
        ok = [r for r in grp if r["fc"] is True]
        if ok and 0 < sum(r["y"] for r in ok) < len(ok):
            pl2, y2 = grouped_cv(ok, BASE, gkey); pa2, _ = grouped_cv(ok, FEAT, gkey)
            al2, aa2 = auroc(list(pl2), list(y2)), auroc(list(pa2), list(y2))
            print("%-14s %-10s %6d %6.3f %8.3f %8.3f   (correct final answers only)" % (c + ":correct", gkey, len(ok), y2.mean(), al2, aa2))
            out("grouped_cv_correct_answers", corpus=c, groupby=gkey, n=len(ok), prevalence=round(float(y2.mean()), 3), auroc_length=round(al2, 3), auroc_features=round(aa2, 3))

    # ---------- 4. echo detector vs DeltaBench 'unuseful' ----------
    print("\n=== 4. Echo/novelty features against DeltaBench section annotations ===")
    rec = [json.loads(l) for l in io.open(os.path.join(DATA, "corpus_recoded.jsonl"), encoding="utf-8")]
    db = [r for r in rec if r["corpus"] == "deltabench"]
    from transport_features import grams
    nov_s, lab_u, lab_e, pos_frac = [], [], [], []
    for r in db:
        pg = grams(r["problem"]); seen = set(pg); n = len(r["steps"])
        for i, s in enumerate(r["steps"]):
            g = grams(s)
            if not g: continue
            nov_s.append(len(g - seen) / len(g)); lab_u.append(i in r["unuseful_positions"]); lab_e.append(i in r["error_positions"]); pos_frac.append(i / max(1, n - 1))
            seen |= g
    a_u = auroc([-x for x in nov_s], lab_u); a_e = auroc([-x for x in nov_s], lab_e); a_pos = auroc(pos_frac, lab_e)
    print("   sections=%d  unuseful=%d  error=%d" % (len(nov_s), sum(lab_u), sum(lab_e)))
    print("   AUROC(low novelty -> unuseful section) = %.3f" % a_u)
    print("   AUROC(low novelty -> error section)    = %.3f   AUROC(position -> error) = %.3f" % (a_e, a_pos))
    out("deltabench_sections", sections=len(nov_s), unuseful=sum(lab_u), error=sum(lab_e), auroc_lownovelty_unuseful=round(a_u, 3), auroc_lownovelty_error=round(a_e, 3), auroc_position_error=round(a_pos, 3))
    # post-error strategy shift
    before = after = nb = na = 0
    for r in db:
        if not r["error_positions"]: continue
        fe = min(r["error_positions"]); n = len(r["steps"])
        for i in range(n):
            if i < fe: nb += 1; before += i in r["strategy_shift_positions"]
            elif i > fe: na += 1; after += i in r["strategy_shift_positions"]
    print("   strategy-shift rate per section before first error %.3f (n=%d)  after %.3f (n=%d)" % (before / max(1, nb), nb, after / max(1, na), na))
    out("post_error_shift", before_rate=round(before / max(1, nb), 4), n_before=nb, after_rate=round(after / max(1, na), 4), n_after=na)

    # ---------- 5. derived but not released ----------
    print("\n=== 5. Derived but not released: gold answer present in the steps of a wrong-final-answer trace ===")
    for c in ("mrgsm8k", "bbm", "deltabench"):
        grp = [r for r in rec if r["corpus"] == c and r["final_correct"] is False and r.get("gold_answer")]
        hit = 0; n = 0
        for r in grp:
            g = str(r["gold_answer"]).strip()
            if len(g) < 1: continue
            body = "\n".join(r["steps"][:-1]) if len(r["steps"]) > 1 else ""
            pat = r"(?<![\w.])" + re.escape(g) + r"(?![\w.])"
            n += 1; hit += bool(re.search(pat, body, flags=re.I))
        print("   %-12s %d / %d = %.1f%%  (bounded literal match in non-final steps)" % (c, hit, n, 100 * hit / max(1, n)))
        out("derived_not_released", corpus=c, hit=hit, n=n, pct=round(100 * hit / max(1, n), 1))

    # ---------- 6. DeltaBench: strategy changes and reflections around the first error ----------
    # strategy-change rate per section, excluding the first erroneous section, the two sections before it and the one
    # after it; reflection density per section over all sections before and after the first erroneous section
    print("\n=== 6. DeltaBench: strategy changes and reflections before and after the first error ===")
    for label, keep in (("all error traces", lambda fe, n: True), ("first error at >=30% depth", lambda fe, n: fe / n >= 0.3)):
        nb = sb = na = sa = mb = rb = ma = ra = 0
        for r in db:
            if not r["error_positions"]: continue
            fe = min(r["error_positions"]); n = len(r["steps"])
            if not keep(fe, n): continue
            sh, rf = set(r["strategy_shift_positions"]), set(r["reflection_positions"])
            for i in range(n):
                if i < fe:
                    mb += 1; rb += i in rf
                    if i < fe - 2: nb += 1; sb += i in sh
                elif i > fe:
                    ma += 1; ra += i in rf
                    if i > fe + 1: na += 1; sa += i in sh
        print("   %-28s strategy changes per section: before %.4f (n=%d), after %.4f (n=%d); reflection density: before %.4f (n=%d), after %.4f (n=%d)" % (
            label, sb / max(1, nb), nb, sa / max(1, na), na, rb / max(1, mb), mb, ra / max(1, ma), ma))
        out("deltabench_around_first_error", subset=label, strategy_before=round(sb / max(1, nb), 4), n_strategy_before=nb,
            strategy_after=round(sa / max(1, na), 4), n_strategy_after=na, reflection_before=round(rb / max(1, mb), 4), n_reflection_before=mb,
            reflection_after=round(ra / max(1, ma), 4), n_reflection_after=ma)

    # ---------- 7. ProcessBench: a self-check after the first error ----------
    # an error trace is split by whether any step after the first erroneous step matches the reflection lexicon of
    # transport_features.py; the outcome is a correct final answer
    print("\n=== 7. ProcessBench error traces: a self-check after the first error and a correct final answer ===")
    from transport_features import REFLECT
    pb = [r for r in rec if r["corpus"] == "processbench" and r["error_positions"]]
    for split in sorted(set(r["split"] for r in pb)) + ["ALL"]:
        grp = [r for r in pb if split == "ALL" or r["split"] == split]
        flags = [any(REFLECT.search(s) for s in r["steps"][min(r["error_positions"]) + 1:]) for r in grp]
        nc = sum(flags); kc = sum(1 for r, f in zip(grp, flags) if f and r["final_correct"])
        nn = len(grp) - nc; kn = sum(1 for r, f in zip(grp, flags) if not f and r["final_correct"])
        print("   %-14s error traces %4d | self-check after the error %3d -> correct %5.1f%% | none %4d -> correct %5.1f%%" % (
            split, len(grp), nc, 100 * kc / max(1, nc), nn, 100 * kn / max(1, nn)))
        out("processbench_selfcheck", split=split, n_error_traces=len(grp), n_selfcheck=nc, correct_selfcheck=kc, n_none=nn, correct_none=kn)

    with io.open(os.path.join(TABLES, "transport_results.csv"), "w", encoding="utf-8", newline="") as f:
        keys = ["table"] + sorted(set(k for o in OUT for k in o if k != "table"))
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n"); w.writeheader(); w.writerows(OUT)
    print("\nwrote tables/transport_results.csv (%d rows)" % len(OUT))


if __name__ == "__main__":
    main()
