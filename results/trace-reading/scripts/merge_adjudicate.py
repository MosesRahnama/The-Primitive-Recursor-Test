"""Merge the two readers' outputs per batch, check every quote for containment, apply the adjudications.

Inputs: extraction/<batch>_A.json and _B.json (one JSON array per reader), adjudication/adjudication.csv.
Outputs: data/extraction_merged.csv (A and B side by side, final value, source of the final value, quote position),
         data/open_items.md (fields still disagreeing or with a quote not contained; empty when the arms are closed).

Final value per field: the adjudicated value when one exists, else the agreed value, else the single reader's value.
A quote that is not contained in its trace after normalisation is a defect and is listed, never silently accepted.
"""
import csv, glob, io, json, os, re
from collections import Counter, defaultdict
from common import ANALYSIS, DATA, EXTRACTION, ADJUDICATION, FIELDS, norm, read_trace

QUOTED = [f for f in FIELDS if f != "trace_status"]
SHORT = {"E1_duplication_seen": "E1", "E2_wholeterm_fails": "E2", "E3_payload_inert": "E3", "E4_escape": "E4",
         "E4_payload_blind_import": "E4_payload_blind_import", "E5_import_denied": "E5", "E6_frame_following": "E6",
         "E7_retrieval": "E7", "E8_false_object_claim": "E8", "T2_license_separated": "T2"}

def load(path):
    try:
        data = json.load(io.open(path, encoding="utf-8-sig"))
    except Exception as e:
        print("LOAD FAIL", path, e); return {}
    if isinstance(data, dict):
        data = data.get("traces") or data.get("results") or list(data.values())
    return {(d.get("file") or "").strip().replace("\\", "/").lower(): d for d in data}

def val(d, k):
    v = d.get(k, "")
    if (v is None or v == "") and k.endswith("_quote"):
        base = k[:-6]; v = d.get(SHORT.get(base, base) + "_quote", "")
    return "" if v is None else str(v).strip()

def main():
    batches = sorted(set(re.sub(r"_[AB]\.json$", "", os.path.basename(p)) for p in glob.glob(os.path.join(EXTRACTION, "*_[AB].json"))))
    adj = defaultdict(dict)
    if os.path.exists(ADJUDICATION):
        for r in csv.DictReader(io.open(ADJUDICATION, encoding="utf-8-sig", newline="")):
            adj[r["file"].strip().replace("\\", "/").lower()][r["field"]] = (r["value"].strip(), r.get("quote", ""), r.get("adjudicator_note", ""))
    rows, queue, texts = [], [], {}
    for b in batches:
        A = load(os.path.join(EXTRACTION, b + "_A.json")); B = load(os.path.join(EXTRACTION, b + "_B.json"))
        for f in sorted(set(A) | set(B)):
            a, bb = A.get(f, {}), B.get(f, {})
            ref = (a.get("file") or bb.get("file") or f).replace("\\", "/")
            if ref not in texts:
                try: texts[ref] = read_trace(ref)
                except Exception as e:
                    texts[ref] = ""; queue.append((b, ref, "FILE", "unreadable: %s" % e))
            text = texts[ref]
            slug = ref.split("/")[-2] if "/" in ref else ref
            row = {"batch": b, "file": ref, "session_slug": slug, "in_A": "yes" if a else "no", "in_B": "yes" if bb else "no", "trace_chars": len(text)}
            n_dis = 0
            for k in FIELDS:
                va, vb = val(a, k), val(bb, k)
                qa, qb = val(a, k + "_quote"), val(bb, k + "_quote")
                ca = "" if not qa else ("ok" if norm(qa) in text else "FAIL")
                cb = "" if not qb else ("ok" if norm(qb) in text else "FAIL")
                row[k + "_A"], row[k + "_B"], row[k + "_A_quote"], row[k + "_B_quote"], row[k + "_A_contain"], row[k + "_B_contain"] = va, vb, qa, qb, ca, cb
                for tag, q, c in (("A", qa, ca), ("B", qb, cb)):
                    if c == "FAIL": queue.append((b, ref, k, "%s quote not contained: %r" % (tag, q[:120])))
                if k in adj.get(f, {}):
                    final, src, q = adj[f][k][0], "adjudicated", adj[f][k][1]
                elif va == vb and va != "": final, src, q = va, "agree", qa
                elif va and not vb: final, src, q = va, "A_only", qa
                elif vb and not va: final, src, q = vb, "B_only", qb
                else:
                    final, src, q = "", "disagree", ""; n_dis += 1
                    queue.append((b, ref, k, "A=%s | B=%s" % (va, vb)))
                row[k], row[k + "_src"], row[k + "_quote"] = final, src, q
                row[k + "_pos_frac"] = "%.3f" % (text.find(norm(q)) / max(1, len(text))) if q and norm(q) in text else ""
            row["n_disagree"] = n_dis
            rows.append(row)
    cols = list(rows[0].keys()) if rows else []
    os.makedirs(DATA, exist_ok=True)
    with io.open(os.path.join(DATA, "extraction_merged.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    open_items = [q for q in queue if q[2] == "FILE" or q[3].startswith("A=")]
    with io.open(os.path.join(DATA, "open_items.md"), "w", encoding="utf-8") as f:
        f.write("# Open items after adjudication\n\n")
        f.write("Fields where the two readers disagree and no adjudication exists. Quote containment failures are reported "
                "separately in the merged table (`*_contain` = FAIL) and never carry a final value.\n\n")
        f.write("| batch | trace | field | issue |\n|---|---|---|---|\n")
        for b, ref, k, msg in open_items:
            f.write("| %s | %s | %s | %s |\n" % (b, ref, k, msg.replace("|", "/")))
        if not open_items: f.write("\nNone.\n")
    print("traces:", len(rows), " open disagreements:", len(open_items),
          " containment failures:", sum(1 for q in queue if "not contained" in q[3]))
    print("final-value sources:", dict(Counter(r[k + "_src"] for r in rows for k in FIELDS)))

if __name__ == "__main__":
    main()
