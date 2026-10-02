"""Merge the derived keys into the reader batches for studies 1 and 3.

Reads extraction/key_<corpus>_bNN.json, checks both key quotes for containment (problem_quote in question,
gold_quote in gold solution), writes data/keys_<corpus>.csv (every key with its containment status) and
batches/read_<corpus>_bNN.jsonl (id, question, steps, decisive_condition, problem_quote). An item whose key
failed containment still goes to the readers with the condition text; its status is recorded for the analysis.
"""
import glob, io, os, re, csv, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, BATCHES, EXTRACTION, read_jsonl, write_jsonl, load_reader_json, contained

SIZE = {"mrgsm8k": 60, "prm800k": 25}
for corpus in ("mrgsm8k", "prm800k"):
    items = {r["id"]: r for r in read_jsonl(os.path.join(DATA, "reader_%s.jsonl" % corpus))}
    keyin = {r["id"]: r for r in read_jsonl(os.path.join(DATA, "keyinput_%s.jsonl" % corpus))}
    keys = {}
    for p in sorted(glob.glob(os.path.join(EXTRACTION, "key_%s_b*.json" % corpus))):
        try: keys.update(load_reader_json(p))
        except Exception as e: print("LOAD FAIL", p, e)
    rows = []
    for iid, it in items.items():
        k = keys.get(iid, {})
        pq, gq = str(k.get("problem_quote", "") or ""), str(k.get("gold_quote", "") or "")
        rows.append({"id": iid, "has_key": "yes" if k else "no", "decisive_condition": str(k.get("decisive_condition", "") or ""),
                     "condition_type": str(k.get("condition_type", "") or ""), "problem_quote": pq,
                     "problem_quote_contained": "ok" if contained(pq, it["question"]) else ("FAIL" if pq else ""),
                     "gold_quote": gq, "gold_quote_contained": "ok" if contained(gq, keyin[iid]["gold_solution"]) else ("FAIL" if gq else "")})
    with io.open(os.path.join(DATA, "keys_%s.csv" % corpus), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    missing = [r["id"] for r in rows if r["has_key"] == "no"]
    print(corpus, "items", len(rows), "keys", len(keys), "missing", len(missing), "problem_quote FAIL", sum(r["problem_quote_contained"] == "FAIL" for r in rows),
          "gold_quote FAIL", sum(r["gold_quote_contained"] == "FAIL" for r in rows))
    if missing: print("  missing ids (first 10):", missing[:10])
    ordered = list(items.values())
    n = 0
    for i in range(0, len(ordered), SIZE[corpus]):
        n += 1
        out = []
        for it in ordered[i:i + SIZE[corpus]]:
            k = keys.get(it["id"], {})
            out.append({"id": it["id"], "question": it["question"], "steps": it["steps"],
                        "decisive_condition": str(k.get("decisive_condition", "") or ""), "problem_quote": str(k.get("problem_quote", "") or "")})
        write_jsonl(os.path.join(BATCHES, "read_%s_b%02d.jsonl" % (corpus, n)), out)
    print("  reader batches", n)
