"""Audit the 17 production encodings for textbook status-tier admissibility."""

from __future__ import annotations

import ast
import contextlib
import io
import runpy
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
CHECKER = BASE / "witness_check_40.py"
ARITY = {
    "0": 0, "T": 0, "F": 0,
    "BIT0": 1, "BIT1": 1, "NUMERAL": 1, "SUC": 1, "PRE": 1,
    "EVEN": 1, "ODD": 1,
    "exp": 2, "mult": 2, "plus": 2, "minus": 2, "eq": 2,
    "le": 2, "lt": 2, "ge": 2, "gt": 2,
    "if": 3,
}

with contextlib.redirect_stdout(io.StringIO()):
    namespace = runpy.run_path(str(CHECKER), run_name="checker_admissibility_import")

tree = ast.parse(CHECKER.read_text(encoding="utf-8"), filename=str(CHECKER))
records = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        continue
    if node.func.id != "check" or len(node.args) < 2:
        continue
    order_call = node.args[1]
    if not isinstance(order_call, ast.Call) or not isinstance(order_call.func, ast.Name):
        continue
    if order_call.func.id != "Order":
        continue
    label = ast.literal_eval(node.args[0])
    levels = eval(compile(ast.Expression(order_call.args[0]), str(CHECKER), "eval"), namespace)
    status = eval(compile(ast.Expression(order_call.args[1]), str(CHECKER), "eval"), namespace)
    incompatible = []
    for group in levels:
        arities = {ARITY[symbol] for symbol in group}
        statuses = {status.get(symbol, "lex") for symbol in group}
        if len(arities) > 1 or len(statuses) > 1:
            incompatible.append((sorted(group), sorted(arities), sorted(statuses)))
    records.append((label, incompatible))

assert len(records) == 17
affected = [(label, groups) for label, groups in records if groups]
print(f"encodings=17 incompatible_tier_encodings={len(affected)}")
for label, groups in affected:
    print(label)
    for symbols, arities, statuses in groups:
        print(f"  symbols={symbols} arities={arities} statuses={statuses}")
