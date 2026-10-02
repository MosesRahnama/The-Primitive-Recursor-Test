r"""Label-free trace features, fixed before any label was read. Reads data/corpus_recoded.jsonl, writes
data/corpus_features.csv. No label, answer key, or model identity is read here.
"""
import csv, io, json, os, re
from common import DATA

IN = os.path.join(DATA, "corpus_recoded.jsonl")
OUT = os.path.join(DATA, "corpus_features.csv")

HEDGE = re.compile(r"\b(maybe|perhaps|possibly|might|may be|i think|i believe|not sure|unsure|seems|appears|"
                   r"probably|likely|unclear|assume|assuming|suppose|guess|approximately|roughly|"
                   r"hmm|wait|actually|let me (re)?check|let me reconsider|hold on|double[- ]check)\b", re.I)
COMMIT = re.compile(r"\b(the answer is|therefore|thus|hence|so the|final answer|we conclude|conclusion|"
                    r"the result is|equals|= ?\\boxed|\\boxed|is correct|is true|is false|does not terminate|terminates)\b", re.I)
REFLECT = re.compile(r"\b(let me (re)?check|let me verify|double[- ]check|wait|actually|on second thought|"
                     r"i made a mistake|correction|re-?examine|reconsider|verify|sanity check|hmm)\b", re.I)
CONF = re.compile(r"\b(clearly|obviously|certainly|definitely|of course|trivially|straightforward|"
                  r"it is easy to see|evidently|undoubtedly|without doubt)\b", re.I)
TOK = re.compile(r"[a-z0-9]+")


def grams(text, n=4):
    t = TOK.findall(text.lower())
    return set(tuple(t[i:i + n]) for i in range(max(0, len(t) - n + 1)))


def per_k(pat, text):
    return 1000.0 * len(pat.findall(text)) / max(1, len(text))


def features(r):
    steps = [s for s in r["steps"] if s and s.strip()] or [""]
    body = " ".join(steps[:-1]); final = steps[-1]
    pg = grams(r["problem"])
    seen = set(pg); echo = []; nov = []; prev = None; streak = best = 0
    for s in steps:
        g = grams(s)
        if g:
            echo.append(len(g & pg) / len(g))
            nov.append(len(g - seen) / len(g))
        if prev is not None and (g or prev):
            j = len(g & prev) / max(1, len(g | prev))
            streak = streak + 1 if j > 0.5 else 0
            best = max(best, streak)
        seen |= g; prev = g
    lead = 1.0
    for i, s in enumerate(steps):
        if COMMIT.search(s):
            lead = i / len(steps); break
    return {
        "hedge_body": per_k(HEDGE, body) if body else 0.0,
        "hedge_final": per_k(HEDGE, final),
        "hedge_collapse": (per_k(HEDGE, body) if body else 0.0) - per_k(HEDGE, final),
        "echo_mass": sum(echo) / len(echo) if echo else 0.0,
        "novelty_rate": sum(nov) / len(nov) if nov else 0.0,
        "repeat_streak": best,
        "verdict_lead": lead,
        "reflection_count": sum(1 for s in steps if REFLECT.search(s)),
        "confidence_final": len(CONF.findall(final)),
        "n_steps": len(steps),
        "n_chars": sum(len(s) for s in steps),
    }


META = ["corpus", "split", "item_id", "generator", "domain", "provenance", "has_error", "first_error", "final_correct"]
FEAT = ["hedge_body", "hedge_final", "hedge_collapse", "echo_mass", "novelty_rate", "repeat_streak",
        "verdict_lead", "reflection_count", "confidence_final", "n_steps", "n_chars"]


def main():
    n = 0
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=META + FEAT, lineterminator="\n")
        w.writeheader()
        for line in io.open(IN, encoding="utf-8"):
            r = json.loads(line)
            row = {k: r.get(k) for k in META}
            row.update(features(r))
            w.writerow(row); n += 1
    print("wrote %d rows -> %s" % (n, OUT))


if __name__ == "__main__":
    main()
