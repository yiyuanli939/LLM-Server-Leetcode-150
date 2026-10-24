from __future__ import annotations


# LC 1106 Parsing A Boolean Expression
def eval_flag_expr(expr: str) -> bool:
    stack: list[str] = []
    for c in expr:
        if c == ",":
            continue
        if c != ")":
            stack.append(c)
            continue
        seen_t = seen_f = False
        while stack[-1] != "(":
            if stack.pop() == "t":
                seen_t = True
            else:
                seen_f = True
        stack.pop()  # "("
        op = stack.pop()
        if op == "!":
            val = seen_f
        elif op == "&":
            val = not seen_f
        else:
            val = seen_t
        stack.append("t" if val else "f")
    return stack[-1] == "t"
