"""A7 statistics layer: model-clustered bootstrap + sign-flip permutation, per plan §4/A7.

Sampling unit is the model family (12 on the new corpus). Every headline rate is
reported as the mean of per-model rates with a B=2000 cluster-bootstrap CI.
Rare cells use Wilson intervals. Paired contrasts use a sign-flip permutation over
per-model paired differences.
"""
import csv, os, math, random, json, collections, statistics

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
random.seed(20260726)
B = 2000
csv.field_size_limit(10**7)

rows = list(csv.DictReader(open(os.path.join(OUT, "thinking_trace_analysis.csv"), encoding="utf-8")))
live = [r for r in rows if r["excluded_stub"] == "no"]
new = [r for r in live if r["corpus"] == "new"]
old = [r for r in live if r["corpus"] == "old"]
OPEN_ENDED = {"schema-test-A-tests", "schema-test-A-new-system-tests", "test-01-kernel-tests"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def per_model(subset, num, den=lambda r: True):
    """{model: (k, n)} using the model family as the cluster."""
    d = collections.defaultdict(lambda: [0, 0])
    for r in subset:
        if not den(r):
            continue
        d[r["model_family"]][1] += 1
        if num(r):
            d[r["model_family"]][0] += 1
    return {m: tuple(v) for m, v in d.items()}


def cluster_boot(pm, B=B):
    """Mean of per-model rates + percentile CI over resampled model clusters."""
    models = [m for m, (k, n) in pm.items() if n > 0]
    if not models:
        return (float("nan"), float("nan"), float("nan"), 0, 0)
    rates = {m: pm[m][0] / pm[m][1] for m in models}
    point = statistics.mean(rates[m] for m in models)
    draws = []
    for _ in range(B):
        s = [random.choice(models) for _ in models]
        draws.append(statistics.mean(rates[m] for m in s))
    draws.sort()
    K = sum(pm[m][0] for m in models)
    N = sum(pm[m][1] for m in models)
    return (point, draws[int(0.025 * B)], draws[int(0.975 * B)], K, N)


def perm_paired(pmA, pmB, B=B):
    """Sign-flip permutation on per-model paired differences (A - B)."""
    common = sorted(set(pmA) & set(pmB))
    diffs = [pmA[m][0] / pmA[m][1] - pmB[m][0] / pmB[m][1]
             for m in common if pmA[m][1] and pmB[m][1]]
    if not diffs:
        return (float("nan"), float("nan"), 0)
    obs = statistics.mean(diffs)
    hits = 0
    for _ in range(B):
        v = statistics.mean(d * random.choice((1, -1)) for d in diffs)
        if abs(v) >= abs(obs) - 1e-12:
            hits += 1
    return (obs, (hits + 1) / (B + 1), len(diffs))


def fmt(res, pct=True):
    p, lo, hi, k, n = res
    if pct:
        return f"{100*p:.1f}% [{100*lo:.1f}, {100*hi:.1f}] (pooled {k}/{n})"
    return f"{p:.3f} [{lo:.3f}, {hi:.3f}] (n={n})"


report = {}
L = []
def say(s=""):
    L.append(s)
    print(s)

say("# Thinking-trace statistics (A7)")
say(f"rows total {len(rows)} | live {len(live)} | stub-excluded {len(rows)-len(live)} "
    f"| new {len(new)} | old {len(old)}")
say()

# ---------------------------------------------------------------- coverage
say("## Coverage")
by_suite = collections.Counter((r["corpus"], r["test_suite"]) for r in live)
for (c, s), n in sorted(by_suite.items()):
    say(f"  {c:4s} {s:44s} {n:5d}")
say(f"  model families (new corpus): {len(set(r['model_family'] for r in new))}")
say(f"  arms: {dict(collections.Counter(r['arm'] for r in new))}")
say(f"  turns: {dict(collections.Counter(r['turn'] for r in live))}")
say()

# A1-A5 exclude turn-2 (self-audit) per plan §7
a15 = [r for r in new if r["turn"] != "2"]
oe = [r for r in a15 if r["test_suite"] in OPEN_ENDED]

# ---------------------------------------------------------------- A1
say("## A1 Verdict-lead telemetry (new corpus, turn-2 excluded)")
have = [r for r in a15 if r["verdict_lead"] != ""]
say(f"traces with both a verdict event and a construction event: {len(have)}/{len(a15)}")
pm = per_model(have, lambda r: float(r["verdict_lead"]) > 0)
res = cluster_boot(pm); report["A1_verdict_first_share"] = res
say(f"  verdict BEFORE first construction: {fmt(res)}")
leads = [float(r["verdict_lead_frac"]) for r in have]
say(f"  verdict_lead as fraction of trace: median {statistics.median(leads):+.3f} "
    f"mean {statistics.mean(leads):+.3f}")
vp = [float(r['first_verdict_frac']) for r in a15 if r['first_verdict_frac'] != '']
say(f"  first verdict position (frac): median {statistics.median(vp):.3f}")
pm = per_model([r for r in a15 if r["first_verdict_frac"] != ""],
               lambda r: float(r["first_verdict_frac"]) <= 0.10)
res = cluster_boot(pm); report["A1_verdict_in_first_decile"] = res
say(f"  verdict inside the first 10% of the trace: {fmt(res)}")
cp = [float(r['first_construction_frac']) for r in a15 if r['first_construction_frac'] != '']
say(f"  first construction position (frac): median {statistics.median(cp):.3f}")

# early vs late verdict accuracy (open-ended, joined)
j = [r for r in oe if r["join_ok"] == "yes" and r["scored_math_validity"] and r["first_verdict_frac"] != ""]
early = [r for r in j if float(r["first_verdict_frac"]) <= 0.10]
late = [r for r in j if float(r["first_verdict_frac"]) > 0.10]
pmE = per_model(early, lambda r: r["scored_math_validity"] == "Correct")
pmL = per_model(late, lambda r: r["scored_math_validity"] == "Correct")
rE, rL = cluster_boot(pmE), cluster_boot(pmL)
obs, p, k = perm_paired(pmE, pmL)
say(f"  method validity | early verdict: {fmt(rE)}")
say(f"  method validity | late  verdict: {fmt(rL)}")
say(f"  paired difference (early - late): {100*obs:+.1f} pts, sign-flip p = {p:.3f} ({k} models)")
report["A1_early_vs_late_validity"] = (obs, p, k)
say(f"  verdict reversals per trace: mean {statistics.mean(float(r['verdict_reversals'] or 0) for r in a15):.2f}")
say()

# ---------------------------------------------------------------- A2
say("## A2 Considered-and-discarded (open-ended surfaces only)")
say(f"open-ended traces: {len(oe)}")
pm = per_model(oe, lambda r: r["w2_mentioned"] == "yes")
res = cluster_boot(pm); report["A2_w2_mentioned"] = res
say(f"  W2 machinery named in trace: {fmt(res)}")
ment = [r for r in oe if r["w2_mentioned"] == "yes"]
deliv = [r for r in ment if r["w2_delivered"] == "yes"]
disc = [r for r in ment if r["discarded"] == "yes"]
say(f"  of those: delivered in the response {len(deliv)}, DISCARDED {len(disc)}")
k, n = len(disc), len(ment)
lo, hi = wilson(k, n)
say(f"  discard rate among mentioners: {k}/{n} = {100*k/n:.1f}% Wilson [{100*lo:.1f}, {100*hi:.1f}]")
report["A2_discard_rate"] = (k, n, lo, hi)
pm = per_model(oe, lambda r: r["discarded"] == "yes")
res = cluster_boot(pm); report["A2_discard_share_all"] = res
say(f"  discard cases as a share of all open-ended traces: {fmt(res)}")
appl = [r for r in ment if r["w2_applied"] == "yes"]
say(f"  W2 named WITH an application cue nearby: {len(appl)}/{len(ment)}")
say(f"  applied-but-not-delivered: {sum(1 for r in appl if r['discarded']=='yes')}/{len(appl)}")
dsc = [r for r in oe if r["w2_mentioned"] == "no" and r["w2_descent_only"] == "yes"]
say(f"  descent-phrasing only (no W2 machinery named): {len(dsc)}/{len(oe)}")
say("  by surface:")
for s in sorted(OPEN_ENDED):
    ss = [r for r in oe if r["test_suite"] == s]
    m = [r for r in ss if r["w2_mentioned"] == "yes"]
    d = [r for r in m if r["discarded"] == "yes"]
    say(f"    {s:34s} mentioned {len(m):4d}/{len(ss):4d}  discarded {len(d):4d}")
say("  by arm (Test-01 only, the arm-bearing surface):")
t01 = [r for r in oe if r["test_suite"] == "test-01-kernel-tests"]
for a in sorted(set(r["arm"] for r in t01)):
    ss = [r for r in t01 if r["arm"] == a]
    m = [r for r in ss if r["w2_mentioned"] == "yes"]
    say(f"    {a:8s} mentioned {len(m):4d}/{len(ss):4d} = {100*len(m)/max(1,len(ss)):.1f}%")
# fruit vs main paired test on Test-01
pmF = per_model([r for r in t01 if r["arm"] == "fruit"], lambda r: r["w2_mentioned"] == "yes")
pmM = per_model([r for r in t01 if r["arm"] == "main"], lambda r: r["w2_mentioned"] == "yes")
obs, p, k = perm_paired(pmM, pmF)
say(f"  main - fruit W2-mention difference: {100*obs:+.1f} pts, sign-flip p = {p:.3f} ({k} models)")
report["A2_main_vs_fruit"] = (obs, p, k)
say()

# ---------------------------------------------------------------- A3
say("## A3 The one-line check (open-ended)")
pm = per_model(oe, lambda r: r["ran_check"] == "yes")
res = cluster_boot(pm); report["A3_ran_check_all"] = res
say(f"  ran an explicit LHS/RHS comparison: {fmt(res)}")
wt = [r for r in oe if r["join_ok"] == "yes" and
      r["scored_method_class"] in ("direct_measure", "polynomial", "path_order")]
pm = per_model(wt, lambda r: r["ran_check"] == "yes")
res = cluster_boot(pm); report["A3_ran_check_wholeterm"] = res
say(f"  among whole-term proposers (direct_measure/polynomial/path_order, n={len(wt)}): {fmt(res)}")
say(f"  post-check behavior (all who ran it): "
    f"{dict(collections.Counter(r['post_check_behavior'] for r in oe if r['ran_check']=='yes'))}")
say(f"  post-check behavior (whole-term proposers): "
    f"{dict(collections.Counter(r['post_check_behavior'] for r in wt if r['ran_check']=='yes'))}")
kept = [r for r in wt if r["ran_check"] == "yes" and r["post_check_behavior"] == "kept_method_anyway"]
say(f"  kept_method_anyway among whole-term proposers who ran the check: {len(kept)}")
say()

# ---------------------------------------------------------------- A4
say("## A4 Duplication noticing (+ SANS false-positive calibration)")
schemaA = [r for r in a15 if r["test_suite"] == "schema-test-A-tests"]
sans = [r for r in a15 if r["test_suite"] == "schema-test-A-new-system-tests"]
for label, ss in (("Schema A (duplicating)", schemaA), ("SANS (non-duplicating)", sans),
                  ("Test-01 KO7", [r for r in a15 if r["test_suite"] == "test-01-kernel-tests"])):
    pm = per_model(ss, lambda r: r["duplication_noticed"] == "yes")
    res = cluster_boot(pm)
    say(f"  {label:26s} {fmt(res)}")
    report[f"A4_{label.split()[0]}"] = res
pmA = per_model(schemaA, lambda r: r["duplication_noticed"] == "yes")
pmS = per_model(sans, lambda r: r["duplication_noticed"] == "yes")
obs, p, k = perm_paired(pmA, pmS)
say(f"  Schema A - SANS: {100*obs:+.1f} pts, sign-flip p = {p:.3f} ({k} models)  <- lexicon calibration")
report["A4_schemaA_vs_sans"] = (obs, p, k)
say(f"  consequence (Schema A): {dict(collections.Counter(r['duplication_consequence'] for r in schemaA if r['duplication_noticed']=='yes'))}")
say(f"  consequence (Test-01):  {dict(collections.Counter(r['duplication_consequence'] for r in a15 if r['test_suite']=='test-01-kernel-tests' and r['duplication_noticed']=='yes'))}")
say()

# ---------------------------------------------------------------- A5
say("## A5 In-trace method churn")
ch = [r for r in oe if r["n_method_families_tried"] != ""]
vals = [int(r["n_method_families_tried"]) for r in ch]
say(f"  families attempted per trace: mean {statistics.mean(vals):.2f} median {statistics.median(vals)} max {max(vals)}")
say(f"  distribution: {dict(sorted(collections.Counter(vals).items()))}")
pm = per_model(ch, lambda r: int(r["n_method_families_tried"]) >= 2)
res = cluster_boot(pm); report["A5_multi_family"] = res
say(f"  traces trying >= 2 families: {fmt(res)}")
pm = per_model(ch, lambda r: int(r["n_method_families_tried"]) >= 3)
say(f"  traces trying >= 3 families: {fmt(cluster_boot(pm))}")


def entropy(counter):
    n = sum(counter.values())
    return -sum((v / n) * math.log2(v / n) for v in counter.values() if v) if n else 0.0

ents = []
for m in sorted(set(r["model_family"] for r in ch)):
    seqs = [r["method_sequence"] for r in ch if r["model_family"] == m and r["method_sequence"]]
    c = collections.Counter(f for s in seqs for f in s.split(">"))
    ents.append(entropy(c))
say(f"  per-model in-trace method entropy: mean {statistics.mean(ents):.3f} bits "
    f"(range {min(ents):.2f}-{max(ents):.2f}); cross-rerun response-level reference = 1.154 bits")
report["A5_entropy_mean"] = statistics.mean(ents)
# churn vs correctness
jc = [r for r in ch if r["join_ok"] == "yes" and r["scored_math_validity"]]
hi_ = [r for r in jc if int(r["n_method_families_tried"]) >= 2]
lo_ = [r for r in jc if int(r["n_method_families_tried"]) <= 1]
pmH, pmLo = (per_model(hi_, lambda r: r["scored_math_validity"] == "Correct"),
             per_model(lo_, lambda r: r["scored_math_validity"] == "Correct"))
say(f"  method validity | churn>=2: {fmt(cluster_boot(pmH))}")
say(f"  method validity | churn<=1: {fmt(cluster_boot(pmLo))}")
obs, p, k = perm_paired(pmH, pmLo)
say(f"  paired difference: {100*obs:+.1f} pts, sign-flip p = {p:.3f} ({k} models)")
report["A5_churn_vs_validity"] = (obs, p, k)
say()

# ---------------------------------------------------------------- A6
say("## A6 Trace-to-response confidence divergence (turn-1 + single)")
dv = [r for r in new if r["turn"] != "2" and r["hedge_count_response"] != ""]
pm = per_model(dv, lambda r: r["divergence_flag"] == "yes")
res = cluster_boot(pm); report["A6_divergence"] = res
say(f"  traces with >=3 hedges whose response has none: {fmt(res)}")
ht = [int(r["hedge_count_trace"]) for r in dv]
hr = [int(r["hedge_count_response"]) for r in dv]
say(f"  mean hedges: trace {statistics.mean(ht):.2f} vs response {statistics.mean(hr):.2f}")
say(f"  median hedges: trace {statistics.median(ht)} vs response {statistics.median(hr)}")
# LENGTH-NORMALIZED (responses are ~1 kB, traces ~16 kB; raw counts are not comparable)
tl = [float(r["trace_chars"]) for r in dv]
rl = [float(r["response_chars"]) for r in dv if r["response_chars"]]
say(f"  mean length: trace {statistics.mean(tl):.0f} chars vs response {statistics.mean(rl):.0f} chars")
trt = [float(r["hedge_rate_trace_per_kchar"]) for r in dv]
rrt = [float(r["hedge_rate_response_per_kchar"]) for r in dv if r["hedge_rate_response_per_kchar"] != ""]
say(f"  hedge RATE per 1k chars: trace {statistics.mean(trt):.3f} vs response {statistics.mean(rrt):.3f}")
pm = per_model(dv, lambda r: r["rate_divergence_flag"] == "yes")
res = cluster_boot(pm); report["A6_rate_divergence"] = res
say(f"  rate-divergence (trace hedges present, response hedges ZERO): {fmt(res)}")
pm = per_model(dv, lambda r: r["hedge_rate_response_per_kchar"] != "" and
               float(r["hedge_rate_response_per_kchar"]) < float(r["hedge_rate_trace_per_kchar"]))
say(f"  response hedge RATE below trace hedge rate: {fmt(cluster_boot(pm))}")
pm = per_model(dv, lambda r: int(r["hedge_count_trace"]) > int(r["hedge_count_response"]))
say(f"  trace hedges > response hedges: {fmt(cluster_boot(pm))}")
# turn-2 self-audit note
t2 = [r for r in new if r["turn"] == "2" and r["hedge_count_response"] != ""]
if t2:
    pm = per_model(t2, lambda r: r["divergence_flag"] == "yes")
    say(f"  [self-audit turn-2, separate note] divergence {fmt(cluster_boot(pm))}, n={len(t2)}")
say()

# ---------------------------------------------------------------- old corpus
say("## Old corpus (submitted-era traces, process-only; no join to the deterministic scoring)")
say(f"  traces: {len(old)} across {len(set(r['model_family'] for r in old))} model families")
ooe = [r for r in old if r["test_suite"] in OPEN_ENDED]
say(f"  open-ended: {len(ooe)}; W2 named: {sum(1 for r in ooe if r['w2_mentioned']=='yes')}")
h = [r for r in old if r["verdict_lead"] != ""]
if h:
    say(f"  verdict-before-construction: {sum(1 for r in h if float(r['verdict_lead'])>0)}/{len(h)}")
say(f"  ran_check: {sum(1 for r in old if r['ran_check']=='yes')}/{len(old)}")
say()

json.dump({k: (list(v) if isinstance(v, tuple) else v) for k, v in report.items()},
          open(os.path.join(OUT, "stats_summary.json"), "w"), indent=1)
open(os.path.join(OUT, "stats_console.txt"), "w", encoding="utf-8").write("\n".join(L))
