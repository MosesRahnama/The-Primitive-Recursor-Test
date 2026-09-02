"""Static admissibility audit for every path-order entry in witness_check_100.py."""

import ast
from pathlib import Path


TARGET = Path(__file__).with_name("witness_check_100.py")
ALL = ['exp','mult','plus','minus','SUC','PRE','le','lt','ge','gt','eq',
       'EVEN','ODD','if','NUMERAL','BIT1','BIT0','0','T','F']
lex = {symbol: 'lex' for symbol in ALL}
mul = {symbol: 'mul' for symbol in ALL}
ARITY = {
    '0':0, 'T':0, 'F':0,
    'BIT0':1, 'BIT1':1, 'NUMERAL':1, 'SUC':1, 'PRE':1,
    'EVEN':1, 'ODD':1,
    'exp':2, 'mult':2, 'plus':2, 'minus':2, 'eq':2,
    'le':2, 'lt':2, 'ge':2, 'gt':2,
    'if':3,
}
namespace = {'ALL': ALL, 'lex': lex, 'mul': mul}
tree = ast.parse(TARGET.read_text(encoding='utf-8'), filename=str(TARGET))
affected = []
count = 0
for node in ast.walk(tree):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        continue
    if node.func.id != 'check_new':
        continue
    count += 1
    session = ast.literal_eval(node.args[0])
    levels = eval(compile(ast.Expression(node.args[2]), str(TARGET), 'eval'), namespace)
    status = eval(compile(ast.Expression(node.args[3]), str(TARGET), 'eval'), namespace)
    problems = []
    for level in levels:
        arities = {ARITY[symbol] for symbol in level}
        statuses = {status.get(symbol, 'lex') for symbol in level}
        if len(arities) > 1 or len(statuses) > 1:
            problems.append((sorted(level), sorted(arities), sorted(statuses)))
    if problems:
        affected.append((session, problems))

print(f'path_entries={count} incompatible_entries={len(affected)}')
for session, problems in affected:
    print(session)
    for symbols, arities, statuses in problems:
        print(f'  symbols={symbols} arities={arities} statuses={statuses}')
