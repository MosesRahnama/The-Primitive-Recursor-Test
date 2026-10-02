r"""Omega, echo, and distinction-boundary measurements at the release boundary.

Inputs: data\trace_flow_sessions.json (72 fresh), data\trace_flow_core.json (339 core),
the raw thinking traces (recency test), ..\external-benchmarks\data\corpus_features.csv (rebuilt by external-benchmarks\scripts\transport_features.py),
results\payload-scaling-tests\pilot-coding\K_SERIES.csv. Writes data\omega_boundary.json and prints the tables
listed in the README.
"""
import csv, io, os, json, math, random, statistics
from collections import Counter, defaultdict
from trace_flow import FAM, h

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.normpath(os.path.join(HERE, "..", "data"))
R = os.path.normpath(os.path.join(HERE, "..", ".."))  # the benchmark results folder
fresh = json.load(io.open(os.path.join(S, "trace_flow_sessions.json"), encoding="utf-8"))
core = json.load(io.open(os.path.join(S, "trace_flow_core.json"), encoding="utf-8"))
random.seed(7)
OUT = {}

# ---- license maps: which released family carries a licensed (exogenous) channel on which system ----
# duplicating systems (Schema A, Test 01 kernel): direct whole-term measures are refuted
# (grammar-closure barrier); path orders and polynomials are W1 imports; DP is the W2 role channel.
# factorial S1 (fac, armC, armC2): every simplification-order and monotone-Nat family is refuted; DP only.
# nonduplicating control (SANS) and payload k-arms: a direct order is certified, so direct measure,
# path order, polynomial are all licensed.
CORE_CLASS_TO_FAM = {"direct_measure": "semantic", "structural_descent": "semantic", "structural_induction": "semantic",
                     "polynomial": "polynomial", "path_order": "path_order", "transformed_calls": "dependency_pairs", "": "none"}
LIC_CORE = {"schema_a": {"polynomial", "path_order", "transformed_calls"},
            "test01": {"polynomial", "path_order", "transformed_calls"},
            "sans": {"direct_measure", "polynomial", "path_order", "transformed_calls"}}
LIC_FRESH_S1 = {"dependency_pairs"}
LIC_FRESH_CTRL = {"dependency_pairs", "path_order", "polynomial"}


def omega_row(n_trace, licensed):
    """Hartley envelope emitted by the trace minus licensed gain (1 bit if the release is a licensed class)."""
    env = h(max(1, n_trace))
    gain = 1.0 if licensed else 0.0
    return env, gain, env - gain


print("=== A. Omega at the release boundary ===")
print("  %-24s %4s %8s %8s %10s %12s %14s" % ("group", "n", "H0>=1", "licensed", "Omega>0", "valid|Om>0", "valid|Om<=0"))
A = {}
for name, rows, lic in [("core sans", [x for x in core if x["suite"] == "sans"], LIC_CORE["sans"]),
                        ("core schema_a", [x for x in core if x["suite"] == "schema_a"], LIC_CORE["schema_a"]),
                        ("core test01", [x for x in core if x["suite"] == "test01"], LIC_CORE["test01"])]:
    ev = 0; lic_n = 0; om_pos = []; om_non = []
    for x in rows:
        licensed = x["method_class"] in lic
        env, gain, om = omega_row(x["n_trace"], licensed)
        ev += env >= 1; lic_n += licensed
        (om_pos if om > 0 else om_non).append(x["valid"])
    A[name] = dict(n=len(rows), branched=ev, licensed=lic_n, omega_pos=len(om_pos),
                   valid_given_pos=sum(om_pos) / max(1, len(om_pos)), valid_given_nonpos=sum(om_non) / max(1, len(om_non)))
    print("  %-24s %4d %8d %8d %10d %11.0f%% %13.0f%%" % (name, len(rows), ev, lic_n, len(om_pos), 100 * A[name]["valid_given_pos"], 100 * A[name]["valid_given_nonpos"]))
