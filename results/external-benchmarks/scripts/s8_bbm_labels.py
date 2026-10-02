"""Study 8: arithmetic errors in BIG-Bench Mistake traces labeled free of mistakes (multistep arithmetic).

A trace whose mistake_index is empty carries the label "no mistake". The script counts those traces and those among
them whose answer differs from the target. It runs the arithmetic scan (boundary_guard/arithmetic.py) over every step
of those traces and counts the flagged traces with a wrong and with a correct answer. The scan also flags spans it
misparses, so each flagged trace was read in full; adjudication/bbm_flag_reading.csv records that reading, one row per
flagged span. For the eight traces whose reading found a false equation, the script finds the equation in the trace
text, evaluates both sides with integer arithmetic, and compares the left side with the stated right side and with the
target. Writes tables/s8_bbm_labels.csv.
"""
import ast, csv, io, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORPORA, TABLES, read_jsonl, contained

SOURCE = os.path.join(CORPORA, "bigbench-mistake", "multistep_arithmetic.jsonl")
OUT = os.path.join(TABLES, "s8_bbm_labels.csv")

# (zero-based line of the dataset file, the equation as written in the trace)
EQUATIONS = [
    (24, "-10 - (-32) - (-2) - (-25) = 15"),
    (34, "(8 + -14) + (-12) = -8"),
    (120, "336 * 74 + 52 = 24984 + 52"),
    (139, "(-2248 * 280) * (-2268 * 280) = -630720 * -630720"),
    (235, "(-23 + 17 - 6 + 9) = -13"),
    (237, "27 - (-3) - 15 + 50 = 69"),
    (283, "(0 + 16) - (-4 - -36) = 16 - (-32)"),
    (299, "(-3 + 330) + (-33 * -10) = 330 + 330"),
]


def value(expression):
    """Integer value of an expression built from integers, + - *, unary minus, and parentheses."""
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -ev(node.operand) if isinstance(node.op, ast.USub) else ev(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = ev(node.left), ev(node.right)
            return a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) else a * b
        raise ValueError("unsupported expression: %r" % expression)
    return ev(ast.parse(expression, mode="eval"))


def steps_text(record):
    steps = record["steps"]
    return steps if isinstance(steps, str) else " ".join(steps)


def step_list(record):
    steps = record["steps"]
    return list(steps) if isinstance(steps, list) else ast.literal_eval(steps)


def main():
    records = read_jsonl(SOURCE)
    clean = [i for i, r in enumerate(records) if r["mistake_index"] in (None, "", "None")]
    wrong = [i for i in clean if str(records[i]["answer"]).strip() != str(records[i]["target"]).strip()]
    rows = [
        {"measure": "traces", "line": "", "equation": "", "count": len(records), "note": "multistep_arithmetic.jsonl"},
        {"measure": "labeled mistake-free", "line": "", "equation": "", "count": len(clean), "note": "mistake_index empty"},
        {"measure": "labeled mistake-free, answer differs from target", "line": "", "equation": "", "count": len(wrong),
         "note": "zero-based lines " + " ".join(str(i) for i in wrong)},
    ]
    from boundary_guard.arithmetic import scan_plain_equalities
    flagged = [i for i in clean if any(scan_plain_equalities(step) for step in step_list(records[i]))]
    rows += [
        {"measure": "labeled mistake-free, flagged by the arithmetic scan", "line": "", "equation": "", "count": len(flagged),
         "note": "zero-based lines " + " ".join(str(i) for i in flagged)},
        {"measure": "flagged, answer differs from target", "line": "", "equation": "",
         "count": len([i for i in flagged if i in wrong]), "note": ""},
        {"measure": "flagged, answer equals target", "line": "", "equation": "",
         "count": len([i for i in flagged if i not in wrong]), "note": "each flag is a misparsed chain of equalities (bbm_flag_reading.csv)"},
        {"measure": "answer differs from target, not flagged", "line": "", "equation": "",
         "count": len([i for i in wrong if i not in flagged]), "note": ""},
    ]
    false_count = target_count = 0
    for line, equation in EQUATIONS:
        record = records[line]
        assert line in wrong, "line %d is not a labeled-mistake-free trace with a wrong answer" % line
        assert line in flagged, "line %d was not flagged by the arithmetic scan" % line
        assert contained(equation, steps_text(record)), "equation absent from line %d" % line
        left, right = equation.split(" = ")
        lv, rv, target = value(left), value(right), int(record["target"])
        false_count += lv != rv
        target_count += lv == target
        rows.append({"measure": "false equation", "line": line, "equation": equation, "count": "",
                     "note": "left %d, right %d, target %d, answer %s, left equals target: %s"
                             % (lv, rv, target, record["answer"], "yes" if lv == target else "no")})
    rows.append({"measure": "checked equations that are false", "line": "", "equation": "", "count": false_count,
                 "note": "of %d" % len(EQUATIONS)})
    rows.append({"measure": "false equations whose left side equals the target", "line": "", "equation": "",
                 "count": target_count, "note": "correcting the equation gives the target answer"})
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["measure", "line", "equation", "count", "note"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["measure"], r["line"], r["equation"], r["count"], r["note"])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
