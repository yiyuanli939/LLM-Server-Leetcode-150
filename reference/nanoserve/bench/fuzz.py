"""Reference: exhaustive fuzz generators."""
from __future__ import annotations


# LC 46 Permutations
def arrival_orders(ids: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    cur = ids[:]

    def bt(i: int) -> None:
        if i == len(cur):
            out.append(cur[:])
            return
        for j in range(i, len(cur)):
            cur[i], cur[j] = cur[j], cur[i]
            bt(i + 1)
            cur[i], cur[j] = cur[j], cur[i]

    bt(0)
    return out


# LC 22 Generate Parentheses
def balanced_brackets(n: int) -> list[str]:
    out: list[str] = []

    def bt(s: str, opened: int, closed: int) -> None:
        if len(s) == 2 * n:
            out.append(s)
            return
        if opened < n:
            bt(s + "(", opened + 1, closed)
        if closed < opened:
            bt(s + ")", opened, closed + 1)

    bt("", 0, 0)
    return out
