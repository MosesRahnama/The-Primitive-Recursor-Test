"""Move the 960 study-6 sessions into the benchmark corpus in the standard arm layout. File operations only; no network.

Target: the corpus arm results/external-benchmarks/bird-interact-sessions/ of the benchmark repository:
  test-sessions\\<instance>__<arm>__<model>\\prompt.txt      the prompt the model received (rebuilt from the task files and
                                                             checked against the sha256 stored at collection time)
                                                 response.txt  the model's visible reply, verbatim
                                                 reasoning.txt the provider-returned reasoning stream, when any
                                                 session.json  the collection record (model id, arm, usage, cost, timestamps, budget)
  tasks.jsonl   the 120 sampled tasks with their ambiguity keys
  README.md     arm description
The source folder data\\s6_sessions is removed after every file is verified in place.
"""
import io, os, json, glob, hashlib, shutil, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CORPORA, DATA, ARM, read_jsonl

BIRD = os.path.join(CORPORA, "bird-interact-full")
SRC = os.path.join(DATA, "s6_sessions")
SESS = os.path.join(ARM, "test-sessions")

PROMPT = """You are given a PostgreSQL database and a user request. Write the SQL query that answers the request.

Database schema:
{schema}

Column meanings:
{columns}

Reference knowledge (definitions the database owner has documented):
{kb}

User request:
{query}

{closing}"""
CLOSING = {"bare": "Return the PostgreSQL query.",
           "permitted": "Return the PostgreSQL query. If the request is unclear on a point that changes the query, you may instead ask the user one clarifying question."}

def build_prompt(task, arm):
    db = task["selected_database"]
    schema = io.open(os.path.join(BIRD, db, db + "_schema.txt"), encoding="utf-8", errors="replace").read()
    columns = io.open(os.path.join(BIRD, db, db + "_column_meaning_base.json"), encoding="utf-8", errors="replace").read()
    deleted = {k.get("deleted_knowledge") for k in task.get("knowledge_ambiguity", [])}
    kb_lines = []
    for l in io.open(os.path.join(BIRD, db, db + "_kb.jsonl"), encoding="utf-8"):
        k = json.loads(l)
        if k["id"] in deleted: continue
        kb_lines.append("- %s: %s %s" % (k["knowledge"], k.get("description", ""), k.get("definition", "")))
    return PROMPT.format(schema=schema.strip(), columns=columns.strip(), kb="\n".join(kb_lines), query=task["amb_user_query"].strip(), closing=CLOSING[arm])

def main():
    tasks = {t["instance_id"]: t for t in (json.loads(l) for l in io.open(os.path.join(BIRD, "bird_interact_data.jsonl"), encoding="utf-8"))}
    sampled = read_jsonl(os.path.join(DATA, "s6_tasks.jsonl"))
    os.makedirs(SESS, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.json")))
    moved = mismatch = 0
    for p in files:
        r = json.load(io.open(p, encoding="utf-8"))
        slug = "%s__%s__%s" % (r["instance_id"], r["arm"], r["model"])
        d = os.path.join(SESS, slug); os.makedirs(d, exist_ok=True)
        prompt = build_prompt(tasks[r["instance_id"]], r["arm"])
        sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if sha != r.get("prompt_sha256"):
            mismatch += 1; print("PROMPT SHA MISMATCH", slug)
        io.open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8", newline="").write(prompt)
        io.open(os.path.join(d, "response.txt"), "w", encoding="utf-8", newline="").write(r.get("content") or "")
        if r.get("reasoning"):
            io.open(os.path.join(d, "reasoning.txt"), "w", encoding="utf-8", newline="").write(r["reasoning"])
        rec = {k: v for k, v in r.items() if k not in ("content", "reasoning")}
        rec["prompt_sha256_rebuilt_matches"] = (sha == r.get("prompt_sha256"))
        io.open(os.path.join(d, "session.json"), "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=1))
        moved += 1
    shutil.copy2(os.path.join(DATA, "s6_tasks.jsonl"), os.path.join(ARM, "tasks.jsonl"))
    io.open(os.path.join(ARM, "README.md"), "w", encoding="utf-8").write(
"""# BIRD-Interact ambiguity sessions

| Item | Value |
|---|---|
| Relation to PRT | a separate collection for the external-benchmark study; not among the 4,160 PRT sessions |
| Object | 120 BIRD-Interact tasks whose user request is deliberately ambiguous (`tasks.jsonl`: request, critical ambiguities, deleted knowledge), stratified over the 22 databases, seed 20260904 |
| Prompt | schema, column meanings, knowledge base with the task's deleted entries removed, the request; arm `bare` asks for the SQL, arm `permitted` adds one sentence that permits one clarifying question |
| Models | gpt-5.4, claude-sonnet-4.6, deepseek-v4-pro, kimi-k2.6 (qwen3.7-max refused under the account's OpenRouter data policy and was replaced before any session was kept) |
| Sessions | 960 = 120 tasks x 2 arms x 4 models, one folder each under `test-sessions\\` |
| Collection | 2026-09-04 21:51 to 2026-09-05 16:44 UTC through OpenRouter, temperature 0; token budget 2,000, raised to 12,000 and then 30,000 for reasoning-model sessions whose visible reply came back empty; `session.json` records the budget used |
| Scoring | handling of each critical ambiguity (asked, declared, silent, absent) coded by readers under `results\\external-benchmarks\\schema\\READER-S6.md`; SQL correctness is unscored because the corpus authors withhold the gold SQL |
| Cost | $24.93 as recorded per response by OpenRouter |
""")
    if mismatch == 0 and moved == len(files):
        shutil.rmtree(SRC)
        print("moved %d sessions to %s; source folder removed" % (moved, ARM))
    else:
        print("moved %d, prompt mismatches %d; source folder kept" % (moved, mismatch))

if __name__ == "__main__":
    main()
