from __future__ import annotations


# LC 394 Decode String
def expand_template(s: str) -> str:
    stack: list[tuple[str, int]] = []
    cur, k = "", 0
    for ch in s:
        if ch.isdigit():
            k = k * 10 + int(ch)
        elif ch == "[":
            stack.append((cur, k))
            cur, k = "", 0
        elif ch == "]":
            prev, times = stack.pop()
            cur = prev + cur * times
        else:
            cur += ch
    return cur
