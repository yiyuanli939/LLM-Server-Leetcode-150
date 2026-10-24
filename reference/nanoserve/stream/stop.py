"""Reference: stream.find_stop, stream.permuted_stop."""
from __future__ import annotations



# LC 28 Find the Index of the First Occurrence in a String (KMP)
def find_stop(text: str, stop: str) -> int:
    m = len(stop)
    fail = [0] * m
    k = 0
    for i in range(1, m):
        while k and stop[i] != stop[k]:
            k = fail[k - 1]
        if stop[i] == stop[k]:
            k += 1
        fail[i] = k
    k = 0
    for i, ch in enumerate(text):
        while k and ch != stop[k]:
            k = fail[k - 1]
        if ch == stop[k]:
            k += 1
            if k == m:
                return i - m + 1
    return -1