for name, rows, lic in [("fresh S1 (fac,C,C2)", [x for x in fresh if x["S1"]], LIC_FRESH_S1),
                        ("fresh controls+k", [x for x in fresh if not x["S1"]], LIC_FRESH_CTRL)]:
    ev = 0; lic_n = 0; om_pos = []; om_non = []
    for x in rows:
        licensed = x["released"] in lic
        env, gain, om = omega_row(x["n_trace"], licensed)
        ev += env >= 1; lic_n += licensed
        (om_pos if om > 0 else om_non).append(x["false_witness"] == "yes")
    A[name] = dict(n=len(rows), branched=ev, licensed=lic_n, omega_pos=len(om_pos),
                   false_witness_given_pos=sum(om_pos) / max(1, len(om_pos)), false_witness_given_nonpos=sum(om_non) / max(1, len(om_non)))
    print("  %-24s %4d %8d %8d %10d   fw|Om>0 %.0f%%  fw|Om<=0 %.0f%%" % (name, len(rows), ev, lic_n, len(om_pos), 100 * A[name]["false_witness_given_pos"], 100 * A[name]["false_witness_given_nonpos"]))
OUT["A_omega"] = A

# paired per-model boundary-event rate, SANS vs Schema A (matched pair)
print("\n  paired per model (boundary event = Omega_release > 0):")
per = defaultdict(lambda: defaultdict(list))
for x in core:
    if x["suite"] in ("sans", "schema_a"):
        env, gain, om = omega_row(x["n_trace"], x["method_class"] in LIC_CORE[x["suite"]])
        per[x["model"]][x["suite"]].append(om > 0)
diffs = []
for m, d in sorted(per.items()):
    if d["sans"] and d["schema_a"]:
        a = statistics.mean(d["sans"]); b = statistics.mean(d["schema_a"]); diffs.append(b - a)
        print("    %-22s sans %.0f%% (n=%d)  schemaA %.0f%% (n=%d)  diff %+.0f pp" % (m, 100 * a, len(d["sans"]), 100 * b, len(d["schema_a"]), 100 * (b - a)))
print("    mean paired difference %+.1f pp over %d models, positive in %d" % (100 * statistics.mean(diffs), len(diffs), sum(1 for v in diffs if v > 0)))
OUT["A_paired"] = dict(mean_diff_pp=100 * statistics.mean(diffs), n_models=len(diffs), positive=sum(1 for v in diffs if v > 0))

# ---- B. Diagonal emission (case II) versus role channel (case III), core corpus ----
print("\n=== B. Trilemma partition of the release on the duplicating systems ===")
B = {}
for s in ("schema_a", "test01", "sans"):
    rows = [x for x in core if x["suite"] == s]
    c = Counter()
    for x in rows:
        mc = x["method_class"]
        if x["n_answer"] > 1 and mc in ("", "structural_descent", "structural_induction"): c["I unresolved branch"] += 1
        elif mc == "direct_measure": c["II direct measure (value channel)"] += 1
        elif mc in ("polynomial", "path_order"): c["W1 import"] += 1
        elif mc == "transformed_calls": c["III DP role channel"] += 1
        else: c["semantic story / none"] += 1
    v = {k: sum(x["valid"] for x in rows if (
        (k == "II direct measure (value channel)" and x["method_class"] == "direct_measure") or
        (k == "W1 import" and x["method_class"] in ("polynomial", "path_order")) or
        (k == "III DP role channel" and x["method_class"] == "transformed_calls"))) for k in c}
    B[s] = dict(counts=dict(c), valid=v)
    print("  %-9s n=%3d  %s" % (s, len(rows), "; ".join("%s %d (valid %d)" % (k, c[k], v.get(k, 0)) for k in c)))
OUT["B_trilemma"] = B

