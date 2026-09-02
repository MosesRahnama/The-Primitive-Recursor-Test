"""Mechanical witness check for the CURRENT 40-session corpus (2026-08-03).
One entry per session that commits to a specific global path-order witness.
RPO with quasi-precedence; statuses: 'lex' (left-to-right), 'lexrl'
(right-to-left), 'mul'. Equality is syntactic modulo head-equivalence, so the
check is at least as strict as the real order: PASS is sound; each FAIL line
names the unoriented rule for hand inspection. Where a stated precedence is
partial, the completion honors every stated constraint and is recorded here.
Replay: python witness_check_40.py   (needs Kaliszyk_19_arith.trs beside it)."""
import re

def tokenize(s): return re.findall(r'[A-Za-z0-9_]+|[(),]', s)

def parse_term(toks, i=0):
    name = toks[i]; i += 1
    if i < len(toks) and toks[i] == '(':
        i += 1; args = []
        while toks[i] != ')':
            t, i = parse_term(toks, i)
            args.append(t)
            if toks[i] == ',': i += 1
        return (name, tuple(args)), i + 1
    return (name, ()), i

def parse_trs(path):
    txt = open(path, encoding='utf-8').read()
    vars_ = set(re.search(r'\(VAR([^)]*)\)', txt).group(1).split())
    body = txt[txt.index('(RULES') + 6: txt.rindex(')')]
    rules = []
    for line in body.splitlines():
        line = line.strip()
        if '->' not in line: continue
        l, r = line.split('->', 1)
        rules.append((parse_term(tokenize(l.strip()))[0],
                      parse_term(tokenize(r.strip()))[0], line))
    return vars_, rules

class Order:
    def __init__(self, levels, status, variables):
        unknown = set(status.values()) - {'lex', 'lexrl', 'mul'}
        if unknown:
            raise ValueError(f'unknown status values: {sorted(unknown)}')
        self.rank = {}
        for depth, group in enumerate(levels):
            for f in group: self.rank[f] = len(levels) - depth
        self.status = status; self.vars = variables
    def is_var(self, t): return t[0] in self.vars and not t[1]
    def eq(self, s, t):
        if self.is_var(s) or self.is_var(t): return s == t
        if len(s[1]) != len(t[1]): return False
        if s[0] != t[0] and self.rank.get(s[0]) != self.rank.get(t[0]): return False
        return all(self.eq(a, b) for a, b in zip(s[1], t[1]))
    def gt(self, s, t):
        if self.is_var(s): return False
        if self.is_var(t): return occurs(t, s) and s != t
        f, ss = s; g, ts = t
        for si in ss:
            if self.eq(si, t) or self.gt(si, t): return True
        if f not in self.rank or g not in self.rank:
            raise KeyError(f'missing from precedence: {f if f not in self.rank else g}')
        if self.rank[f] > self.rank[g]:
            return all(self.gt(s, tj) for tj in ts)
        if self.rank[f] == self.rank[g]:
            # A status order must use one compatible status throughout a
            # quasi-precedence class. The production checker omits this guard.
            if f != g and self.status.get(f, 'lex') != self.status.get(g, 'lex'):
                return False
            if not all(self.gt(s, tj) for tj in ts): return False
            st = self.status.get(f, 'lex')
            if st == 'mul': return self.mul_gt(list(ss), list(ts))
            seq_s = ss if st == 'lex' else tuple(reversed(ss))
            seq_t = ts if st == 'lex' else tuple(reversed(ts))
            for a, b in zip(seq_s, seq_t):
                if self.eq(a, b): continue
                return self.gt(a, b)
            return len(ss) > len(ts)
        return False
    def mul_gt(self, M, N):
        M, N = M[:], N[:]
        for m in M[:]:
            for n in N[:]:
                if self.eq(m, n): M.remove(m); N.remove(n); break
        if not M: return False
        return all(any(self.gt(m, n) for m in M) for n in N)

