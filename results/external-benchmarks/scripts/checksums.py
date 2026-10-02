"""Write batch_ids.csv and checksums.csv in the package root.

batch_ids.csv: the item ids each reader batch file held, in order (ids only, no item text), so the assignment of items
to readers is on record even though the batch files themselves are rebuilt from the external datasets.
checksums.csv: size and sha256 of every file in the package, marked committed (in the repository) or rebuilt (data/,
batches/, adjudication/queue_*: produced by the scripts from the external datasets and not redistributed). A rebuild
matches the study when its files carry the listed checksums.
Usage: python checksums.py
"""
import os, io, csv, hashlib, json, glob, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import EXT, BATCHES

REBUILT = ("data/", "batches/", "adjudication/queue_")

ids = []
for p in sorted(glob.glob(os.path.join(BATCHES, "*.jsonl"))):
    for k, l in enumerate(io.open(p, encoding="utf-8"), 1):
        if l.strip(): ids.append({"batch": os.path.basename(p), "line": k, "id": json.loads(l)["id"]})
with io.open(os.path.join(EXT, "batch_ids.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["batch", "line", "id"], lineterminator="\n"); w.writeheader(); w.writerows(ids)

rows = []
for dp, dn, fn in os.walk(EXT):
    dn[:] = [d for d in dn if d not in ("__pycache__", "corpora", "bird-interact-sessions")]
    for f in sorted(fn):
        p = os.path.join(dp, f); rel = os.path.relpath(p, EXT).replace("\\", "/")
        if rel == "checksums.csv": continue
        rows.append({"path": rel, "committed": "no" if rel.startswith(REBUILT) else "yes", "bytes": os.path.getsize(p),
                     "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()})
rows.sort(key=lambda r: r["path"])
with io.open(os.path.join(EXT, "checksums.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["path", "committed", "bytes", "sha256"], lineterminator="\n"); w.writeheader(); w.writerows(rows)
print("batch_ids.csv: %d lines; checksums.csv: %d files (%d committed, %d rebuilt)" % (
    len(ids), len(rows), sum(r["committed"] == "yes" for r in rows), sum(r["committed"] == "no" for r in rows)))
