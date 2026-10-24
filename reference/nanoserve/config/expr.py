"""Reference: +/- expression evaluator."""
from __future__ import annotations


# LC 224 Basic Calculator
def eval_expr(s: str) -> int:
    result = 0
    sign = 1
    num = 0
    stack: list[tuple[int, int]] = []
    for ch in s:
        if ch.isdigit():
            num = num * 10 + int(ch)
        elif ch in "+-":
            result += sign * num
            num = 0
            sign = 1 if ch == "+" else -1
        elif ch == "(":
            stack.append((result, sign))
            result, sign = 0, 1
        elif ch == ")":
            result += sign * num
            num = 0
            prev, prev_sign = stack.pop()
            result = prev + prev_sign * result
    return result + sign * num