def occurs(x, t):
    return t == x or any(occurs(x, a) for a in t[1])

def check(name, order, rules):
    fails = []
    for l, r, src in rules:
        try: ok = order.gt(l, r)
        except KeyError as e: fails.append((src, str(e))); continue
        if not ok: fails.append((src, 'not oriented'))
    tag = 'SOUND (all 108 oriented)' if not fails else f'FALSE ({len(fails)} rule failures)'
    print(f'{name}: {tag}')
    for src, why in fails[:6]: print(f'    FAIL: {src}   [{why}]')
    return fails

variables, rules = parse_trs('Kaliszyk_19_arith.trs')
ALL = ['exp','mult','plus','minus','SUC','PRE','le','lt','ge','gt','eq',
       'EVEN','ODD','if','NUMERAL','BIT1','BIT0','0','T','F']
lex = {f: 'lex' for f in ALL}
mul = {f: 'mul' for f in ALL}
print(f'parsed {len(rules)} rules\n-- carried over from pilot (sessions still in corpus) --')

check('claude-sonnet-5_T21-56-34-00000 [RPO mul, exact stated]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC','PRE'},
             {'EVEN','ODD','eq','le','lt','ge','gt','minus'},
             {'BIT0','BIT1','NUMERAL','0','if','T','F'}], mul, variables), rules)
check('grok-4.5_T21-52-32-00004 [RPO strict, faithful completion]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'SUC'},{'PRE'},{'BIT1'},{'BIT0'},
             {'NUMERAL'},{'if'},{'eq'},{'le'},{'lt'},{'ge'},{'gt'},{'EVEN'},{'ODD'},
             {'T'},{'F'},{'0'}],
            {f:('lex' if f in ('exp','mult','plus','minus','eq','le','lt','ge','gt') else 'mul') for f in ALL},
            variables), rules)
check('grok-4.5_T21-58-52-00016 [RPO strict chain, faithful completion]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'PRE'},{'if'},{'eq'},{'le'},{'lt'},
             {'minus'},{'ge'},{'gt'},{'EVEN'},{'ODD'},{'BIT0'},{'BIT1'},{'NUMERAL'},
             {'0'},{'T'},{'F'}], mul, variables), rules)
check('grok-4.5_T21-59-06-00017 [RPO lex quasi, exact stated]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'PRE'},{'SUC'},{'if'},{'le','lt'},
             {'ge','gt'},{'eq'},{'EVEN'},{'ODD'},{'BIT0','BIT1'},{'NUMERAL'},
             {'0','T','F'}], lex, variables), rules)
check('grok-4.5_T21-59-52-00018 [RPO strict chain, exact stated]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'PRE'},{'minus'},{'if'},{'eq'},{'le'},
             {'lt'},{'ge'},{'gt'},{'EVEN'},{'ODD'},{'BIT1'},{'BIT0'},{'NUMERAL'},{'0'},
             {'T','F'}], lex, variables), rules)
check('grok-4.5_T22-00-02-00019 [LPO strict chain, faithful completion]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'PRE'},{'minus'},{'le'},{'lt'},{'ge'},
             {'gt'},{'eq'},{'EVEN'},{'ODD'},{'NUMERAL'},{'BIT1'},{'BIT0'},{'if'},{'0'},
             {'T'},{'F'}], lex, variables), rules)

print('\n-- new sessions (second wave + recollected gemini) --')
check('claude-sonnet-5_T22-22-31-00002 [grouped hierarchy, mul status; if/T/F bottom completion]',
      Order([{'exp'},{'mult'},{'plus','minus'},{'PRE','SUC'},
             {'eq','le','lt','ge','gt','EVEN','ODD'},{'BIT0','BIT1'},
             {'NUMERAL','0','if','T','F'}], mul, variables), rules)
