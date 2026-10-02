r"""Recode the labeled trace corpora into one per-trace table.

Output: data/corpus_recoded.jsonl, one record per trace:
  corpus, split, item_id, generator, domain, steps[list[str]], problem, gold_answer,
  final_answer, final_correct (bool|None), error_positions[list[int]], first_error (int|-1),
  has_error (bool), unuseful_positions (DeltaBench only), reflection_positions, strategy_shift_positions,
  provenance ("natural"|"injected")
Every label is copied verbatim from the source; nothing is inferred.
"""
import ast, csv, glob, io, json, os, re, sys

from common import CORPORA as ROOT, DATA
OUT = os.path.join(DATA, "corpus_recoded.jsonl")
csv.field_size_limit(10 ** 9)


def rec(**k):
    k.setdefault("generator", "")
    k.setdefault("domain", "")
    k.setdefault("gold_answer", None)
    k.setdefault("final_answer", None)
    k.setdefault("final_correct", None)
    k.setdefault("unuseful_positions", [])
    k.setdefault("reflection_positions", [])
    k.setdefault("strategy_shift_positions", [])
    k.setdefault("provenance", "natural")
    k["first_error"] = min(k["error_positions"]) if k["error_positions"] else -1
    k["has_error"] = bool(k["error_positions"])
    return k


def processbench():
    for split in ("gsm8k", "math", "olympiadbench", "omnimath"):
        for r in json.load(io.open(os.path.join(ROOT, "processbench", split + ".json"), encoding="utf-8")):
            yield rec(corpus="processbench", split=split, item_id=r["id"], generator=r["generator"], domain="math",
                      steps=list(r["steps"]), problem=r["problem"], final_correct=bool(r["final_answer_correct"]),
                      error_positions=[r["label"]] if r["label"] != -1 else [])


def bbm():
    for split in ("word_sorting", "tracking_shuffled_objects", "logical_deduction", "multistep_arithmetic", "dyck_languages"):
        for i, line in enumerate(io.open(os.path.join(ROOT, "bigbench-mistake", split + ".jsonl"), encoding="utf-8")):
            r = json.loads(line)
            yield rec(corpus="bbm", split=split, item_id="%s-%d" % (split, i), generator="PaLM-2", domain="symbolic",
                      steps=list(r["steps"]), problem=r["input"], gold_answer=str(r["target"]), final_answer=str(r["answer"]),
                      final_correct=str(r["answer"]).strip() == str(r["target"]).strip(),
                      error_positions=[r["mistake_index"]] if r["mistake_index"] is not None else [])


def mrgsm8k():
    for r in json.load(io.open(os.path.join(ROOT, "mr-gsm8k", "MR-GSM8K.json"), encoding="utf-8")):
        fe = r["model_output_solution_first_error_step"]
        errs = [] if fe in ("N/A", None, "") else [int(fe) - 1]
        yield rec(corpus="mrgsm8k", split=r["question_type"], item_id=r["uuid"], domain="math",
                  steps=list(r["model_output_steps"]), problem=r["question"], gold_answer=str(r["ground_truth_answer"]),
                  final_correct=r["model_output_answer_correctness"] == "correct", error_positions=errs)


def retraceqa():
    import pyarrow.parquet as pq
    for f in sorted(glob.glob(os.path.join(ROOT, "retraceqa", "**", "*.parquet"), recursive=True)):
        split = os.path.basename(os.path.dirname(f))
        t = pq.read_table(f).to_pandas()
        for i, r in t.iterrows():
            paras = re.findall(r"<paragraph_\d+>(.*?)</paragraph_\d+>", str(r["model_output"]), flags=re.S)
            steps = [p.strip() for p in paras] if paras else [s for s in str(r["model_output"]).split("\n") if s.strip()]
            a = r["annotation"]
            errs = [] if a is None or a != a or float(a) < 0 else [int(float(a))]  # NaN and -1 are clean
            yield rec(corpus="retraceqa", split=split, item_id="%s-%d" % (split, i), generator=str(r["model_name"]),
                      domain="qa", steps=steps, problem=str(r["question"]), gold_answer=str(r["answer"]),
                      error_positions=errs)


def deltabench():
    rows = list(csv.DictReader(io.open(os.path.join(ROOT, "deltabench", "Deltabench_v1.csv"), encoding="utf-8", newline="")))
    for r in rows:
        secs = r["sections_content"]
        try:
            parsed = ast.literal_eval(secs)
            steps = [str(s.get("content", s)) if isinstance(s, dict) else str(s) for s in parsed] if isinstance(parsed, list) else None
        except Exception:
            steps = None
        if not steps:
            steps = [s for s in re.split(r"\n(?=section\s*\d+)", secs, flags=re.I) if s.strip()] or [secs]
        lit = lambda k: [int(x) - 1 for x in ast.literal_eval(r[k] or "[]")] if r.get(k) else []
        yield rec(corpus="deltabench", split=r["task_l1"], item_id=r["id"], domain=r["task_l1"],
                  steps=steps, problem=r["question"], gold_answer=r["answer"], final_correct=False,
                  error_positions=lit("reason_error_section_numbers"), unuseful_positions=lit("reason_unuseful_section_numbers"),
                  reflection_positions=lit("reflection_section_numbers"),
                  strategy_shift_positions=lit("stragegy_shift_section_numbers"))


def grace():
    for r in json.load(io.open(os.path.join(ROOT, "grace", "data_grace_examples.json"), encoding="utf-8")):
        yield rec(corpus="grace", split=r["track"], item_id=str(r["id"]), generator=r["model"], domain="qa",
                  steps=[s["step_text"] for s in r["steps"]], problem=r["question"], gold_answer=str(r["gold_answer"]),
                  final_answer=str(r["final_answer"]), final_correct=bool(r["is_correct"]),
                  error_positions=[i for i, s in enumerate(r["steps"]) if s["faithfulness"] == "unfaithful"])


def prmbench():
    for line in io.open(os.path.join(ROOT, "prmbench", "prmbench_preview.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        yield rec(corpus="prmbench", split=r["classification"], item_id=str(r["idx"]), domain="math",
                  steps=list(r["modified_process"]), problem=r["question"],
                  error_positions=[int(x) for x in r["error_steps"]], provenance="injected")
        yield rec(corpus="prmbench_clean", split=r["classification"], item_id=str(r["idx"]) + "-orig", domain="math",
                  steps=list(r["original_process"]), problem=r["question"], error_positions=[], provenance="injected-control")


def main():
    n = 0
    with io.open(OUT, "w", encoding="utf-8") as f:
        for gen in (processbench, bbm, mrgsm8k, retraceqa, deltabench, grace, prmbench):
            k = 0
            for r in gen():
                f.write(json.dumps(r, ensure_ascii=False) + "\n"); k += 1
            print("%-14s %6d" % (gen.__name__, k)); n += k
    print("total", n, "->", OUT)


if __name__ == "__main__":
    main()