# ---- C. Recency echo: which trace family is released? ----
print("\n=== C. Which family the release echoes (core, traces naming >= 2 families) ===")
B_ROOT = os.path.join(R, "final_scored_data")
SUITES = {"schema_a": "schema-test-A-tests", "sans": "schema-test-A-new-system-tests", "test01": "test-01-kernel-tests"}
rec = Counter(); n_rec = 0; chance = []
for x in core:
    if x["n_trace"] < 2: continue
    d = os.path.join(R, SUITES[x["suite"]], "test-sessions", x["slug"])
    tp = next((p for p in (os.path.join(d, "thinking.txt"), os.path.join(d, "thinking_1.txt")) if os.path.isfile(p)), None)
    if not tp: continue
    t = io.open(tp, encoding="utf-8", errors="replace").read()
    rel = CORE_CLASS_TO_FAM.get(x["method_class"], "none")
    if rel not in x["trace_fams"]: rec["released family absent from trace"] += 1; continue
    last = {k: max(m.start() for m in FAM[k].finditer(t)) for k in x["trace_fams"]}
    first = {k: min(m.start() for m in FAM[k].finditer(t)) for k in x["trace_fams"]}
    cnt = {k: len(FAM[k].findall(t)) for k in x["trace_fams"]}
    n_rec += 1; chance.append(1 / x["n_trace"])
    rec["released = last-mentioned"] += rel == max(last, key=last.get)
    rec["released = first-mentioned"] += rel == min(first, key=first.get)
    rec["released = most-mentioned"] += rel == max(cnt, key=cnt.get)
print("  n=%d; chance %.0f%%; last-mentioned %.0f%%; first-mentioned %.0f%%; most-mentioned %.0f%%; released family absent from trace %d" % (
    n_rec, 100 * statistics.mean(chance), 100 * rec["released = last-mentioned"] / n_rec, 100 * rec["released = first-mentioned"] / n_rec,
    100 * rec["released = most-mentioned"] / n_rec, rec["released family absent from trace"]))
OUT["C_recency"] = dict(n=n_rec, chance=statistics.mean(chance), **{k: v / n_rec for k, v in rec.items() if k.startswith("released =")}, absent=rec["released family absent from trace"])

# ---- D. Mutual information across the boundary, with a permutation null ----
def mi_bits(xs, ys):
    n = len(xs); pxy = Counter(zip(xs, ys)); px = Counter(xs); py = Counter(ys)
    return sum(c / n * math.log2((c / n) / ((px[a] / n) * (py[b] / n))) for (a, b), c in pxy.items())


def binned(vals, k=4):
    qs = sorted(vals); cuts = [qs[int(len(qs) * i / k)] for i in range(1, k)]
    return [sum(v > c for c in cuts) for v in vals]


def mi_with_null(feature, label, perms=2000, k=4):
    xs = binned(feature, k) if len(set(feature)) > k else list(feature)
    obs = mi_bits(xs, label); lab = list(label); nulls = []
    for _ in range(perms):
        random.shuffle(lab); nulls.append(mi_bits(xs, lab))
    nulls.sort()
    return obs, nulls[int(0.95 * perms)], statistics.mean(nulls)


def H(label):
    n = len(label); return -sum(c / n * math.log2(c / n) for c in Counter(label).values())


print("\n=== D. Bits about validity across the boundary (core 339, quartile bins, 2000-permutation null) ===")
lab = [int(x["valid"]) for x in core]
print("  H(valid) = %.3f bits" % H(lab))
D = {"H_valid": H(lab)}
for side, feats in (("answer side", ["hedge_answer", "n_answer", "answer_chars", "dp_in_answer"]),
                    ("trace side", ["hedge_trace", "n_trace", "trace_chars", "n_refute", "dp_in_trace"])):
    for f in feats:
        vals = [float(x[f]) if x[f] is not None else 0.0 for x in core]
        obs, p95, mean0 = mi_with_null(vals, lab)
        D[f] = dict(mi=obs, null95=p95, null_mean=mean0, side=side)
        print("  %-11s %-13s I = %.4f bits  (null 95th %.4f, null mean %.4f) %s" % (side, f, obs, p95, mean0, "ABOVE NULL" if obs > p95 else ""))
