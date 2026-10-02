"""Build the third-read queues for a study 1/3 corpus from data/disagreements_<corpus>.jsonl.

Usage: python build_adjudication_queues.py [mrgsm8k|prm800k]   (default mrgsm8k)
Selection (the open fields that feed a cited number): E8 open on any item, or E1 open on an item whose final answer
is correct (the study 1 population; every PRM800K item). Labels are read here only to select; nothing from them is
written into a queue. Output: adjudication/queue_<corpus>_bNN.jsonl, 31 items each, format per schema/ADJUDICATOR.md
(id, item, A, B, open_fields restricted to E1, E8, E8_step, E8_kind). Headline-cell items (correct answer, wrong solution) go first.
"""
import io, os, csv, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from common import DATA, ADJ, read_jsonl, write_jsonl

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "mrgsm8k"
DECIDED = ("E1", "E8", "E8_step", "E8_kind")
SIZE = 31
labels = {r["id"]: r for r in csv.DictReader(io.open(os.path.join(DATA, "labels_%s.csv" % CORPUS), encoding="utf-8-sig", newline=""))}
queue = []
for it in read_jsonl(os.path.join(DATA, "disagreements_%s.jsonl" % CORPUS)):
    of = [f for f in it["open_fields"] if f in DECIDED]
    lab = labels[it["id"]]
    keep = "E8" in of or ("E1" in of and lab["answer_correct"] == "correct")
    if not keep: continue
    if "E1" in of and lab["answer_correct"] != "correct": of.remove("E1")   # E1 on a wrong answer feeds no cited number
    head = lab["answer_correct"] == "correct" and lab["solution_correct"] == "wrong"
    queue.append((0 if head else 1, {"id": it["id"], "item": it["item"], "A": it["A"], "B": it["B"], "open_fields": of}))
queue.sort(key=lambda x: x[0])
rows = [q for _, q in queue]
os.makedirs(ADJ, exist_ok=True)
n = 0
for i in range(0, len(rows), SIZE):
    n += 1
    write_jsonl(os.path.join(ADJ, "queue_%s_b%02d.jsonl" % (CORPUS, n)), rows[i:i + SIZE])
print("queue items", len(rows), "headline-cell first", sum(1 for h, _ in queue if h == 0), "batches", n, "of", SIZE)
