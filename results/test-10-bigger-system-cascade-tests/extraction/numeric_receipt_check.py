"""Independent tree-recursion check of the two numeric receipts."""


def node(head, *args):
    return head, args


def depth(term):
    return 1 if not term[1] else 1 + max(depth(arg) for arg in term[1])


def size(term):
    return 1 + sum(size(arg) for arg in term[1])


zero = node("0")
bit1_zero = node("BIT1", zero)
bit0_zero = node("BIT0", zero)

plus_lhs = node("plus", bit1_zero, bit1_zero)
plus_rhs = node("BIT0", node("SUC", node("plus", zero, zero)))
exp_lhs = node("exp", bit0_zero, bit0_zero)
exp_call = node("exp", bit0_zero, zero)
exp_rhs = node("mult", exp_call, exp_call)

receipt = {
    "plus_depth_lhs": depth(plus_lhs),
    "plus_depth_rhs": depth(plus_rhs),
    "exp_size_lhs": size(exp_lhs),
    "exp_size_rhs": size(exp_rhs),
}
assert receipt == {
    "plus_depth_lhs": 3,
    "plus_depth_rhs": 4,
    "exp_size_lhs": 5,
    "exp_size_rhs": 9,
}
for key, value in receipt.items():
    print(f"{key}={value}")