# joint answer side vs joint trace side
def joint(fs):
    cols = [binned([float(x[f]) if x[f] is not None else 0.0 for x in core], 3) for f in fs]
    return [tuple(c[i] for c in cols) for i in range(len(core))]
for side, fs in (("answer side joint", ["hedge_answer", "n_answer", "answer_chars"]), ("trace side joint", ["hedge_trace", "n_trace", "n_refute"])):
    xs = joint(fs); obs = mi_bits(xs, lab); labc = lab[:]; nulls = []
    for _ in range(2000): random.shuffle(labc); nulls.append(mi_bits(xs, labc))
    nulls.sort(); D[side] = dict(mi=obs, null95=nulls[1900], null_mean=statistics.mean(nulls))
    print("  %-28s I = %.4f bits (null 95th %.4f, null mean %.4f)" % (side, obs, nulls[1900], statistics.mean(nulls)))
OUT["D_mi_core"] = D

print("\n=== E. Bits about has_error on the external corpora (deciles, 500-permutation null) ===")
rows = list(csv.DictReader(io.open(os.path.join(R, "external-benchmarks", "data", "corpus_features.csv"), encoding="utf-8", newline="")))
E = {}
for corpus in ("processbench", "bbm", "mrgsm8k", "retraceqa", "deltabench"):
    rr = [r for r in rows if r["corpus"] == corpus and r["has_error"] in ("True", "False")]
    lab = [int(r["has_error"] == "True") for r in rr]
    E[corpus] = {"n": len(rr), "H": H(lab)}
    line = []
    for f in ("hedge_final", "confidence_final", "hedge_body", "echo_mass", "novelty_rate", "n_chars"):
        vals = [float(r[f]) for r in rr]
        obs, p95, m0 = mi_with_null(vals, lab, perms=500, k=10)
        E[corpus][f] = dict(mi=obs, null95=p95); line.append("%s %.4f%s" % (f, obs, "*" if obs > p95 else ""))
    print("  %-12s n=%5d H=%.3f  %s" % (corpus, len(rr), H(lab), "  ".join(line)))
OUT["E_mi_corpora"] = E

# ---- F. r-ary role exchange against the payload k-series ----
print("\n=== F. r-ary role exchange (Theorem finite-role-exchange) against the payload k-series, 7-model panel ===")
ks = [r for r in csv.DictReader(io.open(os.path.join(R, "payload-scaling-tests", "pilot-coding", "K_SERIES.csv"), encoding="utf-8", newline="")) if r["panel"] == "7-model"]
F = []
for r in ks:
    k = int(r["k"]); n = int(r["n"]); rd = int(r["valid_rule_derived"]); vp = int(r["valid_proof"])
    if k >= 1:
        idp = math.log2(k + 1) - k / (k + 1) * math.log2(k) if k > 1 else 1.0
        resid = k / (k + 1) * math.log2(k) if k > 1 else 0.0
    else:
        idp = resid = 0.0
    F.append(dict(k=k, n=n, rule_derived=rd, valid=vp, I_DP_bits=idp, frame_residual_bits=resid))
    print("  k=%d  n=%2d  DP released %2d (%.0f%%)  valid %2d (%.0f%%)  I_DP = %.3f bits  frame residual = %.3f bits" % (k, n, rd, 100 * rd / n, vp, 100 * vp / n, idp, resid))
OUT["F_rary"] = F

json.dump(OUT, io.open(os.path.join(S, "omega_boundary.json"), "w", encoding="utf-8"), indent=1)
print("\nwrote omega_boundary.json")
