"""Shared paths and helpers. Paths are relative to the package root, the parent of scripts/."""
import os, re, io, json, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.dirname(HERE)                                   # the package root
# the external datasets (sources.csv): set EXTERNAL_CORPORA to their folder, or place them under corpora/ in the package root
CORPORA = os.environ.get("EXTERNAL_CORPORA") or os.path.join(EXT, "corpora")
# the BIRD-Interact sessions collected for study 6
ARM = os.path.join(EXT, "bird-interact-sessions")
DATA = os.path.join(EXT, "data")
BATCHES = os.path.join(EXT, "batches")
EXTRACTION = os.path.join(EXT, "extraction")
ADJ = os.path.join(EXT, "adjudication")
TABLES = os.path.join(EXT, "tables")
for d in (DATA, BATCHES, EXTRACTION, ADJ, TABLES):
    os.makedirs(d, exist_ok=True)

def norm(s):
    """Normalisation used for quote containment: line endings, unicode compatibility forms, curly quotes, whitespace runs."""
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def contained(quote, text):
    q = norm(quote)
    return bool(q) and q in norm(text)

def read_jsonl(path):
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def write_jsonl(path, rows):
    with io.open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def load_reader_json(path):
    """Reader output: a JSON array (or a dict with 'items') of objects keyed by 'id'."""
    data = json.load(io.open(path, encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("results") or data.get("traces") or list(data.values())
    return {str(d.get("id")).strip(): d for d in data if isinstance(d, dict)}

def fisher(a, b, c, d):
    """Two-sided Fisher test on [[a, b], [c, d]]."""
    from math import lgamma, exp
    def lch(n, k): return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
    r1, r2, c1 = a + b, c + d, a + c; n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c1 == n: return float("nan")
    def lp(x): return lch(r1, x) + lch(r2, c1 - x) - lch(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1); po = lp(a)
    return min(1.0, sum(exp(lp(x)) for x in range(lo, hi + 1) if lp(x) <= po + 1e-9))

def clopper_pearson(k, n, alpha=0.05):
    from math import lgamma, exp, log
    if n == 0: return (float("nan"), float("nan"))
    def cdf(p, j):
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
    low = 0.0 if k == 0 else bisect(lambda p: 1 - cdf(p, k - 1), alpha / 2, True)
    high = 1.0 if k == n else bisect(lambda p: cdf(p, k), alpha / 2, False)
    return (low, high)

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return ((c - h) / d, (c + h) / d)

def pct(k, n): return "%d/%d = %.1f%%" % (k, n, 100.0 * k / n) if n else "0/0"

def mutual_information_bits(xs, ys):
    """I(X;Y) in bits for two discrete sequences."""
    from math import log2
    from collections import Counter
    n = len(xs); cx, cy, cxy = Counter(xs), Counter(ys), Counter(zip(xs, ys))
    return sum(c / n * log2((c / n) / ((cx[x] / n) * (cy[y] / n))) for (x, y), c in cxy.items())

def entropy_bits(ys):
    from math import log2
    from collections import Counter
    n = len(ys); return -sum(c / n * log2(c / n) for c in Counter(ys).values())

def permutation_null(xs, ys, draws=2000, seed=20260904):
    import random
    rng = random.Random(seed); ys = list(ys); vals = []
    for _ in range(draws):
        rng.shuffle(ys); vals.append(mutual_information_bits(xs, ys))
    vals.sort(); return vals[int(0.95 * len(vals))]
