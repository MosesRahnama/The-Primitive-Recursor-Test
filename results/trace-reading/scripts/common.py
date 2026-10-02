"""Shared paths and helpers. Every path is relative to the `results` folder that contains this analysis folder."""
import os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(HERE)                 # results/trace-reading
RESULTS = os.path.dirname(ANALYSIS)              # results
SCORED = os.path.join(RESULTS, "final_scored_data")
DATA = os.path.join(ANALYSIS, "data")
BATCHES = os.path.join(ANALYSIS, "batches")
EXTRACTION = os.path.join(ANALYSIS, "extraction")
ADJUDICATION = os.path.join(ANALYSIS, "adjudication", "adjudication.csv")
TABLES = os.path.join(ANALYSIS, "tables")
FIGURES = os.path.join(ANALYSIS, "figures")

EVENTS = ["E1_duplication_seen", "E2_wholeterm_fails", "E3_payload_inert", "E4_escape", "E4_payload_blind_import",
          "E5_import_denied", "E6_frame_following", "E7_retrieval", "E8_false_object_claim", "T2_license_separated"]
FIELDS = EVENTS + ["trace_status"]

ARM_OF = {"schema-test-A-tests": "schemaA", "schema-a-nonce-arm-tests": "nonce", "schema-test-A-new-system-tests": "control",
          "payload-scaling-tests": "payload", "test-01-kernel-tests": "test01", "schema-test-B-tests": "schemaB"}

def trace_path(rel):
    """A trace reference of the form <suite>/test-sessions/<slug>/<file>, resolved against the results folder."""
    return os.path.join(RESULTS, rel.replace("/", os.sep))

def norm(s):
    """Normalisation used for quote containment: line endings, unicode compatibility forms, curly quotes, whitespace runs."""
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[  -​  　]", " ", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s

def read_trace(rel):
    import io
    return norm(io.open(trace_path(rel), encoding="utf-8", errors="replace", newline="").read())

def fisher(a, b, c, d):
    """Two-sided Fisher exact test on [[a, b], [c, d]]."""
    from math import lgamma, exp
    def lch(n, k): return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
    r1, r2, c1 = a + b, c + d, a + c; n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c1 == n: return float("nan")
    def lp(x): return lch(r1, x) + lch(r2, c1 - x) - lch(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1); po = lp(a)
    return min(1.0, sum(exp(lp(x)) for x in range(lo, hi + 1) if lp(x) <= po + 1e-9))

def clopper_pearson(k, n, alpha=0.05):
    """Exact (Clopper-Pearson) binomial confidence interval for k successes in n trials, by bisection."""
    from math import lgamma, exp, log
    if n == 0: return (float("nan"), float("nan"))
    def cdf(p, j):  # P[X <= j] under Binomial(n, p)
        if p <= 0: return 1.0
        if p >= 1: return 0.0
        return sum(exp(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) + i * log(p) + (n - i) * log(1 - p)) for i in range(0, j + 1))
    def bisect(f, target, increasing):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if (f(mid) < target) == increasing: lo = mid
            else: hi = mid
        return (lo + hi) / 2
    low = 0.0 if k == 0 else bisect(lambda p: 1 - cdf(p, k - 1), alpha / 2, True)   # P[X >= k] rises with p
    high = 1.0 if k == n else bisect(lambda p: cdf(p, k), alpha / 2, False)         # P[X <= k] falls with p
    return (low, high)
