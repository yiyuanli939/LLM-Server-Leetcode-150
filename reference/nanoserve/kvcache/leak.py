from __future__ import annotations


# LC 136 Single Number
def find_leaked(events: list[int]) -> int:
    x = 0
    for v in events:
        x ^= v
    return x


