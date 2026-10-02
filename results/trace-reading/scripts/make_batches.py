"""Batch manifests for one arm: one text file of trace references per batch (15 files or 300,000 bytes).

Usage: python make_batches.py <test_suite> <file_names,comma-separated> <tag> [all]
Example: python make_batches.py schema-test-A-tests thinking_1.txt schemaA_t1
The 40 calibration sessions (data/calibration_sample.csv) are excluded because their first turn was hand-coded;
pass `all` as the fourth argument to include them (used for the follow-up turn).
"""
import csv, glob, io, os, sys
from common import DATA, BATCHES

MAX_FILES, MAX_BYTES = 15, 300_000
suite, turn_files, tag = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
cal = set() if (len(sys.argv) > 4 and sys.argv[4] == "all") else \
      {r["session_slug"] for r in csv.DictReader(io.open(os.path.join(DATA, "calibration_sample.csv"), encoding="utf-8-sig", newline=""))}
rows = [r for r in csv.DictReader(io.open(os.path.join(DATA, "thinking_files_inventory.csv"), encoding="utf-8-sig", newline=""))
        if r["test_suite"] == suite and r["file_name"] in turn_files and r["session_folder"] not in cal]
rows.sort(key=lambda r: r["session_folder"])
os.makedirs(BATCHES, exist_ok=True)
for old in glob.glob(os.path.join(BATCHES, tag + "_b*.txt")):
    os.remove(old)
batches, cur, cur_bytes = [], [], 0
for r in rows:
    sz = int(r["file_size_bytes"])
    if cur and (len(cur) >= MAX_FILES or cur_bytes + sz > MAX_BYTES):
        batches.append(cur); cur, cur_bytes = [], 0
    cur.append(r); cur_bytes += sz
if cur: batches.append(cur)
for i, chunk in enumerate(batches, 1):
    p = os.path.join(BATCHES, "%s_b%02d.txt" % (tag, i))
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(r["full_path"] for r in chunk) + "\n")
print("total", len(rows), "batches", len(batches))