check('gemini_T22-22-31-00006 [RPOS lex, stated partial; completion adds SUC/PRE/minus > numeral constructors]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'SUC'},{'PRE'},{'le','lt'},{'ge','gt'},
             {'if','eq','EVEN','ODD','NUMERAL'},{'BIT0','BIT1'},{'0','T','F'}],
            lex, variables), rules)
check('gemini_T22-22-31-00007 [LPO lex, stated chain; tier {if,le,lt}]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'PRE'},{'SUC'},{'if','le','lt'},
             {'ge','gt'},{'eq'},{'EVEN','ODD'},{'BIT1'},{'BIT0'},{'NUMERAL'},
             {'T','F','0'}], lex, variables), rules)
check('gemini_T22-22-31-00008 [stated chain w/ SUC>PRE>minus; lex exp/eq/comparisons, mul plus/mult/minus]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'PRE'},{'minus'},{'if'},{'le','lt'},
             {'ge','gt'},{'eq'},{'EVEN'},{'ODD'},{'NUMERAL'},{'BIT0'},{'BIT1'},{'0'},
             {'T'},{'F'}],
            {f:('mul' if f in ('plus','mult','minus') else 'lex') for f in ALL},
            variables), rules)
check('gemini_T22-22-31-00009 [MPO, stated constraints; completion]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'SUC'},{'PRE'},{'le','lt'},{'ge','gt'},
             {'eq'},{'if'},{'EVEN','ODD'},{'NUMERAL'},{'BIT1'},{'BIT0'},{'0'},{'T','F'}],
            mul, variables), rules)
check('gemini_T22-23-15-00010 [LPO lex, stated chain]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'minus'},{'PRE'},{'eq'},{'le','lt'},
             {'ge','gt'},{'EVEN'},{'ODD'},{'if'},{'BIT1'},{'BIT0'},{'NUMERAL'},{'0'},
             {'T'},{'F'}], lex, variables), rules)
check('gemini_T22-23-26-00011 [RPO mixed statuses incl. right-to-left lex, stated chain]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'PRE'},{'SUC'},{'if'},{'le','lt'},
             {'ge','gt'},{'eq'},{'EVEN'},{'ODD'},{'BIT1'},{'BIT0'},{'NUMERAL'},{'T'},
             {'F'},{'0'}],
            {**lex, 'exp':'lexrl', 'ge':'lexrl', 'gt':'lexrl', 'eq':'mul'},
            variables), rules)
check('gemini_T22-23-48-00012 [LPO lex, "roughly" tiers as stated]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC','minus'},{'PRE'},
             {'if','le','lt','ge','gt','eq','EVEN','ODD'},{'BIT1','BIT0'},{'NUMERAL'},
             {'0','T','F'}], lex, variables), rules)
check('gemini_T22-23-48-00013 [LPO lex, stated chain]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'minus'},{'PRE'},{'if'},{'le','lt'},
             {'ge','gt'},{'eq'},{'EVEN','ODD'},{'NUMERAL'},{'BIT1'},{'BIT0'},{'0'},
             {'T'},{'F'}], lex, variables), rules)
check('grok-4.5_T22-24-31-00017 [RPO lex, stated constraint set; completion]',
      Order([{'exp'},{'mult'},{'plus'},{'minus'},{'SUC'},{'PRE'},{'if'},{'eq'},
             {'le','lt'},{'ge','gt'},{'EVEN'},{'ODD'},{'NUMERAL'},{'BIT1'},{'BIT0'},
             {'0'},{'T'},{'F'}], lex, variables), rules)
check('grok-4.5_T22-25-02-00019 [LPO, stated chain w/ PRE>minus; faithful completion]',
      Order([{'exp'},{'mult'},{'plus'},{'SUC'},{'PRE'},{'minus'},{'eq'},{'le'},{'lt'},
             {'ge'},{'gt'},{'EVEN'},{'ODD'},{'BIT0','BIT1','NUMERAL','if'},{'0'},
             {'T'},{'F'}], lex, variables), rules)
