"""Merge reader outputs per study, check every quote for containment, apply third-read decisions.

Usage: python merge.py <study> single   primary analysis: one reader per item (reader-A files only)
       python merge.py <study>          both readers and the third read, where the study has them
       study in mrgsm8k, prm800k, prmbench, s6

Inputs : batches/read_<study>_bNN.jsonl (what the readers saw), extraction/read_<study>_bNN_A*.json and _B*.json,
         adjudication/adj_<study>_*.json (third-read decisions).
Outputs: data/merged_<study>.csv (single mode) or data/merged_<study>_two_readers.csv: one row per item with reader A
         and B values and quotes, containment flags, final value and its source (agree / A_only / B_only /
         adjudicated / open). Two-reader mode also writes data/disagreements_<study>.jsonl, the items with an open
         field, which build_adjudication_queues.py turns into third-read queues.
Rule: a quote that fails containment carries no value; the field is treated as unread by that reader. A governing
value that requires a quote (E1 yes, E8 yes, dropped yes, handling asked/declared/silent) with the required quote
empty is treated the same way, and the invalidation extends to the fields that depend on the governor (E1_step,
E8_step, E8_kind, step, confidence).
"""
import glob, io, os, re, csv, json, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import BATCHES, EXTRACTION, ADJ, DATA, read_jsonl, load_reader_json, contained, norm

STUDY = sys.argv[1]
# QUOTES: quote field -> (source text, governing field, required when the governor is "yes")
# DEPENDS: governing field -> fields that carry no value when the governor is invalid
if STUDY in ("mrgsm8k", "prm800k"):
    FIELDS = ["E1", "E1_step", "E8", "E8_step", "E8_kind"]
    QUOTES = {"E1_quote": ("steps", "E1", True), "E8_quote": ("steps", "E8", True), "E8_given_quote": ("question", "E8", False)}
    DEPENDS = {"E1": ["E1_step"], "E8": ["E8_step", "E8_kind"]}
elif STUDY == "prmbench":
    FIELDS = ["dropped", "step", "confidence"]
    QUOTES = {"condition_quote": ("question", "dropped", True), "step_quote": ("steps", "dropped", True)}
    DEPENDS = {"dropped": ["step", "confidence"]}
elif STUDY == "s6":
    FIELDS = ["sql_given", "any_question"]; QUOTES = {}; DEPENDS = {}
else:
    raise SystemExit("unknown study")

# step fields bound to a governor whose quote locates the step
STEP_OF = {"E1_step": "E1", "E8_step": "E8"} if STUDY in ("mrgsm8k", "prm800k") else ({"step": "dropped"} if STUDY == "prmbench" else {})

def step_of_quote(q, item):
    """1-based index of the first step containing the quote after normalisation; 0 when none does."""
    for i, s in enumerate(item.get("steps", [])):
        if contained(q, s): return i + 1
    return 0

def text_of(item, which):
    if which == "steps": return "\n".join(item.get("steps", []))
    if which == "response": return item.get("response", "")
    return item.get("question", "")

def flatten(d, item):
    """Return field dict for one reader; for s6 expand per_ambiguity into handling_i / quote_i."""
    out = {}
    for k in FIELDS + list(QUOTES): out[k] = "" if d.get(k) is None else str(d.get(k)).strip()
    if STUDY == "s6":
        pa = d.get("per_ambiguity") or []
        for i, amb in enumerate(item.get("ambiguities", [])):
            e = pa[i] if i < len(pa) and isinstance(pa[i], dict) else {}
            out["handling_%d" % i] = str(e.get("handling", "") or "").strip()
            out["quote_%d" % i] = str(e.get("quote", "") or "").strip()
    return out

