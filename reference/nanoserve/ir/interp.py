"""Reference: IR bytecode interpreter pieces."""
from __future__ import annotations


# LC 150 Evaluate Reverse Polish Notation
def eval_rpn(tokens: list[str]) -> int:
    stack: list[int] = []
    for t in tokens:
        if t in ("+", "-", "*", "/"):
            r = stack.pop()
            l = stack.pop()
            if t == "+":
                stack.append(l + r)
            elif t == "-":
                stack.append(l - r)
            elif t == "*":
                stack.append(l * r)
            else:
                stack.append(int(l / r))
        else:
            stack.append(int(t))
    return stack[-1]


