r"""Re-check the stated whole-term MEASURES (not interpretations) in the payload-scaling corpus.

Three grok-4.5 sessions certify termination by the measure

    mu(t) = multiset of third-argument depths of every F occurrence in t

(one of them lexicographically paired with the F count), claiming that the recursive
rule replaces one F at depth d+1 by one F at depth d. That accounting is correct only
when the payload y contains no F. When y does, the rule copies every F inside y k times,
and the multiset gains k-1 extra copies of each of those depths. The Dershowitz-Manna
order then fails to decrease as soon as any F inside y sits at depth >= d+1.

This script builds that instance and evaluates the measure before and after one root
step, so the verdict is reproducible without trusting the prose.

Usage: python payload_scaling_verify_measures.py
"""
from collections import Counter


def mk(sym, *args):
    return (sym,) + tuple(args)


def s_iter(j, t):
    for _ in range(j):
        t = mk("S", t)
    return t


def depth(t):
    """Constructor depth of a Z/S numeral; 0 for anything else at the head."""
    d = 0
    while t[0] == "S":
        d += 1
        t = t[1]
    return d


def f_depths(t, acc):
    if t[0] == "F":
        acc.append(depth(t[3]))
    for a in t[1:]:
        if isinstance(a, tuple):
            f_depths(a, acc)
    return acc


def ms_gt(m, n):
    """Dershowitz-Manna: m > n iff n arises from m by replacing >=1 element by finitely many
    strictly smaller ones. Decidable form: m != n and for every x with n(x) > m(x) there is
    y > x with m(y) > n(y)."""
    if m == n:
        return False
    for x in n:
        if n[x] > m.get(x, 0):
            if not any(y > x and m[y] > n.get(y, 0) for y in m):
                return False
    return True


def step_rule2(k, x, y, n):
    lhs = mk("F", x, y, mk("S", n))
    rhs = mk("G", *([y] * k), mk("F", x, y, n))
    return lhs, rhs


def main():
    a, b = mk("a"), mk("b")
    print("%-22s %-3s %-6s %s" % ("payload y", "k", "mu(lhs) > mu(rhs)?", "multisets before / after"))
    print("-" * 90)
    for k in (0, 1, 2, 8):
        for label, y in (("F-free: y = b", b),
                         ("y = F(a,b,S^1(Z))", mk("F", a, b, s_iter(1, mk("Z")))),
                         ("y = F(a,b,S^5(Z))", mk("F", a, b, s_iter(5, mk("Z"))))):
            lhs, rhs = step_rule2(k, a, y, mk("Z"))
            ml, mr = Counter(f_depths(lhs, [])), Counter(f_depths(rhs, []))
            ok = ms_gt(ml, mr)
            print("%-22s %-3d %-6s        %s / %s" % (label, k, "yes" if ok else "NO", dict(ml), dict(mr)))
    print()
    print("The multiset-of-third-argument-depths measure decreases on every instance only at k = 0.")
    print("For every k >= 1 it fails on each instance whose payload contains an F at depth >= that")
    print("of the redex. Pairing it lexicographically with the F count does not help; the multiset")
    print("component is compared first and already fails.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