def main():
    items = {}
    for p in sorted(glob.glob(os.path.join(BATCHES, "read_%s_b*.jsonl" % STUDY))):
        b = re.search(r"(b\d+)\.jsonl$", p).group(1)
        for it in read_jsonl(p): items[it["id"]] = (b, it)
    A, B = {}, {}
    # either reader may write a batch in two parts (_A1/_A2, _B1/_B2) to stay under the output cap; all parts are merged.
    # PRMBench also has the twin-completion batches read_prmbench_pair_bNN, whose items also appear in the
    # read_prmbench_bNN batch files; only their reader outputs are added here.
    pats = {"A": ["read_%s_b*_A*.json" % STUDY], "B": ["read_%s_b*_B*.json" % STUDY]}
    if STUDY == "prmbench":
        pats["A"].append("read_prmbench_pair_b*_A*.json"); pats["B"].append("read_prmbench_pair_b*_B*.json")
    # single mode: only the reader-A files are read; second reads (_B) and third reads (adjudication/) are ignored
    single = len(sys.argv) > 2 and sys.argv[2] == "single"
    if single: pats["B"] = []
    for tag, target in (("A", A), ("B", B)):
        for pat in pats[tag]:
            for p in glob.glob(os.path.join(EXTRACTION, pat)):
                try: target.update(load_reader_json(p))
                except Exception as e: print("LOAD FAIL", p, e)
    adj = {}
    for p in ([] if single else glob.glob(os.path.join(ADJ, "adj_%s_*.json" % STUDY))):
        try: adj.update(load_reader_json(p))
        except Exception as e: print("LOAD FAIL", p, e)
    rows, open_items, src_count, voided, adj_bad = [], [], Counter(), Counter(), Counter()
    def adj_ok(iid, k, it):
        """An adjudicated yes on a governor needs its required quote contained in the item text; otherwise the decision is dropped and the field stays open."""
        a = adj[iid]
        if k not in DEPENDS or str(a.get(k, "")).strip() != "yes": return True
        for q, (which, gov, req) in QUOTES.items():
            if gov != k or not req: continue
            qv = str(a.get(q, "") or "").strip()
            if not qv or not contained(qv, text_of(it, which)):
                adj_bad[(k, "missing quote" if not qv else "quote not contained")] += 1
                return False
        return True
    for iid, (b, it) in items.items():
        a, bb = A.get(iid, {}), B.get(iid, {})
        fa, fb = flatten(a, it), flatten(bb, it)
        row = {"id": iid, "batch": b, "in_A": "yes" if a else "no", "in_B": "yes" if bb else "no"}
        fields = list(fa.keys())
        # containment
        cont = {}
        for tag, f in (("A", fa), ("B", fb)):
            for q, (which, gov, req) in QUOTES.items():
                cont[(tag, q)] = "" if not f[q] else ("ok" if contained(f[q], text_of(it, which)) else "FAIL")
            if STUDY == "s6":
                for k in fields:
                    if k.startswith("quote_"): cont[(tag, k)] = "" if not f[k] else ("ok" if contained(f[k], it.get("response", "")) else "FAIL")
        # a governor is invalid for a reader when it is "yes" (or a quoted s6 handling) and a required quote is
        # missing or fails containment; the governor, its quotes and its dependents are then unread for that reader
        def governor_invalid(tag, f, gov):
            if gov in DEPENDS:
                if f[gov] != "yes": return False
                for q, (which, g, req) in QUOTES.items():
                    if g != gov: continue
                    if cont.get((tag, q)) == "FAIL": return True
                    if req and not f[q]: return True
                return False
            if STUDY == "s6" and gov.startswith("handling_"):
                if f[gov] not in ("asked", "declared", "silent"): return False
                c = cont.get((tag, "quote_" + gov.split("_")[1]), "")
                return c == "FAIL" or (c == "" and not f["quote_" + gov.split("_")[1]])
            return False
        def invalid(tag, f, k):
            for gov, deps in DEPENDS.items():
                if k == gov or k in deps or any(k == q and g == gov for q, (w, g, r) in QUOTES.items()):
                    if governor_invalid(tag, f, gov): return True
            if STUDY == "s6" and (k.startswith("handling_") or k.startswith("quote_")):
                return governor_invalid(tag, f, "handling_" + k.split("_")[1])
            return False
        n_open = 0
        for k in fields:
            va, vb = fa[k], fb[k]
            row[k + "_A"], row[k + "_B"] = va, vb
            if va and invalid("A", fa, k): va = ""; voided[(k, "A")] += 1
            if vb and invalid("B", fb, k): vb = ""; voided[(k, "B")] += 1
            key = k
            if iid in adj and adj[iid].get(k) not in (None, "") and adj_ok(iid, k, it):
                final, src = str(adj[iid][k]).strip(), "adjudicated"
            elif k in STEP_OF and iid in adj and str(adj[iid].get(STEP_OF[k], "")).strip() == "yes" and adj[iid].get(STEP_OF[k] + "_quote"):
                # the third reader decided the governor with its own quote: the step is the first step containing that quote
                s = step_of_quote(str(adj[iid][STEP_OF[k] + "_quote"]), it)
                if s: final, src = str(s), "adjudicated"
                elif va == vb and va != "": final, src = va, "agree"
                elif va and not vb: final, src = va, "A_only"
                elif vb and not va: final, src = vb, "B_only"
                else: final, src = "", "none"
            elif va == vb and va != "": final, src = va, "agree"
            elif va and not vb: final, src = va, "A_only"
            elif vb and not va: final, src = vb, "B_only"
            elif not va and not vb: final, src = "", "none"
            else:
                final, src = "", "open"
                # only coded fields go to the third read; quote spans that differ while both readers agree are not open
                if k in FIELDS or (STUDY == "s6" and k.startswith("handling_")): n_open += 1
            row[k], row[k + "_src"] = final, src; src_count[(k, src)] += 1
        for (tag, q), c in cont.items(): row["%s_%s_contain" % (q, tag)] = c
        row["n_open"] = n_open
        rows.append(row)
        if n_open:
            open_items.append({"id": iid, "batch": b, "item": it, "A": fa, "B": fb,
                               "open_fields": [k for k in fields if row[k + "_src"] == "open" and (k in FIELDS or (STUDY == "s6" and k.startswith("handling_")))]})
    cols = []
    for r in rows:
        for k in r:
            if k not in cols: cols.append(k)
    with io.open(os.path.join(DATA, ("merged_%s.csv" if single else "merged_%s_two_readers.csv") % STUDY), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    if not single:
        with io.open(os.path.join(DATA, "disagreements_%s.jsonl" % STUDY), "w", encoding="utf-8") as f:
            for o in open_items: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    nA, nB = sum(r["in_A"] == "yes" for r in rows), sum(r["in_B"] == "yes" for r in rows)
    print("%s: items %d, read by A %d, by B %d, items with open fields %d" % (STUDY, len(rows), nA, nB, len(open_items)))
    fails = Counter(k for r in rows for k, v in r.items() if k.endswith("_contain") and v == "FAIL")
    print("  containment failures:", dict(fails))
    print("  reader values set aside by the validator (missing or failed required quote):", dict(voided))
    print("  adjudicated items %d; adjudicated yes decisions dropped for a missing or uncontained quote: %s" % (len(adj), dict(adj_bad)))
    basis = Counter(str(a.get("basis", "")).strip() for a in adj.values())
    print("  third-read basis:", dict(basis))
    for k in FIELDS + ([f for f in rows[0] if f.startswith("handling_") and not f.endswith(("_A", "_B", "_src"))] if rows and STUDY == "s6" else []):
        print("  %-12s" % k, {s: src_count[(k, s)] for s in ("agree", "A_only", "B_only", "adjudicated", "open", "none") if src_count[(k, s)]})

if __name__ == "__main__":
    main()
