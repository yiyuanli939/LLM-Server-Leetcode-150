"""Reference: benchmark sweep expansion."""
from __future__ import annotations

_KEYPAD = {
    "2": "abc", "3": "def", "4": "ghi", "5": "jkl",
    "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz",
}


# LC 77 Combinations
def choose(n: int, k: int) -> list[list[int]]:
    out: list[list[int]] = []
    path: list[int] = []

    def bt(start: int) -> None:
        if len(path) == k:
            out.append(path[:])
            return
        for x in range(start, n - (k - len(path)) + 2):
            path.append(x)
            bt(x + 1)
            path.pop()

    bt(1)
    return out


